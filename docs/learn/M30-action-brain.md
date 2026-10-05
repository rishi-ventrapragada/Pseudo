# M30: Action requests go to Claude Code

## The concept in one paragraph

Until M30, Pseudo had one brain: every question went through `loop.py` to Groq. M29 showed that no free Groq model reliably turns "tick that box" into the right approval popup, and that Claude Sonnet, run through Claude Code, does. M30 gives Pseudo a second brain for that one job. A small **router** reads your message and decides, with plain word rules and no model, whether it is an **action request**. If it is, the message goes to Claude Code, which is itself an agent (a loop that calls tools and then answers), started as a child process for that one request. Everything else stays on Groq. The safety parts didn't move: Claude Code talks to its own copy of `pseudo_hands`, so the redactor, the refusals and the approval popup are the same code as before. Two things had to be added to make a second brain safe: a **billing check** before every launch (who pays, and who sees the data), and an action limit that is shared between processes.

## Web-dev analogy

- **The router** is route matching. `/api/pay` goes to one service and everything else to another, decided by a pattern, not by the service.
- **Claude Code as a child process** is calling a CLI from your server (`ffmpeg`, `git`): you start it, feed it input, read its output line by line, and stop it if it misbehaves.
- **`--output-format stream-json`** is a stream of server-sent events: one JSON object per line, as things happen.
- **The billing check** is checking which credentials a deploy will use before you run it. An environment variable can silently outrank the login you meant.
- **The shared action limit** is rate limiting with more than one server. A counter in each server's memory lets every server allow 4 requests; you need one shared store (here a small locked file, where a web app would use Redis).
- **Fail closed** is a guard that redirects to the login page when the session check itself errors.
- **The badge** is showing "served by: cache" or "served by: origin" in a response header.

## What was built (file by file)

