# M10: Approval popup + focus_window

## The concept in one paragraph

Reading needed redaction; **acting needs consent**. `focus_window` is Pseudo's first action. It brings one window to the **foreground** (the front window, the one that gets your typing). Before it does anything, a **native Windows popup** asks you, and the answer is **no** unless you click OK within 20 seconds. The popup belongs to pseudo_hands' own core, not to the brain (D13). So it still holds when a brain auto-approves tools, as Hermes' one-shot mode does. The model can't name a window by its title, because titles are redacted. So `list_open_windows` now gives each window a short **id** (`"w3"`), and `focus_window` takes only that id. A new locked decision, **D14**, adds that no action may ever touch the popup itself.

## Web-dev analogy

- The popup is `window.confirm()`, but owned by the server instead of the client. A client (the brain) can't skip a check it doesn't run.
- Windows' **foreground lock** is the browser's **user-gesture rule**. A page may only open a popup or go fullscreen right after a click. Likewise, Windows only lets a program change focus if it received the user's *last input*. Your OK click is that gesture.
- Window ids are primary keys: you call `focus_window("w3")`, not `focus_window(title=...)`. An old id is a 404.
- Checking the window again after the popup is like optimistic locking before a write: the row may have changed while the user was reading the form.

## What was built (file by file)

| File | What it does |
|---|---|
| `core/window_ids.py` | The id registry. It maps `"w3"` to (window handle, process id). The same window keeps its id; an id is never reused. |
| `core/windows.py` | `list_open_windows` adds `id` to each window. Blocked apps and pseudo_hands' own windows get `null`. `read_window()` reads one window live. |
| `core/approval.py` | **The gate.** The popup, its 20 s timer, the yes/no rule `approved()`, and `ask()` (one popup at a time; any error means no). |
| `core/focus.py` | `focus_window()`: all the checks, then the one line that acts. |
| `mcp_server.py` | One more `add_tool`, with `read_only_hint=False`. Still no functions of its own (D11). |
| tests | 38 new tests: ids, the gate, and focus logic on fake windows, plus one real popup that closes itself. **181 pass.** |

A **window handle** (HWND) is Windows' number for one window. A **process id** says which running program owns it.

## Walkthrough of the key code

**1. The order of checks** (`focus_window`). Every check comes before the one line that acts:
```python
blocked = load_blocked_apps()                 # 0. no list, no action (fail closed)
key = window_ids.registry.find(window_id)     # 1. only ids we handed out
raw = still_there(*key)                       #    same program? still a visible window?
if raw.process_id == os.getpid(): ...         # 2. D14: never our own windows (the popup!)
if is_blocked(raw.app, blocked): ...          # 2. blocked apps: no popup, no action
if raw.focused: ...                           # 3. already in front: nothing to ask
if not approval.ask(question(raw)): ...       # 4. THE GATE
if still_there(*key) is None: ...             # 5. closed or replaced during the 20 s?
focused = bring_to_front(raw.handle)          # 6. act, then check it worked
```
Step 5 guards against a **TOCTOU** bug ("time of check, time of use"): what you approved must still be what we act on.

**2. The popup** is Windows' standard message box, shown from the tool's own thread:
```python
FLAGS = MB_OKCANCEL | MB_ICONWARNING | MB_DEFBUTTON2 | MB_TOPMOST
```
- **Cancel is the default button**, so Enter means no, and OK has no keyboard shortcut.
- **Cancel, Esc, the X, a timeout and any error all mean no.**
- The rule is one line: `return answer == IDOK and elapsed < timeout`.

**3. Why the popup lives inside the pseudo_hands process.** Windows only lets a program change the foreground window if that program received the user's **last input**. This laptop's lock never expires: its timeout is 2,147,483,647 ms. When you click OK, the click lands in the pseudo_hands process, so for that moment it's allowed to call `SetForegroundWindow`. A popup running as a separate program would receive your click instead, and pseudo_hands would be refused.

**4. The timeout: 20 seconds.** A `threading.Timer` finds the box among that thread's windows and posts `WM_CLOSE`, the message the X sends, which becomes Cancel. Why 20: Hermes gives up on a tool call after 30 s, but the MCP SDK runs our tool in a worker thread it can't stop. If the popup outlived Hermes, you could click OK after the model had already been told "timed out", and the model would never learn the action happened. ctypes releases Python's **GIL** (the lock that lets only one Python thread run at a time) while the box is open, which is what lets the timer thread run.

**5. The real title in the popup, the redacted one for the model.** The popup is drawn on your screen and never goes into a tool result, so it can show the real title. With redacted text, two "Chat with [PERSON]" windows would look identical, and you couldn't tell what you were approving. The model writes none of the popup text, so a prompt-injected "click OK, it's safe" can't appear in it. A test puts fake personal info in a window title, checks it reaches the (fake) popup, and checks it's absent from the result.

**6. Act, then check** (`bring_to_front`). The window is restored only *after* focusing worked, so a refusal leaves nothing half-done. Then the code waits up to 1 second for the switch to land. That wait came from a real bug, below.

