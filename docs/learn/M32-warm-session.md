# M32: The warm Claude Code session (built)

## The concept in one paragraph

Since M30 every action request has started Claude Code, waited for it and its own `pseudo_hands` to load, got the answer and stopped both. That is a **launch**: about 20 s to the popup. M31 measured the alternative, a **warm session**: one Claude Code kept open, each request written to it, restarted every 6 requests so that what it re-sends can't grow without limit. M32 builds it. Keeping a process open takes three lines. The work is deciding **when**: when a request may use the session, when the session is restarted, when it is stopped so the laptop gets its memory back, and what happens whenever there isn't one. Those decisions are a **policy**, and they live in one file, apart from the **mechanism** that starts and stops the process. Nothing in `pseudo_hands` changed, so the redactor, the refusals, the shared action count and the approval popup work exactly as before.

## Web-dev analogy

- **Launch vs warm session** is a serverless cold start vs a long-lived worker process.
- **Restart after 6 requests** is a worker's `max-requests` setting: recycle it before it bloats.
- **Restart at 3 times the first request's input** is a size watchdog beside that counter: recycle early if this worker is growing faster than usual.
- **Stopped after 10 idle minutes** is scale-to-zero: an idle instance is shut down and the next request pays a cold start.
- **A launch whenever none is open** is the on-demand fallback. The request you are waiting for never queues behind a worker that is still booting; the pool is warmed for the *next* one.
- **One JSON line per request** is NDJSON over a socket. Encoding the question as JSON is the parameterized query of this pipe: the text is data, so it can't be read as an option or as a second request.
- **Off until the face says on** is a server-side default that a client preference overrides on connect. The preference sits in `localStorage`, like "Speak answers".
- **A process remembered by pid and start time** is a row identified by id *and* created-at, because Windows hands a finished process's pid to the next one that starts.

## What was built (file by file)

