# M18: Pseudo's own face

## The concept in one paragraph

Pseudo now has its own window. It's built with **Electron**, which bundles Chromium (the browser engine) and Node.js into one desktop app, and the page inside it is React. The window only displays: every decision stays in `pseudo_brain` and `pseudo_hands` (D11). The face talks to the brain over a **child-process pipe**. It starts `python -m pseudo_brain.bridge` as its child, and the two exchange **JSON lines** (one JSON object per line) on the child's stdin and stdout. Nothing listens on a network port (D18), so no other program and no web page can reach the brain. Three fixes came with the face:
- **The self-read fix:** `read_active_window` skips assistant apps, so it reads the window you were on before you switched to Pseudo.
- **The approval popup:** it opened *behind* the face, because of Windows' foreground rules, so the face now lets only `pseudo_hands` come to the front, right before each tool runs.
- **Private mode:** switching to it now closes the old connection to Groq.

## Web-dev analogy

- **Electron's main process** is a small Node server. The **renderer** (the page) is a browser tab with no Node at all. **preload.js** is the one API route between them, and **IPC** (inter-process communication) is the fetch to that route.
- **JSON lines over a pipe** is like Server-Sent Events, but over `child_process.spawn`'s stdin/stdout instead of HTTP. No port, so there is nothing to `curl`.
- **`app://pseudo/`** serving only `face/dist` is a static host that refuses anything outside `public/`. The CSP `default-src 'self'` is the header you'd set on Vercel.
- **`reduce()` in `state.ts`** is a Redux reducer: (state, message) → new state.
- **Windows' foreground rule** is the browser's popup blocker: `window.open` works only right after a user click, and that "user activation" runs out.
- **The keep-alive socket** is a database connection pool. Switching databases without `pool.end()` leaves the old connections open.

## What was built (file by file)

- **`pseudo_hands/core`:**
  - `assistant_apps.txt` (new): owner-editable list of assistant apps;
  - `active_window.py`: `pick_window()` skips them, and fails closed if the list can't be read.
- **`pseudo_brain`:**
  - `chat.py` (new): one conversation shared by the terminal and the face. `use()` closes the old model.
  - `bridge.py` (new): the protocol.
  - `hands.py`: `find_hands_pid()`. `model.py`: `close()`. `session.py`: `list_sessions()`, `load_session()`.
  - `terminal.py`: now a thin wrapper over `Chat`.
- **`face/`:**
  - `main.js`, `brain-process.js`, `preload.js`, `foreground.js` and `taskbar-flash.js` run in the main process.
  - `src/` holds the page: `App`, `state`, `events`, `Markdown`, `ProviderBar`, `Sessions` and `ApprovalBanner`.
  - `index.html` carries the CSP. `package.json` pins exact versions; koffi 3.3.1 lets JavaScript call a Windows DLL function.
- **Tests:**
  - pytest: `test_assistant_apps`, `test_brain_chat`, `test_brain_bridge` (+ `_sessions`, `bridge_fakes`), `test_brain_hands_pid`, `test_brain_switch_connections`;
  - vitest: events, Markdown, state, banner, foreground and taskbar flash.
- **Docs:** D18, L5, PRD, ARCHITECTURE, both READMEs, and a CLAUDE.md git rule.

## Walkthrough of the key code

**1. The self-read fix** (`active_window.py`). Windows lists windows front-most first, so skipping the assistant leaves the window you were on:
```python
for raw in read_all_windows():  # z-order: front-most first
    if is_user_window(raw) and (raw.app or "").lower() not in assistants:
        return raw
```
Limit: an always-on-top window still counts as "in front". That's why the tests use a normal window.

**2. Starting the brain** (`brain-process.js`). No shell and no port, just a child with two pipes:
```js
spawn(PYTHON, ['-m', 'pseudo_brain.bridge'], { cwd: REPO, stdio: ['pipe', 'pipe', 'inherit'], windowsHide: true });
```
Quitting sends `{"type":"quit"}`. If the bridge is still alive after 8 s, `taskkill /T /F` ends the whole tree. The venv's `python.exe` is a launcher with the real Python as its child, so killing only the launcher would leave the brain running.

**3. The protocol** (`bridge.py`). The face sends `ask`, `provider`, `new_session`, `list_sessions`, `open_session` and `quit`. The brain sends `ready` (including `hands_pid`), `event`, `refused`, `switched`, `session`, `sessions` and `turn_done`. Two rules keep the pipe clean:
```python
protocol = sys.stdout.buffer  # the pipe to the face: from here on, protocol lines only
sys.stdout = sys.stderr  # a print() anywhere now goes to the log, never into the protocol
```
Every line has every key replaced by `<hidden>`, and only one job runs at a time; a second one is refused as `busy`.

**4. An event's journey to the screen.**
- `run_turn` calls `on_event("tool_call", ...)`, and `Bridge.event` writes one JSON line.
- `BrainProcess` splits stdout into lines, and `main.js` hands each one to `grant`, `flash` and the page.
- `preload.js` passes it to the page, whose `reduce()` words it like the terminal (`events.ts`), and React draws it.

**5. The security checklist** (`main.js`):
```js
webPreferences: { preload, contextIsolation: true, sandbox: true, nodeIntegration: false, webSecurity: true }
```
The page can't reach Node, so a bug in it can't read files or start programs. Pages come only from `face/dist` (resolved, and anything outside is refused, as in M3). Navigation, new windows and every permission request are blocked, and IPC is accepted only from `app://pseudo/`.

