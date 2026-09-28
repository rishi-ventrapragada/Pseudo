# M3: Mini agent loop

## The concept in one paragraph

An **agent** is M2 in a loop. Each **iteration** (one trip around the loop, meaning one model call) sends the whole history plus the tool list. If the reply asks for tools, the program runs them and appends the results. If the reply is plain text, the model is saying "I'm done", and the loop stops. A hard cap (`MAX_ITERATIONS = 10`) guarantees it always ends. Because the model now acts on its own for several steps, safety can't depend on it behaving well. So the tools themselves enforce the rules. A **sandbox** means they can only touch `playground/sandbox/`, judged by where a path *really* ends up. An **approval gate** (a "human in the loop") means every write shows you a preview and waits for your `y`. And both are backed by tests that fail if anyone weakens them.

## Web-dev analogy

- **The loop** is like a client that keeps calling an API until the server says "complete". Here the "server" is the model, and it can say "first, run this for me".
- **The sandbox** is like Supabase row-level security: the rule lives in the data layer, so it holds no matter which client calls it. **Path traversal** (`../../secret`) is the classic attack on a static file server.
- **`startswith` vs `is_relative_to`** is like a route matcher where `/admin` wrongly matches `/administrator`.
- **The approval gate** is GitHub's "type the repo name to delete it": a confirmation before anything irreversible. A **safe default** (deny unless someone says yes) is like a CORS policy that blocks everything until you allow an origin.
- **429 + `retry-after`** is the same as backing off on any rate-limited API.
- **pytest** is like Jest or Vitest, a **fixture** is like `beforeEach` (but only for tests that ask for it), **monkeypatch** is like `vi.spyOn`, and **parametrize** is like `test.each`.

## What was built (file by file)

- **`playground/agent_tools.py`** (179 lines): `list_files`, `read_file`, `write_file`, the sandbox check, the approval gate, and `run_tool()`, the one entry point every brain uses. Plain Python with no model code (D11).
- **`playground/agent_tool_schemas.py`**: the three JSON schemas, which are all the model ever sees of the tools.
- **`playground/03_agent_loop.py`** (188 lines): the `while` loop, the terminal y/N prompt, and 429 handling.
- **`tests/conftest.py`**: shared fixtures. Each test gets its own temporary sandbox, an `outside` folder holding `secret.txt`, and fake "yes" or "no" humans.
- **`tests/test_sandbox.py`**: 37 escape tests: `../`, absolute paths, Windows names, and real links. **`tests/test_agent_tools.py`**: 22 tests for behavior, the approval gate, the dispatcher, and the schema contract.
- **`requirements.txt`**: adds `pytest==9.1.1`. **`.gitignore`**: adds `.pytest_cache/`.

## Walkthrough of the key code