- **`pseudo_brain/claude_session.py`** (new): the mechanism. `open_session` starts Claude Code with a launch's options plus `--input-format stream-json`; `WarmSession.ask` writes one request and reads until its result line; `stop` closes its input and confirms nothing is left.
- **`pseudo_brain/claude_process.py`** (new): the process tree. `Family` remembers every process a session had and adds up their memory. `stop_tree` and `hands_pid` moved here from `claude_code.py`, which had passed 200 lines.
- **`pseudo_brain/warm_sessions.py`** (new): the policy. Seven rules, each a number M31 measured.
- **`pseudo_brain/bridge_warm.py`** (new): thin, like `bridge_voice.py`. The face's switch in, the session's state out, a tick every 5 s.
- **`pseudo_brain/claude_code.py`**: `ask_claude` is now the billing check plus `launch`, so the rules can check once and then choose. `follow` takes the line reader, so a session keeps one across requests.
- **`pseudo_brain/chat.py`**: an action request goes through the rules when the interface gave it some (the face does, the terminal doesn't).
- **`face/src/useWarm.ts`, `WarmControl.tsx`**: the remembered switch, and one line saying what is running.
- **Tests**: `tests/fixtures/fake_claude.py` gained a warm mode; `test_brain_claude_session.py`, `test_brain_warm_sessions.py`, `test_brain_bridge_warm.py`, `WarmControl.test.tsx`, `message-types.test.mjs`. 48 more Python tests and 15 more face tests.

## Walkthrough of the key code

**1. A session is a launch with one option swapped** (`claude_code.py`):
```python
turns = ["--input-format", "stream-json"] if warm else ["--max-turns", str(MAX_ITERATIONS)]
```
Same tools, same system prompt, same model, nothing saved to disk. `--max-turns` would count across the whole session, so a session leaves it out and `follow()` caps each request at 6 tool calls instead.

**2. One request is one line** (`claude_session.py`):
```python
line = {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": text}]}}
await self.process.stdin.send(json.dumps(line).encode("ascii") + b"\n")
return await follow(self.lines, self.process.pid, self.brain, result, on_event)
```
`json.dumps` escapes quotes and line breaks, so whatever you type stays one line of data. `follow` is the function a launch uses, so every request gets the same checks: exactly the listed tools, no API key, the model asked for.

**3. The decision** (`warm_sessions.py`):
```python
if not self.on:
    return "warm sessions are off"
if self.session is None:
    return "no warm session is open"
if not self.session.alive:
    return "the warm session had ended"
if conversation != self.conversation:
    return "the open session belongs to another conversation"
return "this request brings memories, which never enter a warm session" if memories else ""
```
An empty string means "use the session". Anything else is a launch, and the text becomes a step you can read in the face. A memory belongs to one question (M24); a session's prompt is fixed at its start, so the only other place for a memory would be the request text, where it would stay for five more requests.

**4. The restart rule** is a pure function, so it is tested without any process:
```python
if first_input and last_input >= INPUT_TIMES * first_input:
    return f"this request's input was {last_input / first_input:.2f} times the session's first (limit {INPUT_TIMES:g})"
if asked >= MAX_REQUESTS:
    return f"it has answered {MAX_REQUESTS} requests"
```
The count is M31's result. The 3-times check is M31's own W-T criterion, now checked on every request, because the 6th request reached 2.83.

**5. A request that goes wrong stops the session:**
```python
try:
    result = await self.session.ask(text, on_event)
finally:
    if result is None or not result.ok:
        await self.stop("a request failed inside it", now=True)
```
`finally` also runs when Pseudo is quitting mid-request (`result` is still `None`). The request is never asked again: an action you approved may already have happened.

**6. Only its own processes are ever killed** (`claude_process.py`):
```python
process = psutil.Process(pid)
if process.create_time() == started:
    found.append(process)
```
A session lives for minutes. By then a remembered pid could belong to another program, so the start time has to match too.

## What happens when you run it (annotated real output)

The live check asked 25 real requests through the face, on fake windows. Four of its lines (fields trimmed):
```
A1 toggle cancel | launch (no warm session is open) | billing clean x2 | s to popup 20.1 | tokens in 6731 | session opened
A3 set_text ok   | warm 2 of 6 | billing clean x1 | s to popup 12.3 | tokens in 9311 | 1.32 times the session's first | same Claude Code as the request before True
A7 choose ok     | warm 6 of 6 | billing clean x2 | tokens in 18125 | RESTART: it has answered 6 requests | session opened | 2.57 times the session's first
B5 press         | warm 5 of 6 | tools ['read_active_window', 'act_on_control', 'read_active_window'] | calls 4 tokens in 22151 | RESTART: this request's input was 3.29 times the session's first (limit 3)
```
- **A1, `billing clean x2`:** one check before the request, one before the session's start. The launch answered first; the session opened behind it.
- **A3:** the same process as the request before, and the input has grown to 1.32 times the first. That growth is the history Claude Code re-sends.
- **A7:** the count rule. `x2` again: the new session got its own check.
- **B5:** the request asked to press a link and then say what the status line showed. That needs a second read, so 4 model calls instead of 3, and the input crossed 3 times on the 5th request. This is the case the early rule exists for.

The switch, the shared limit and the face's own line:
```
C1 switched off True: its processes still running 0 (after 1.7 s) | the face says off True and shows no memory True
D paths ['launch', 'warm', 'warm', 'warm', 'warm'] | action popups per request [1, 1, 1, 1, 0] | the 5th asked to act True
G  9 min idle: its processes running 2 | the face says: 'Open: 301 MB · 0 of 6 requests · stopped after 10 idle minutes.'
G  10.5 min idle: its processes running 0 | the face says: 'None open (stopped: idle for 10 minutes). Your next action request starts Claude Code (about 20 s), then one stays open.'
```
- **D:** the fifth popup was refused by core although it came from a different process than the first. The count lives in one small file every `pseudo_hands` shares (M30), so M32 changed nothing there.

The summary: `restarts as the rule says 15/15`, `s to the popup, warm: median 11.3`, `launch: median 17.0`.

**Found by the live check, not by a test.** The first run's first line read `launch (warm sessions are off)` with the switch on. A message from the page passes three lists: `protocol.ts`, `preload.js` and `main.js`. `warm_sessions` was on two of them, and the preload dropped it without a word. `face/message-types.test.mjs` now reads the three files and checks they agree. In that stopped run one launch also read the form and answered without acting; it never happened again and the cause isn't known.

## Try this (3 small experiments)

1. In a Python shell: `from pseudo_brain.warm_sessions import restart_reason`, then try `restart_reason(5, 7000, 20999)`, `restart_reason(5, 7000, 21000)` and `restart_reason(6, 7000, 9000)`. Which two restart, and for which reason?
2. Feed the fake two requests by hand, in PowerShell from the repo:
   `'{"message":{"content":[{"text":"one"}]}}','{"message":{"content":[{"text":"two"}]}}' | .\.venv\Scripts\python.exe tests\fixtures\fake_claude.py -p --allowedTools a --system-prompt b --input-format stream-json`
   One process prints "Fake answer 1" and "Fake answer 2", then ends because its input closed. That ending is how a session is stopped.
3. In `warm_sessions.py` change `MAX_REQUESTS` to 3 and run `pytest tests/test_brain_warm_sessions.py -q`. Read which tests fail and why each one mentions 6. Undo the change.

## Check yourself

1. A request finds no session open. Why is it answered by a launch, instead of starting a session and waiting for it?
2. Why can't a memory be sent into a warm session?
3. A request fails halfway inside a session. Why isn't it sent again as a launch?
4. Why does the brain keep warm sessions off until the face says on?
5. In a session, the previous request's control ids still work. What still stands between a stale id and a wrong action?

<details>
<summary>Answers</summary>

1. Both take about 20 s, but the launch is the path M30 measured, and the session is opened only after the answer. So nothing slows the request you are waiting for, and at most one Claude Code is ever starting.
2. A memory is for one question. A session's system prompt is fixed at its start, so the memory would have to go into the request text, where Claude Code would re-send it with every later request and read it as your words.
3. The action may already have run. Sending the request again could do it twice, so the turn fails visibly and you decide.
4. An open session holds 310 to 440 MB. Off is the default that costs nothing, and it means the terminal, which never says on, keeps a launch per request.
5. Core checks the control again after the popup, and the popup names the control from Windows' own data for you to approve. A fresh read before each action rests on the model (18 of 18 in M31). Enforcing it in core is in the Backlog.
</details>

## How this connects to Pseudo's final architecture

In ARCHITECTURE.md the routing arrow used to end in one `claude -p` per action request. It now forks after the billing check: an open session if the rules allow, else a launch. Everything below the arrow is untouched: Claude Code still gets only the three action-brain tools, and blocked apps, the redactor, the refusals, the shared action count and the popup stay in `pseudo_hands` core (D11, D13). That is why a second way of running the brain needed no change there. The pattern to keep is the split: `claude_session.py` knows how to hold a process, `warm_sessions.py` knows when, and `bridge_warm.py` only carries messages. A future change of policy, say a different restart number, touches one constant and its tests.
