# M4: list_open_windows in the core

## The concept in one paragraph

Windows keeps a list of every **top-level window** on the desktop: each one has a **handle** (a number that identifies it), a **title**, and an owning **process** (the running program). Pseudo's first "eye" walks that list through the **Windows API** (the C functions Windows exposes to programs), keeps only the windows a person would actually see, and returns plain data a model can read. Before anything is returned, a **privacy check** replaces the windows of blocked apps with `"[restricted app]"`. That check lives inside the tool, so it holds no matter which brain or wrapper calls it.

## Web-dev analogy

- `EnumWindows` is like `document.querySelectorAll` over the page's top-level elements. A **handle** is like an element ref.
- **Cloaked** windows are like elements with `display: none`: still in the DOM, invisible to the user. `IsWindowVisible` doesn't catch them, so we check separately.
- The **process name** (`KeePass.exe`) is like a request's origin: it says *who* is really there. The window title is like the page `<title>`: the app can set it to anything. So we decide trust by the origin, never by the title.
- The blocked-apps list is like a server-side deny-list. It's enforced in the backend (the core), never in the UI (the wrapper), so no client can skip it.
- `pywin32` is to the Windows API what the `openai` SDK is to the HTTP API: a friendly wrapper over calls you could make by hand.

## What was built (file by file)

| File | What it does |
|---|---|
| `pseudo_hands/core/windows.py` | Reads all windows from Windows, filters them, applies the mask. The only file that talks to the Windows API. |
| `pseudo_hands/core/blocked_apps.py` | Loads the list and decides what to mask. Fails closed. |
| `pseudo_hands/core/blocked_apps.txt` | Your list of private apps (one `.exe` per line). |
| `pseudo_hands/show_windows.py` | Thin terminal demo. Calls the core, prints, no logic. |
| `tests/test_windows.py` | 11 tests: fake desktops plus one real-API smoke test. |
| `requirements.txt` | Adds `pywin32` (Windows API) and `psutil` (process id → program name). |

New terms: a **package** is a folder of Python files with an `__init__.py` (like a folder with an `index.js`). `python -m pseudo_hands.show_windows` runs a file *as part of its package*, so its imports like `from pseudo_hands.core...` work (like running a script through `npx` from the project root).

## Walkthrough of the key code

**1. Walking the window list** (`read_all_windows`):
```python
def remember(handle: int, _extra: None) -> bool:
    handles.append(handle)
    return True  # True = "keep going, give me the next window"

win32gui.EnumWindows(remember, None)  # calls remember() once per window
```
`EnumWindows` doesn't return a list. It takes a **callback** and calls it once per window, like `array.forEach(fn)`. We collect the handles, then ask about each one: `GetWindowText`, `IsWindowVisible`, `GetWindowThreadProcessId` (which process owns it), and compare with `GetForegroundWindow()` to mark the focused one.

**2. The one raw ctypes call** (`is_cloaked`):
```python
result = ctypes.windll.dwmapi.DwmGetWindowAttribute(
    ctypes.wintypes.HWND(handle), DWMWA_CLOAKED, ctypes.byref(cloaked), ctypes.sizeof(cloaked))
```
`pywin32` doesn't wrap this function, so `ctypes` (built into Python) calls it straight from `dwmapi.dll`. We pass a small integer *by reference* and Windows writes the answer into it. That's how C functions return extra values. Without this, suspended Store apps show up as ghost windows.

**3. Process id → program name** (`app_name`): `psutil.Process(pid).name()` returns `"Code.exe"`. If Windows refuses (an admin-level app) or the process just ended, we return `None`, meaning "unknown".

**4. Filter, then mask** (`list_open_windows`):
```python
blocked = load_blocked_apps()  # first, so a broken list stops us before we read any window
for raw in read_all_windows():
    if not is_user_window(raw):
        continue
    title, app = mask_if_blocked(raw.title, raw.app, blocked)
```
**5. Failing closed** (`blocked_apps.py`): "fail closed" means that when something is uncertain, the safe outcome wins. There are three cases:
```python
return app is None or app.lower() in blocked   # unknown app -> masked
return RESTRICTED, RESTRICTED                  # title AND app name hidden
raise BlockedAppsError(...)                    # no list -> nothing returned at all
```
`focused` is kept even for masked windows, so a model can still say "you're in a restricted app".