**1. The sandbox check: judge a path by where it really ends up**
```python
if Path(raw).drive and not Path(raw).root:        # "C:notes.md": confusing drive-relative form
    raise SandboxError(...)
target = (root / raw).resolve()                   # collapses "..", follows symlinks/junctions
if not target.is_relative_to(root):               # compares whole path parts, not text
    raise SandboxError(f"{raw!r} is outside the sandbox")
if any(is_odd_windows_name(n) for n in target.relative_to(root).parts):
    raise SandboxError(f"{raw!r} uses a name Windows treats specially")
```
`resolve()` turns `sub/../../x` into its real location, and a **symlink** or **junction** (Windows' folder shortcut that needs no admin rights) into its real target. `is_relative_to` then asks "is this at or under the sandbox?" part by part, which is why `sandbox_evil` is correctly *outside* `sandbox`.

The last line handles names that are "inside" the folder but aren't normal files:
- `CON`, `NUL`, `COM1` are devices, and `COM1` is a serial port.
- `notes.md:hidden` is a hidden **alternate data stream**.
- Names ending in `.` or a space get silently changed by Windows.

**2. Hard links: the one trick `resolve()` can't see**
```python
if target.is_file() and target.stat().st_nlink > 1:
    raise SandboxError(...)
```
A **hard link** is one file with two names. `sandbox/twin.txt` can *be* a file that also lives outside the sandbox, with nothing to follow or resolve. `st_nlink` counts a file's names, so more than 1 means "this lives somewhere else too".

**3. `write_file`: check everything, then ask, then (and only then) write**
```python
target = resolve_in_sandbox(path)                 # 1. where would it land?
...size, folder, hard-link checks...              # 2. is it sane?
preview = build_preview(display(target), old, content)   # 3. what exactly changes
if not approver(preview):                         # 4. THE GATE
    return f"Denied: the user did not approve writing {path}. Nothing was written."
target.write_text(content, encoding="utf-8")      # 5. touch the disk
```
Bad writes are refused *before* you're asked, so you're never asked to approve something impossible.

**4. The gate is pluggable, and safe by default**
```python
approver: Callable[[str], bool] = deny_everything             # agent_tools.py
agent_tools.approver = terminal_approver(api_key)            # 03_agent_loop.py plugs in the terminal
```
The *check* lives in the tool. Only the *way of asking* is plugged in: today the terminal, later an MCP client or the overlay. If nothing is plugged in, every write is denied. `terminal_approver` is a **closure** (a function that builds and returns another function, remembering `api_key`), just like closures in JS.

**5. `run_tool`: only the schema's own arguments get through**
```python
unknown = sorted(set(kwargs) - ALLOWED_ARGUMENTS[name])
if unknown:  # e.g. a sneaky {"root": "C:/"}
    return f"Error: unknown argument(s) {unknown} for {name}."
```

**6. The loop and its exits**
```python
while iteration < MAX_ITERATIONS:
    ...call the model...
    if not message.tool_calls:   return 0       # DONE: plain text means "finished"
    for call in message.tool_calls:
        result = agent_tools.run_tool(call.function.name, call.function.arguments)
        messages.append({"role": "tool", "tool_call_id": call.id, "content": result})
return 1                                         # STOPPED: hit the cap
```
There are other exits too: `StopAgent` (bad key, 413, a long rate limit) and Ctrl+C. A denied write does **not** end the loop, because the model gets to react. A `400 tool_use_failed` (the M2 kind of error) is retried, and each retry counts toward the cap.

**7. Rate limits:** on `openai.RateLimitError` the loop sleeps for the `retry-after` seconds and retries the same call, at most 3 times. If the server asks for more than 60 s, it stops instead. `max_retries=0` means the SDK never retries silently behind our back.

## What happens when you run it (annotated real output, trimmed)

**The Done task, first attempt: a real failure.** My first system prompt said "every write needs the user's approval". The model replied in plain text: *"Do you approve creating notes.md with the following content?..."*. Plain text means DONE, so the loop ended after 1 iteration with no file. The fix was wording: "calling write_file automatically asks the user; never ask for permission in text". **The loop only knows one signal: whether the reply contains tool calls.**

**The Done task, fixed** (approvals answered by piped `y` lines):
```
=== ITERATION 1 of 10 | sending 2 messages + 3 tools ===
tokens this call: 466 in / 115 out | budget left this minute: 7188 of 8000
--- MODEL WANTS TO CALL TOOL: list_files ---          <- looks first
=== ITERATION 2 of 10 | sending 4 messages + 3 tools ===
--- APPROVAL NEEDED ---
write_file wants to CREATE sandbox/notes.md (289 characters): # Study Tips  1. **Active Recall** ...
Allow this write? [y/N] -> APPROVED (you typed 'y')
=== ITERATION 3 ... 4 ===  read_file notes.md (twice: redundant, but harmless)
=== ITERATION 5 of 10 | sending 10 messages + 3 tools ===
tokens this call: 777 in / 130 out | budget left this minute: 4889 of 8000
--- APPROVAL NEEDED ---
write_file wants to OVERWRITE sandbox/notes.md (289 -> 392 characters). Changes:
+4. **Chunking**: Break information into smaller, manageable units ...
Allow this write? [y/N] -> APPROVED (you typed 'y')
=== ITERATION 6 of 10 | sending 12 messages + 3 tools ===
--- DONE after 6 iteration(s) ---
assistant> Created `notes.md` with three study tips and then added a fourth tip about chunking.
13 messages, 4494 tokens in total.
```
The tokens sent per call grew 466 → 502 → 603 → 690 → 777 → 901: every iteration re-sends everything. One task used more than half of the 8K-per-minute budget.

**Denial** ("add a fifth tip", answered `n`): the preview showed `+5. **Multimodal Learning**...`, then `-> DENIED`. The tool result was `Denied: ... Nothing was written.` The model didn't retry, and said *"the write request was denied, so the file was not changed"*. The file hash was identical before and after.

**Escape attempts:** asked to read a decoy file outside the sandbox, the model refused **on its own** twice, without calling a tool. That's nice, but **a model's caution is not a security boundary**. It can be talked around, and a different model might not refuse. So the tool was tested directly with the exact paths: `read_file("..\..\..\..\Users\...\decoy.txt")`, the absolute path, `../../.env`, and `list_files("../..")` all returned `Error: '...' is outside the sandbox`.

> **Note (rule added after M3): the `../../.env` check is now banned.** Tests and checks must never read, open, or target real secrets, even in a local call with no model involved. If the check itself had a bug, the real key is exactly what would leak. Use decoy files instead, like the fake `secret.txt` that `tests/conftest.py` puts in the `outside` folder.

**429** (a fake one, injected by a test script):
```
--- RATE LIMITED (429): waiting 2 s, as the server asked (wait 1 of 3) ---
reply: 'ok' | model calls attempted: 2 | elapsed: 2.6 s
```
**Tests:** `59 passed in 3.35s`, with no skips, so real symlinks, junctions, and hard links were created. To check that the tests really catch problems, each safety check was broken on purpose (this is called **mutation testing**):
- `startswith` instead of `is_relative_to`: exactly `test_escape_tricks_are_refused[../sandbox_evil/x]` failed.
- Skipping the approval: 4 approval tests failed.
- Deleting the hard-link check: the hard-link test failed.

## Try this

1. **Hit the cap.** Set `MAX_ITERATIONS = 1` and run the notes task. You'll see `STOPPED: reached MAX_ITERATIONS = 1`. Set it back afterwards.
2. **Be the gate.** Run the notes task yourself and type `n` at the second preview. Watch what the model does with "Denied", then check `notes.md`.
3. **Break the sandbox (tests only!).** In `resolve_in_sandbox`, replace `target.is_relative_to(root)` with `str(target).startswith(str(root))` and run `python -m pytest -q`. The `sandbox_evil` test goes red. Undo it, and never run the agent with a check broken.

## Check yourself

1. Why does the sandbox check live in `agent_tools.py`, not in the loop?
2. Why is `str(target).startswith(str(root))` the wrong check?
3. What exactly happens when you answer `n`?
4. Why is there a `MAX_ITERATIONS` cap if the model eventually says it's done?
5. What does `retry-after` tell the loop, and why does it stop instead of waiting when the value is huge?

<details>
<summary>Answers</summary>

1. So the rules hold for *any* caller: this loop, a future MCP server, Hermes, anything (D11). A loop-level check would protect only this loop.
2. It compares text, so `C:\...\sandbox_evil` "starts with" `C:\...\sandbox` and would be allowed. `is_relative_to` compares whole path parts.
3. `write_file` returns `"Denied: ... Nothing was written."` without touching the disk. That string becomes the tool result, and the loop continues so the model can react. The prompt tells it not to retry, and it reported the denial.
4. Models can get stuck repeating steps or retrying forever, and every iteration costs tokens and rate-limit budget. The cap guarantees the loop ends.
5. It's how many seconds the server wants us to wait before trying again. A huge value (e.g. the daily limit is used up) means waiting would hang the program for hours, so the loop stops with a clear message.

</details>

## How this connects to Pseudo's final architecture

- **This loop is what Hermes (and Claude Code) run internally,** just with more tools, memory, and smarter stopping rules. You can now read any agent's core.
- **`run_tool(name, arguments)` is the seam.** A Phase 2 MCP server wraps these same functions and schemas, and the brain on the other side changes nothing inside them.
- **Sandbox + default-deny gate + pluggable approver** is the Phase 3 approval-gate pattern in miniature. `list_open_windows` and click/type tools will follow it.
- **Every tool result goes to the cloud model.** Phase 4's privacy layer sits exactly between `run_tool` and `messages.append`.
- **Known limit:** a link swapped in *between* the check and the write (a "race condition") isn't covered. That's acceptable for a learning sandbox, and it's worth remembering for real ones.

## Extension: count_words

A Phase 1 extra, added after M3 as a learning exercise. It shows that **adding a tool takes three small edits and some tests**, and the loop itself doesn't change:

1. **The function** (`agent_tools.py`): `count_words(path)` reuses the same safety checks as `read_file` (`resolve_in_sandbox`, `refuse_hard_links`, UTF-8 only), then returns `len(text.split())`. It only reads, so it needs no approval gate.
2. **The dispatcher entry** (`TOOL_FUNCTIONS`): `"count_words": count_words`. This is how `run_tool` turns the name the model sends into the Python function to run. `ALLOWED_ARGUMENTS` is built from the schemas, so it picks up `path` by itself.
3. **The schema** (`COUNT_WORDS_SCHEMA` in `agent_tool_schemas.py`, added to `TOOL_SCHEMAS`): this is all the model ever knows about the tool. The description tells it *when* to choose this tool over `read_file`.
4. **The tests** (`tests/test_agent_tools.py`): word counting across mixed whitespace, sandbox escapes refused, and a missing file becoming `"Error: ..."` through `run_tool`. The existing schema-contract test checks the new schema against the Python signature automatically.

The system prompt names the tools too, so it got one extra word. Nothing else in `03_agent_loop.py` changed. The loop just sends whatever is in `TOOL_SCHEMAS`.
