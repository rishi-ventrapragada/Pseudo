# M14: pseudo_brain, Pseudo's own loop

## The concept in one paragraph

M13 ruled Hermes out, so M14 gives Pseudo **its own brain**, grown from the M3 loop. It's still the same agent loop: send the history plus the tools, run the tools the model asks for, repeat until it answers in plain text, and stop at a hard cap. What's new is that it is an **MCP client**: it starts `pseudo_hands` over stdio (as Hermes did) and **discovers** its tools at startup instead of importing them. It is **async**, because the MCP client and the model client are, and it **never prints**. Every step becomes an **event** that an interface shows: the terminal now, the React face in M15. It keeps a **session** that is trimmed to Groq's budget and saved without any screen content. It is also honest: a failure is never shown as an answer.

## Web-dev analogy

- The **MCP client** is `fetch` to a local API whose contract it learns at runtime: `list_tools()` is like reading an OpenAPI spec at startup, so the brain never hardcodes the endpoints.
- **Events** are an `onProgress` prop. `run_turn` is a component with no JSX: it calls `on_event(kind, data)`, and whoever renders it (the terminal, or React in M15) decides what that looks like.
- **Trimming** is cache eviction: the oldest whole conversation turns are evicted first to stay under the per-minute token quota.
- **async/await** is exactly JavaScript's: one **event loop** runs many waiting things (the model call, the MCP connection). `input()` would freeze that loop, so it runs in a helper thread (`anyio.to_thread`), like moving work into a Web Worker.

## What was built (file by file)

| File | What it does |
|---|---|
| `pseudo_brain/model.py` | Groq through `AsyncOpenAI` (`max_retries=0`). `call_model()` waits out 429s visibly; every other failure becomes a `ModelFailure` with a plain reason. |
| `pseudo_brain/hands.py` | The MCP client: starts `pseudo_hands` over stdio, lists its tools, converts them to the OpenAI format, and calls them. No tool is named anywhere in `pseudo_brain`; a test checks this. |
| `pseudo_brain/session.py` | History as whole turns; `messages_for_request()` trims to ~3,000 estimated tokens; `save()` keeps only your messages and the final answers. |
| `pseudo_brain/loop.py` | `SYSTEM_PROMPT` and `run_turn()`: THE LOOP. It returns a `TurnResult`, where `ok=False` always means there is no answer. |
| `pseudo_brain/terminal.py` | The only file that prints. It turns events into `--- SENDING TO MODEL ---` style lines, and handles `--continue`, `/new` and `/quit`. |
| tests | 21 new tests with a **fake model** and an in-memory **fake MCP server**. **226 pass.** |

## Walkthrough of the key code

**1. Tools are discovered, not imported** (`hands.py`):
```python
async with Client(target if target is not None else pseudo_hands_process()) as client:
    tools = (await client.list_tools()).tools
    yield Hands(client, tools)
```
Add a tool to `pseudo_hands` and the brain gets it on the next start, with no change in `pseudo_brain`.

**2. The loop never prints** (`loop.py`):
```python
on_event("tool_call", {"name": name, "arguments": arguments})
text, is_error = await hands.call(name, arguments)
session.add({"role": "tool", "tool_call_id": tool_call.id, "content": text})  # memory only
on_event("tool_result", {"name": name, "chars": len(text), "is_error": is_error})
```
Events carry the **size** of a tool result, never its text. The text goes to the model and stays in memory.

**3. Honest rate limits** (`model.py`). The wait is announced *before* it happens, and giving up is a failure, not an answer:
```python
on_event("rate_limited", {"seconds": delay, "wait": waits, "of": MAX_RATE_LIMIT_WAITS})
await wait(delay)
...
raise ModelFailure(f"Groq is still rate limiting (429) after {waits - 1} wait(s) ...")
```

**4. Trimming by whole turns** (`session.py`):
```python
if estimate <= MAX_PROMPT_TOKENS or len(kept) <= 1:
    break
kept.pop(0)  # the oldest whole turn
```
Dropping single messages could leave a tool result without the call that asked for it, and the API would reject that. Trimming only shapes one request; the history itself keeps everything.

**5. What is sent unredacted (L8).** What *you type* goes to Groq exactly as typed, by design: redacting it would break tasks that need the real values, such as a name to search for. Only **screen content** is redacted, inside `pseudo_hands` core (D6).

## M3 loop vs pseudo_brain

| | M3 loop (`playground/03_agent_loop.py`) | pseudo_brain |
|---|---|---|
| Tools | 4 Python functions, imported | discovered from `pseudo_hands` over MCP |
| Approval | terminal y/n inside `write_file` | native popup shown by `pseudo_hands` (D13) |
| Style | synchronous | async (event loop) |
| History | one task, then exit | multi-turn session, trimmed, saved, `--continue` |
| Output | `print` inside the loop | events → any interface |
| 429 | wait for retry-after, then stop | the same, plus `TurnResult(ok=False)`, never an answer |
| Cap | 10 model calls | 6 model calls per question |
| Prompt | a file assistant | Pseudo, plus how to treat `[PERSON]`-style masks (99 tokens) |