- **`pseudo_brain/routing.py`:** two rules. `offers_focus` (M29's, unchanged) and `is_action_request`.
- **`pseudo_brain/providers.toml`:** `switch_tool` and a new `[action_brain]` table: the program, the model, the three tools it gets, and the *name* of the `.env` variable that holds your account.
- **`pseudo_brain/action_brain.py`:** loads and checks those settings. It refuses a list that gives the action brain the switch tool or a memory tool.
- **`pseudo_brain/claude_billing.py`:** the check before every launch.
- **`pseudo_brain/claude_code.py`:** one request through `claude -p`, reported as the same events the loop reports.
- **`pseudo_brain/chat.py`, `hands.py`:** the routing itself, and `OfferedHands`, a view of the tools with one left out.
- **`pseudo_hands/mcp_server.py`:** `--tools a,b,c` publishes only those tools.
- **`pseudo_hands/core/action_budget.py`:** the 4-popups-per-2-minutes count, now in a locked file.
- **`face/`:** a badge on every answer, the route and billing lines among the steps, the action brain named under the provider, and `foreground.js` letting Claude Code's `pseudo_hands` bring its popup forward.
- **Tests:** `test_brain_routing.py`, `test_brain_claude_billing.py`, `test_brain_claude_code.py` (with `fixtures/fake_claude.py`, a script that only prints lines shaped like Claude Code's), `test_brain_chat_routing.py`, `test_action_budget.py`, and the face's tests.

## Walkthrough of the key code

**1. Is it an action request?** (`routing.py`)
```python
def is_action_request(message: str) -> bool:
    text = message.lower().strip()
    if QUESTION_START.match(text):          # "what...", "which...", "is..." ask; they don't tell
        return False
    found = set(ACTION_WORD.findall(text))  # click, tick, type, choose... as whole words
    if SEE_A_WINDOW.search(text):           # "open the calculator window" is a switch
        found.discard("open the")
    return bool(found)
```
A miss is safe: the message stays on Groq, as before M30. A false hit costs quota, but nothing can act without your popup.

**2. Where a question goes** (`chat.py`)
```python
brain = self.action_brain_for(text)
if brain:
    result = await self.ask_action(brain, text, memories, intro)
else:
    withheld = self.routing.switch_tool if self.routing and not offers_focus(text) else ""
    result = await run_turn(self.session, text, self.model, OfferedHands(hands, withheld), ...)
```
`action_brain_for` returns nothing in private mode (`leaves_laptop` is false), so a private conversation is never sent to the cloud. There is no `except: try Groq instead`: if Claude Code can't be used, the turn fails and says why.

**3. The billing check** (`claude_billing.py`)
```python
login = (status.get("loggedIn"), status.get("authMethod"), status.get("apiProvider"))
yours = str(status.get("email") or "").strip().lower() == account
clean = not found and login == (True, "claude.ai", "firstParty") and yours
```
`found` lists anything Claude Code would use *before* your subscription login: an API key variable, a key helper in its settings, another provider's switch. `account` comes from `.env`; it is compared and never printed. Any error while checking returns "not clean".

**4. Starting Claude Code** (`claude_code.py`)
```python
return [*program, "-p", "--strict-mcp-config", "--mcp-config", str(config), "--tools", "",
        "--allowedTools", *[PREFIX + tool for tool in brain.tools], "--system-prompt", system_prompt,
        "--model", brain.model, "--max-turns", str(MAX_ITERATIONS), "--output-format", "stream-json", ...]
```
- `--strict-mcp-config`: only our `pseudo_hands`, none of your own MCP servers.
- `--tools ""`: none of Claude Code's built-in tools.
- Your question is **not** in this list. It is written to the process's **stdin** (its input pipe), so a message starting with `--` can never be read as an option.

**5. Trust, then verify** (`claude_code.py`)
```python
if set(init.get("tools") or []) != {PREFIX + tool for tool in brain.tools}:
    return "it started with other tools than the ones in providers.toml"
if init.get("apiKeySource") != "none":
    return "it isn't using the subscription login"
```
Claude Code's first line says what it actually started with. If that isn't exactly what was asked for, it is stopped before any tool runs.

**6. One count for every process** (`action_budget.py`)
```python
with open(path, "a+b") as file:
    lock(file)                     # msvcrt.locking: another pseudo_hands waits here
    try:
        return self._take_locked(file, path)
    finally:
        unlock(file)
```
and around it: `except (OSError, ValueError): return self.seconds`, which means "limit reached" when the file can't be used.

## What happens when you run it (annotated real output)

An approved request, from the live check (real face, real popup, a fake window):
```
A choose      ok     | answered by claude-code · claude-sonnet-5-5 | routed to Claude Code True | billing clean True |
tools ['read_active_window', 'act_on_control'] | action popups 1 named right True clicked OK on top True |
s to popup 20.4 | effect as asked True | nothing else changed True
```
- Two tool calls: a fresh read, then the action. No `focus_window`, because Claude Code never gets it.
- `choose` got through. In M28, through Groq, it never did (0 of 6).

A question that stays on Groq:
```
B read-only | answered by groq · openai/gpt-oss-120b | routed to Claude Code False | tools ['read_active_window'] | action popups 0
```

Five cancelled requests in a row, each a separate Claude Code launch with its own `pseudo_hands`:
```
part C: action popups per request [1, 1, 1, 1, 0] | s since the first popup [7.0, 32.0, 56.0, 81.0, 109.0]
```
The fifth was refused by core before any popup. With the old in-memory count, every launch would have started at zero.

Billing not clean (a fake outranking variable set for this one run):
```
D not-clean billing | answered None | tools [] | action popups 0 | face shows 'NOT CLEAN' True |
face shows 'Nothing was sent' True | face names the variable True | form unchanged True
```

Cold against warm, measured before building (M29's 18 held-out questions):
```
cold: usable 18/18 | raw s to popup: median 18.7
warm: usable 18/18 | raw s to popup: median 10.6
warm input tokens in order: [7091, 9580, 12038, ... 46817, 49487]    18th / 1st: 6.98
```
A **warm** session is one Claude Code process kept open for many requests. It is faster, but it keeps every earlier request and screen read in its conversation, so each request costs more than the last. The limit fixed before measuring was 3 times; it measured 7.0. So M30 launches once per request, and M31 will measure a warm session restarted every 6 requests.

**Found by the live check:** after an action request, the face gave the memory popup's bring-to-front permission to Claude Code's `pseudo_hands`, which had already exited. The unit tests didn't catch it, because it only shows with two real processes. It is fixed, with a test.

## Try this (3 small experiments)

1. In a Python shell: `from pseudo_brain.routing import is_action_request`, then try "Tick the box.", "Which box is ticked?", "The box needs to be ticked." and "Check whether the page mentions a deadline." Work out from `routing.py` why the third is a miss and the fourth a false hit.
2. Run `pytest tests/test_action_budget.py -q`. Then, in `action_budget.py`, find the line `return self.seconds  # fail closed: we can't prove there is room` and change it to `return 0.0` and run it again. Read which tests fail and what that change would allow. Undo it.
3. Run `python -m pseudo_brain` with `CLAUDE_CODE_ACCOUNT` set to a wrong address in `.env`, and type "Tick the box." Read the lines it prints: the check fails before anything on screen is read. Then put your address back.

## Check yourself

1. Why does the router use word lists instead of asking a model whether a message is an action request?
2. Claude Code runs its own `pseudo_hands`. Why does the approval popup still protect you?
3. What could go wrong if the billing check ran once at start-up instead of before every launch?
4. Why did the 4-per-2-minutes limit have to move from memory to a file?
5. The warm session was faster and just as accurate. Why wasn't it built?

<details>
<summary>Answers</summary>

1. A rule costs no tokens and no time, gives the same answer every time, and you can read exactly why a message went where it did. A wrong answer is cheap: a miss stays on Groq, and a false hit still can't act without your approval.
2. The popup, the refusals and the redactor live in `pseudo_hands`' core, not in any brain (D11, D13). A second copy of `pseudo_hands` is the same code with the same checks.
3. The login or an environment variable can change while Pseudo runs (in M29 an account switch happened mid-run). A check done once would keep sending screen text under credentials nobody checked.
4. Each Claude Code launch starts a new `pseudo_hands` process, and a count kept in a process's memory starts again at zero. Only something outside the processes can count across them.
5. It missed a criterion fixed before measuring: its 18th request sent 7 times the input of its 1st, against a limit of 3. Changing the limit after seeing the result would make the criteria meaningless, so it becomes its own milestone (M31) with a fresh test set.
</details>

## How this connects to Pseudo's final architecture

ARCHITECTURE.md's picture always had "any brain" above the MCP line. M30 is the first time two brains work in one conversation, and the layers below didn't change to allow it: `pseudo_hands` gained only an option to publish fewer tools and a limit that counts across processes. That is D11 paying off. It is also D11's first exception (D26): `pseudo_brain` now depends on one harness's command line and output format, which is why `claude_code.py` checks what Claude Code actually started with instead of trusting it. The face stays display-only: it shows which brain answered, and decides nothing.