**6. The approval popup** (`foreground.js`):
```js
if (message.type === 'ready') this.handsPid = isProcessId(message.hands_pid) ? message.hands_pid : null;
else if (message.type === 'event' && message.kind === 'tool_call') this.grant();
```
Windows lets a program bring a window to the front only if it is the program you're using. The face is; `pseudo_hands` isn't. So before each tool runs, the face passes its right to `pseudo_hands` with `AllowSetForegroundWindow`, to that one PID only and never to "any process" (`ASFW_ANY`). Windows withdraws the right at your next input. That's why the first version, which granted on Ask, failed: the Enter key's own key-up came a moment later. The banner and the taskbar flash cover the case where you're in another window.

**7. Closing the old provider** (`chat.py`):
```python
old, self.model = self.model, model
if old is not None and old is not model:
    await old.close()
```

## What happens when you run it (real output, annotated)

Every check below used fake windows, our own face, and output limited to counts and labels (lines shortened).
```
window visible: True | always-on-top: False
   electron.exe (main) -> python.exe -m pseudo_brain.bridge (launcher) -> python.exe -m pseudo_brain.bridge
       -> python.exe -m pseudo_hands.mcp_server (launcher) -> python.exe -m pseudo_hands.mcp_server
listening sockets in the face's process tree: 0 []                       <- D18: no port
V1: 4/4      <- notes behind the Claude app: pick_window still reads our notes
notes then face in front: [True, True] | pick_window reads OUR notes window: True
finished: True after 5.1 s | label: groq · openai/gpt-oss-120b | tools: ['read_active_window'] | says BLUE: True
label: groq · openai/gpt-oss-20b, fallback                               <- V4: a real 429, announced
```
**The popup, before the fix:** it opened behind the face, so the script refused to click it and it timed out as no:
```
[cancel] popup: {"seen": true, "topmost": false, "above_face": false, "hit_test_ok": false}
[A: as today, after input to the face] popup topmost: False | above face: False      <- 2/2, without the face
[B: plus SetWindowPos(HWND_TOPMOST)] popup topmost: False | above face: False         <- the easy fix: refused
```
**After the fix, with a real Enter** (6/6 scored runs; one more attempt crashed in the test script before it could record):
```
[ok] popup: {"seen": true, "topmost": true, "above_face": true, "banner": true, "hit_test_ok": true}
foreground after: the face False | our target True | banner gone after the answer: True
```
**Private mode, before and after closing the old client:**
```
[net] connections outside this laptop: 1 {'python.exe -m pseudo_brain.bridge': 1}     <- an idle socket to Groq
[net] connections outside this laptop (face tree + Ollama): 0 in 95 samples {}
before: {'electron (face)': 4, 'bridge': 2, 'pseudo_hands': 2, 'ollama': 1}   after 1.2 s: all 0   <- quit
```

## Try this

1. **Break the self-read fix.** Put a `#` in front of `electron.exe` in `assistant_apps.txt`, restart the face, and ask "What does my active window say?". It reads its own transcript. Remove the `#` afterwards.
2. **Watch the attention signals.** Ask "Bring the window called Pseudo M15 target to the front" with a fake target window open. Then switch to another window straight away. Because the face is no longer the window you're using, it can't grant: the banner shows, the taskbar button flashes, and the popup may open behind your window.
3. **Speak the protocol yourself.** Run `.\.venv\Scripts\python.exe -m pseudo_brain.bridge` and wait for the `ready` line. Type `{"type":"list_sessions"}`, then `{"type":"delete_everything"}` (refused), then `{"type":"quit"}`.

## Check yourself

1. Why a pipe instead of a small HTTP server on `127.0.0.1`?
2. Why does the bridge point `sys.stdout` at stderr?
3. Why did the popup open behind the face, and why did granting on Ask fail with Enter?
4. Why does the face grant to one PID, and why the inner Python rather than the launcher?
5. Private mode held a connection to Groq although no data went over it. Where did it come from, and why close it?

<details>
<summary>Answers</summary>

1. Any program on the laptop, and any web page through the browser, can connect to a local port. M5 and M17 showed that whatever is reachable gets reached. Only the face holds the pipe's two ends, so only the face can talk to the brain (D18).
2. The pipe must carry only protocol lines. A stray `print()` anywhere in the brain or its libraries would corrupt it, so normal output goes to stderr (the log), and only `write()` uses the real stdout.
3. Windows lets only the program you're using bring a window to the front. `pseudo_hands` started minutes earlier, and your keystrokes went to the face. The right the face passed on was withdrawn at your next input, and the Enter key's key-up is input. Granting at `tool_call` happens milliseconds before the popup.
4. `ASFW_ANY` would let any process jump in front of you while Pseudo works. The inner Python is the one that calls `MessageBoxW`; the launcher shows no windows, so granting to it would do nothing.
5. At startup, the bridge checks Groq's model list (`check()`). The SDK keeps that connection open to reuse it, and the old client was never closed. Private mode promises nothing leaves the laptop, and an open socket to the cloud is exactly what a check should never find.
</details>

## How this connects to Pseudo's final architecture

- **Voice and the overlay** will be new message types on the same bridge, over the same `Chat`; nothing in the brain changes.
- **Click and type tools** (roadmap 8) go through the same popup, and the face already grants before every tool call.
- **Packaging** adds `Pseudo.exe` to `assistant_apps.txt`.
- **Next: the redactor's over-masking** (Backlog, high priority). It showed up in every run: "Pseudo M15 notes" became "Pseudo [PERSON] notes", and V6 had to name the target by what the model could see.
