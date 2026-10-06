# P8-fix: focus_window refuses assistant apps

## The concept in one paragraph

A safety rule only protects you if **every** tool that could break it checks it. Pseudo has a rule that it never reads or acts on its own window. The rule is a list, `assistant_apps.txt`: the programs you talk to Pseudo (or another AI) through. Reading skipped them since M18, and clicking and typing refused them since M28. But `focus_window`, the oldest action tool (M10), was written before the list existed and never learned about it. So Pseudo's own face got a window id, and a model could ask to bring the face to the front. This fix makes the list **one rule read in one place**, and has all four tools use it.

## Web-dev analogy

- **It's an authorization check missing from one route.** `/read` and `/act` checked "is this the admin's own page?", but the older `/focus` route never got the check. Nobody attacked it; it was found by reading the code.
- **The fix is shared middleware.** Instead of each route parsing the list itself, one module owns the rule and every route calls it.
- **A circular import is the same problem as in JavaScript.** If `a.js` imports `b.js` and `b.js` imports `a.js`, one of them sees a half-loaded module. The cure is the same too: move the shared piece into a third file both can import.
- **No id is like not rendering the button.** The server still refuses the request if someone sends it anyway. Pseudo does both.

## What was built (file by file)

- **`pseudo_hands/core/assistant_apps.py` (new):** the list's loader, its error, and `is_assistant()`. Moved out of `active_window.py`.
- **`pseudo_hands/core/windows.py`:** `list_open_windows` still lists an assistant app's window, but gives it no id.
- **`pseudo_hands/core/focus.py`:** `focus_window` refuses an assistant app before any popup, and refuses everything if the list can't be read.
- **`pseudo_hands/core/active_window.py`, `act.py`:** unchanged rules, now importing from the new file.
- **`pseudo_hands/core/assistant_apps.txt`:** its comment says what the list now does.
- **Tests:** 5 new ones in `test_focus_window.py` and `test_window_ids.py`. Three older tests moved, unchanged, to `test_focus_bring_to_front.py`, because the file passed 200 lines.

## Walkthrough of the key code

**1. One question, asked the same way everywhere** (`assistant_apps.py`):
```python
def is_assistant(app: str | None, assistants: set[str]) -> bool:
    return (app or "").lower() in assistants
```
A program is judged by its **process name** (`electron.exe`), never by its window title, the same reason as blocked apps in M4: a title is whatever the app chooses to show.

**2. No id** (`windows.py`):
```python
def may_get_id(raw: RawWindow, assistants: set[str] | None) -> bool:
    return raw.process_id != os.getpid() and assistants is not None and not is_assistant(raw.app, assistants)
```
- Three reasons for "no": it's `pseudo_hands`' own window (D14), the list couldn't be read (`None`), or the program is on the list.
- `assistants is not None` is the **fail closed** part. Without the list, Pseudo can't tell the face from your window, so nothing gets an id.

**3. The refusal** (`focus.py`):
```python
if is_assistant(raw.app, assistants):  # 2. (P8-fix) never the face, or another assistant
    return result(window_id, ASSISTANT_APP)
```
This runs before `approval.ask`, so no popup is ever shown for it.

**Why check twice?** Ids are handed out by one call and used by a later one. In between, the list can change. `list_open_windows` withholding the id covers the normal case; `focus_window` checking again covers an id that was handed out earlier. The same pattern protects blocked apps since M10.

## What happens when you run it (real output, annotated)

Two fake windows, core called directly, no model. The stand-in plays the assistant app; a temporary list names its program.
```
stand-in's program: pythonw.exe | form's program: python.exe
A. before the stand-in is on the list (how every assistant window was treated before the fix)
  PASS  the stand-in gets an id while it is not on the list
B. the stand-in's program goes on the (temporary) assistant list
  PASS  focus_window on the stand-in's old id is refused | status: assistant app
  PASS  no popup was asked for | popups: 0
  PASS  focus unchanged (still the form)
   windows listed: 6 | with an id: 5
  PASS  the stand-in is still listed
  PASS  the stand-in has no id
C. an ordinary window still focuses after OK (this script's own test popup)
  PASS  focus_window on the form: focused | status: focused
  PASS  exactly one popup, in the always-on-top layer | popups: 1, on top: [True]
D. the assistant list can't be read
  PASS  windows are still listed, none with an id | listed: 6, with an id: 0
  PASS  focus_window is refused, no popup
RESULT: 15 of 15 checks passed
```
- **Part B** is the second check at work: the id was real, and it was still refused.
- **"listed: 6, with an id: 5":** the one window without an id is the stand-in.
- **Part D:** every window is still listed, so a question like "what's open?" still works; only pointing at a window stops.

## Try this

1. In `focus.py`, delete the two `is_assistant` lines and run `.\.venv\Scripts\python.exe -m pytest tests/test_focus_window.py`. Which tests fail? Put the lines back.
2. Add `notepad.exe` to `assistant_apps.txt`, then run `.\.venv\Scripts\python.exe -m pseudo_hands.show_windows` with Notepad open. What changed for Notepad? Remove the line again.
3. In `assistant_apps.py`, move `load_assistant_apps` back into `active_window.py` and import it from `windows.py`. Run any test. What does Python say, and why?

## Check yourself

1. Reading and clicking already refused the face. How could `focus_window` still reach it?
2. Why does `list_open_windows` still list an assistant app instead of hiding it?
3. `list_open_windows` gives the face no id. Why does `focus_window` check the list again?
4. What happens to window ids if `assistant_apps.txt` is deleted, and why is that the right direction?
5. After this fix, what does "switch to Claude" do?

<details>
<summary>Answers</summary>

1. `focus_window` was written in M10, before the list existed (M18). It only refused `pseudo_hands`' own windows, by process id. The face is a different process (`electron.exe`), so it passed.
2. The list of windows is information, and "Pseudo is open" isn't a secret. Hiding it would also make the count of windows wrong. What matters is that nothing can be pointed at it.
3. An id can outlive the list it was checked against: a program can be added to the list after its window got an id. The check next to the action is the one that counts (D11).
4. No window gets an id, and `focus_window` refuses everything. Without the list Pseudo can't tell its own face from your window, so it does nothing rather than guess (fail closed).
5. It's refused with "assistant app" and no popup, because `claude.exe` is on the same list. You switch to it yourself.
</details>

## How this connects to Pseudo's final architecture

- **Phase 9 depends on it.** A global hotkey and an always-on-top bar put Pseudo's own window in front far more often. The rule had to hold for every tool before that.
- **The check lives in core (D11).** `pseudo_brain`, Claude Code's own `pseudo_hands` and any future brain get it without knowing it exists.
- **`Pseudo.exe` needs one line.** When the face is packaged (M34), adding its name to `assistant_apps.txt` covers reading, listing, focusing and acting at once.