## What happens when you run it (real output, fake windows only)

**V2: "What does my active window say?"**, about our fake window:
```
--- CONNECTED: 3 tools discovered: list_open_windows, read_active_window, focus_window ---
--- SENDING TO MODEL (call 1 of max 6) | 2 messages + 3 tools, ~545 tokens ---
tokens: 480 in / 50 out (estimated ~545 in) | Groq budget left this minute: 6944 of 8000
--- MODEL WANTS TO CALL TOOL: read_active_window {"":{}} ---      <- odd arguments; pseudo_hands ignores them
--- TOOL RESULT: 402 chars, sent to the model, kept in memory only ---
--- ANSWER (2 model call(s), 1102 tokens in / 220 out) ---
pseudo> ... Meeting with **[PERSON]** in **[LOCATION]** ... Call **[IN_PHONE]** ...
```

| Same question | Input tokens |
|---|---|
| Hermes `pseudo` profile (M9, untuned) | 6,109 |
| Hermes `pseudo` profile (M9, tuned) | 3,644 |
| **pseudo_brain (M14)** | **1,102** (480 + 622) |

The system prompt costs 99 tokens and Groq's chat format 76; the three discovered tool schemas are about 290.

**V3: the approval popup, from the `pseudo_hands` child process:**
```
deny run:    popup seen, owned by our pseudo_hands: True, clicked Cancel -> status 'not approved', foreground unchanged
approve run: popup seen, owned by our pseudo_hands: True, clicked OK     -> status 'focused', target now in front
```

**V5: the terminal, then `--continue`:**
```
--- SESSION 20260928-223936: 1 earlier turn(s) loaded ---
pseudo> You asked me to tell you, in one sentence, what your active window says.
--- SESSION SAVED: ...\Pseudo\sessions\20260928-223936.json (your messages and final answers only) ---
```
The saved file holds `user` / `assistant` entries with `role` and `content`, and no tool calls or results.

**What the real runs taught us:**
- **No real 429.** At about 1,100 tokens per question, Groq's budget refilled faster than 5 back-to-back questions could spend it (the lowest it fell was 2,200 of 8,000). Hermes hit 429s at 3,600–6,100 per question. The 429 paths are proven by the fake-429 tests.
- **Answers from history.** Asked the same question 5 times in one session, the model re-read the window only once and answered the rest from history. That's cheap, but it could be stale if the screen changed. It's a candidate for the Backlog.
- **Style.** The model used Markdown bold although the prompt says plain text.
- **Terminal noise.** `pseudo_hands` prints Presidio's startup messages to stderr (222 lines, no screen text). Quieting them would be a `pseudo_hands` change.

## Try this

1. Run `python -m pseudo_brain`, ask something, type `/quit`, then run `python -m pseudo_brain --continue` and ask "what did I ask before?".
2. In `session.py`, set `MAX_PROMPT_TOKENS = 700` and ask three questions: watch `dropped N old turn(s) to fit`.
3. In `model.py`, set `MAX_RATE_LIMIT_WAITS = 0` and run `pytest tests/test_brain_loop.py`. Which test fails, and what does it protect?

## Check yourself

1. Why is `pseudo_brain` async, and why does `input()` run in a helper thread?
2. Why does `loop.py` never print, and what does that give M15?
3. Why does trimming drop whole turns, never single messages?
4. What guarantees that a failed model call never looks like an answer?
5. Why is what you type sent unredacted while screen content is not?

<details>
<summary>Answers</summary>

1. The MCP client and `AsyncOpenAI` are async: they run on one event loop that must keep turning. A blocking `input()` would freeze it, including the MCP connection to `pseudo_hands`, so it runs in a thread and the loop keeps going.
2. It reports events instead, so any interface can render them. M15's React face will pass its own `on_event` to the same `run_turn`, with no change to the loop. A test fails if `print` appears in the loop's modules.
3. A turn's messages belong together: the assistant's tool call, then the tool result. Dropping one without the other gives the API an orphaned tool result, which it rejects. Whole turns always form a valid conversation.
4. Every failure goes through `fail()`, which returns `TurnResult(ok=False, answer=None)` and sends a `failed` event. The terminal prints `FAILED: ... No answer was produced.`, and no fake assistant message is added to history.
5. L8: typed text is yours and often needs its real values; a redacted "call [PERSON]" couldn't find the person. Screen content can include anything, like other people's names, numbers and chats, so it's redacted in `pseudo_hands` core before it leaves the laptop (D6).
</details>

## How this connects to Pseudo's final architecture

`pseudo_brain` is now the **brain** in the diagram (D15). `pseudo_hands` didn't change at all, because every privacy rule and the approval popup already lived in its core (D11). **M15** adds a React window that talks to `pseudo_brain` through a local server and passes its own `on_event`, so the same loop, events and honesty rules show up in a real UI. After that, the roadmap adds memory (L6), then voice, then click and type, each one a new tool in `pseudo_hands` that the brain discovers on its own.