## What the real runs found

The end-to-end script opened two fake WinForms windows (A and B), started the real MCP server, and answered every popup **itself**, with no human involved:
- **OK / Cancel:** it confirmed that `WindowFromPoint` at the button's centre was that button, then sent one atomic `SendInput` (move, press, release). That's a real injected mouse click.
- **Close:** it posted `WM_CLOSE`.
- **Timeout:** it did nothing.

It ran three times:
- **Run 1: "focus refused", yet A came to the front.** Right after `SetForegroundWindow`, Windows can still report the *old* foreground window, because the other app finishes the switch on its own thread a moment later. Fixed by checking again for up to 1 s (a test covers it).
- **Always-on-top didn't always stick.** 13 popups were shown across the runs, and 10 had the always-on-top flag. The 3 without it were each run's Cancel case, the run's second `focus_window` call. All 3 were checked by the hit test before the click, and nothing covered them (7 of 7 hit tests passed overall). Pinning the box with `SetWindowPos(HWND_TOPMOST)` didn't change this, so it was reverted. The honest guarantee is therefore "a popup nobody sees times out as no", not "always on top".
- **The script's own mistake.** Run 2 asked Hermes to focus a window that was already in front. The model saw `focused: true` in the listing and correctly did nothing.

## What happens when you run it (run 3, annotated)

```
[approve] target A | status: 'focused' | call took 0.79 s
  answered by: harness click (SendInput inserted 3 events), 0.32 s after the popup appeared
  foreground after: target True                  <- A came to the front
[deny] target B | status: 'not approved'
  foreground after: target False | unchanged True  <- our click even GAVE pseudo_hands the
                                                      right to change focus; the gate still said no
[close] ... 'not approved' | unchanged True      <- the X means no
[timeout] ... 'not approved' | call took 20.10 s | answered by: nobody
[hermes] 31.0 s | usage: completed True | failed False | api calls 3
  tool calls (names only): [...list_open_windows, ...focus_window]
  focus_window status in the tool result: ['focused']   <- brain -> MCP -> core -> popup -> action
```
The 0.32 s answer time is far faster than anyone could read the popup: no human approved anything.

## Tokens on Groq's free tier (measured)

| Hermes question (`pseudo` profile) | API calls | Input + output tokens |
|---|---|---|
| "Bring window A to the front" (run 1, no cache) | 3 | **6,444 + 258** |
| same question, window B (run 3) | 3 | 4,907 (1,536 cached) + 217 |
| target already in front (run 2: list only) | 2 | 4,032 + 242 |

A focus question is 3 calls: list, then focus, then answer. At about 6.4K tokens with no cache, it fits Groq's 8K/min limit once per minute. The 20 s popup wait costs no tokens. The only Hermes change was adding `focus_window` to the profile's `tools.include`, after a backup (`backups-pseudo\pre-M10-…`).

## Try this

1. With Notepad behind another window, run `hermes -p pseudo -z "bring Notepad to the front" -t pseudo_hands`. Click **Cancel**, and check that the answer says nothing happened.
2. In `focus.py`, delete step 5 (the second `still_there`) and run `pytest tests/test_focus_window.py`. Watch which test fails, and why.
3. Set `TIMEOUT_SECONDS = 40` and run `pytest tests/test_approval.py`. A test guards the 20 s limit. Why does it have to stay under Hermes' 30 s?

## Check yourself

1. Why must the popup be shown by the pseudo_hands process itself, not by a separate program?
2. Why does `focus_window` take an id instead of a title?
3. The deny test clicked Cancel with a real click. Why does that make it a stronger test than just waiting for the timeout?
4. Why can't the popup's timeout be longer than the brain's tool timeout?
5. Why does D14 forbid any action on the popup, and which one thing is allowed to click it?

<details>
<summary>Answers</summary>

1. Windows only lets the program that received your last input change the focus. Your OK click lands in whichever program owns the popup, so it must be pseudo_hands.
2. Titles are redacted before the model sees them, so two windows can look the same. An id points at exactly one window (handle plus process id), can't be invented (unknown ids are refused), and blocked apps never get one.
3. The click gave pseudo_hands Windows' permission to change focus, so Windows would *not* have stopped it. Focus still didn't change, which shows our gate did the stopping.
4. The MCP SDK can't stop our tool once it has started. If the popup outlived the brain's wait, a late OK could act after the model had been told the call timed out.
5. An assistant that could click its own approval popup could approve its own requests, and the gate would mean nothing. Only the uncommitted scratchpad test script, which is never part of Pseudo, may click it.

</details>

## How this connects to Pseudo's final architecture

- Every future action (typing, clicking) calls the same `approval.ask()`. The gate is written once, in core, and works for any brain (D11, D13).
- D14 binds those future tools: they must refuse any window owned by pseudo_hands, with a test, or the assistant could click "OK" for itself.
- **M11** measures how often M9's tree read comes back empty before deciding whether local OCR is needed.