**6. Tests that can't leak.** Most tests replace `read_all_windows` with fake data using `monkeypatch`, so they never depend on your desktop. The real-API smoke test asserts only counts and types. If it fails, pytest prints numbers, not your window titles.

## What happens when you run it

Real counts from a run on this machine. **The titles and app names below are placeholders**, because real titles are private and this file is public on GitHub.
```
--- BLOCKED-APPS LIST (pseudo_hands/core/blocked_apps.txt) ---
1password.exe, bitwarden.exe, keepass.exe, keepassxc.exe, signal.exe, telegram.exe, whatsapp.exe

--- ASKING WINDOWS FOR EVERY TOP-LEVEL WINDOW ---
273 windows in total (most are invisible helper windows)      <- tooltips, message-only windows, etc.
7 are visible, not cloaked, and have a title                  <- what you'd see in Alt+Tab, roughly

--- WHAT list_open_windows() RETURNS (what a model would see) ---
 * WindowsTerminal.exe      Windows PowerShell                <- focused: the terminal you ran it from
   Code.exe                 windows.py - Pseudo - VS Code
   chrome.exe               Some page - Google Chrome
   ...
7 windows, 0 masked as '[restricted app]'  (* = focused)

--- THE FIRST TWO AS JSON (the shape the M5 MCP server will send) ---
[ { "title": "Windows PowerShell", "app": "WindowsTerminal.exe", "focused": true }, ... ]
```
It took about 0.01 seconds. The window list is ordered front-most first ("z-order"), which roughly means most recently used first.

## Try this

1. Add `notepad.exe` to `blocked_apps.txt`, open Notepad, and run the demo. Its line becomes `[restricted app]` in both columns. Remove it afterwards.
2. Rename `blocked_apps.txt` for a moment and run the demo. You get `BlockedAppsError` and no windows at all. That's fail-closed. Rename it back.
3. In `is_user_window`, delete `and not window.cloaked` and run the demo. Count the ghost windows that appear (Settings, Text Input Application...). Then undo it and run `pytest` to confirm the tests catch it.

## Check yourself

1. Why is blocking decided by process name and not by window title?
2. Why does an unknown app (`None`) get masked instead of shown?
3. Why does the masking live in `core/` rather than in `show_windows.py` or the future MCP server?
4. Why doesn't `IsWindowVisible` alone give you the windows a person sees?
5. Name one sensitive thing the blocked-apps list *can't* hide, and which phase handles it.

<details>
<summary>Answers</summary>

1. An app can put anything in its title, and a harmless program can have a scary-sounding title. The process name tells you which program it really is. The test `test_the_process_name_decides_not_the_title` shows both directions.
2. D6 says "when unsure, mask". If we can't tell who owns a window, it might be a blocked app, and a wrong guess would leak it.
3. D11: then every caller (demo, MCP server, Hermes, a future brain) gets the check for free, and none of them can forget it or skip it.
4. Windows also reports cloaked windows (such as suspended Store apps) as visible. We need the extra `DwmGetWindowAttribute` check.
5. A website. A bank tab in Chrome is just `chrome.exe`, and its tab title reaches the model. Phase 4's local redactor handles that.

</details>

## How this connects to Pseudo's final architecture

- **M5** wraps `list_open_windows()` in an MCP server without changing a line of `core/`. The demo is already the same shape: call the core, pass the result on.
- **M6** lets Hermes call it to answer "what am I working on right now?". The masking happens before Hermes ever sees the data.
- **Phase 4's redactor** plugs in right next to `mask_if_blocked`, where titles are cleaned, so the non-blocked titles that reach the cloud today get redacted too.
- **Phase 3** (UI Automation, `focus_window`) builds on the same handles and the same `pywin32` foundation.
