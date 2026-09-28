# M12: Harden the readers

## The concept in one paragraph

M11 went looking for windows that need OCR and found reader bugs instead. M12 fixes exactly those three, each with a robustness rule worth remembering:
1. **A partial failure shouldn't become a total failure.** One control that can't answer is now skipped, not allowed to throw away the whole read.
2. **Some providers are lazy and need a second knock.** A first read that fails or finds nothing gets one retry after a short wait.
3. **Not everything that looks like a window is one.** Invisible and click-through overlays are no longer listed.

New terms:
- A **COMError** is how UI Automation (a COM interface) reports failure.
- Its **HRESULT** is Windows' numeric error code; `0x80040201` means "element not available".
- A window's **extended style** is a set of on/off bits (`WS_EX_...`) describing how it behaves.

## Web-dev analogy

- `Promise.all` rejects if *one* promise rejects; `Promise.allSettled` keeps the rest. M9's walk was `Promise.all` over controls. M12 made it `allSettled`, and it counts the rejections.
- The retry is the classic **serverless cold start**: the first request to a sleeping function can fail, and one retry after a moment usually works.
- Overlays are like a full-screen `<div style="pointer-events: none">` with `aria-hidden`. It's in the DOM and on top of everything, but it isn't content, and you'd never tab to it.

## What was built (file by file)

| File | Change |
|---|---|
| `core/ui_tree.py` | New `walk(root)`: the loop, with one `try` per control. `TreeRead` gains `skipped`. `read_tree(handle)` just sets up COM and calls `walk`. |
| `core/active_window.py` | `attempt()`, `read_with_retry()`, `success_note()`. `read_window` retries once and reports what happened in `note`. |
| `core/windows.py` | `is_overlay_style()`, plus `RawWindow.overlay`. `is_user_window()` now drops overlays. |
| `requirements.txt` | Pins `comtypes==1.4.17`. It was already installed with uiautomation, but ui_tree now imports its `COMError` directly. |
| tests | New `test_ui_tree.py` (9, on fake control trees), 6 in `test_active_window.py`, 9 in `test_windows.py`. **205 pass**, 1 expected failure. |

## Walkthrough of the key code

**1. One `try` per control** (`ui_tree.walk`):
```python
try:  # every question we ask this one control, together
    if depth > 0 and control.IsOffscreen: continue
    kind = control.ControlTypeName.removesuffix("Control")
    text = control_line(control, kind)
    children = control.GetChildren() if depth < MAX_DEPTH else []
    ...
except COMError:  # it vanished or won't answer: skip it and everything inside it, like off-screen
    skipped += 1
    continue
if text:
    lines.append(TreeLine(depth, kind, text))  # only after EVERY call for this control worked
```
Three decisions here:
- **Everything inside a failing control is skipped too.** A vanished element's children are usually gone as well, and "skip the subtree" is the rule we already had for off-screen controls.
- **The line is added only after the whole `try` succeeds.** A control whose name was read but whose children failed is dropped whole. Nothing half-read is kept.
- **Only `COMError` is caught.** A bug in *our* code (say, a `ValueError`) still crashes loudly, so a test notices it. A test with a deliberately buggy control proves that.

**Privacy check:** if a password box's `IsPassword` question itself fails, the control is skipped, so its value is never read. The test's fake control fails the test if `GetPattern` (reading the value) is ever called.

**2. Why `walk(root)` became its own function.** `read_tree(handle)` needs a real window and COM. `walk(root)` takes *any* object that answers `Name`, `ControlTypeName`, `GetChildren()` and the rest. So `tests/test_ui_tree.py` builds fake trees from a small `FakeControl` class, and one fake raises the real `COMError(0x80040201)`. It's the same idea as passing a mock `fetch` into a function instead of letting it call the network.

**3. The retry** (`active_window.read_with_retry`):
```python
tree, error = attempt(handle)
if tree is not None and any(line.depth > 0 for line in tree.lines):
    return tree, error, False                  # something inside the window: done
time.sleep(RETRY_WAIT_SECONDS)                 # 1.0 s for a lazy app to build its tree
tree, error = attempt(handle)
return tree, error, True
```
It runs **after** the blocked-apps check, so a blocked app is still never read, not even once. The `note` now tells the model what happened, using fixed words and numbers only:
- `read on the second try`
- `1 control skipped (read errors)`
- `read failed (COMError)`: the error's type only, never its message

**4. The overlay rule** (`windows.is_overlay_style`):
```python
never_active_tool = ex_style & win32con.WS_EX_TOOLWINDOW and ex_style & win32con.WS_EX_NOACTIVATE
return bool(ex_style & win32con.WS_EX_TRANSPARENT or never_active_tool)
```
`&` tests one bit (like `flags & READ` in a permissions mask). `LAYERED` alone isn't an overlay, because Electron apps like Claude and VS Code are layered too. The rule lives in `is_user_window()`, which three tools already share, so **one line fixed all three**:
- `list_open_windows`: overlays aren't listed and get no id
- `read_active_window`: an overlay is never picked as "the active window"
- `focus_window`: an overlay can never be focused

## What happens when you run it (real re-verification, counts only)

The same counts-only method as M11: the unchanged M11 script, then the production path and MCP.

| App | M11 (M9 code) | M12 |
|---|---|---|
| claude.exe | **read failed on every read** (`0x80040201`) | 30 controls, 239 chars below the window line, note `1 control skipped (read errors)` |
| Obsidian, fresh launch, first read | **COMError** | 14 controls, 95 chars, note `1 control skipped (read errors)`, 920 ms |
| Brave / VS Code | the first read failed | readable (1,111 and 449 chars) |
| Overlays (cua-driver, NVIDIA) | listed, with focus ids | 2 still on the desktop; **0 listed, 0 ids** |

Through the real MCP server over stdio, `list_open_windows` returned 6 windows with no overlay apps, and `read_active_window` read Brave (200 controls, 1,111 chars).

What the real runs taught us:
- **The skip, not the retry, fixed Obsidian's cold start.** Its cold failure was also a single control. With it skipped, the first read already has content, so the retry never fired. The retry remains for reads that fail at the window itself or come back empty; unit tests cover that, but the real desktop didn't show it this time.
- **Cold reads are thinner.** Obsidian's first read found 14 controls and 65 content chars; M11's warm read found 47 and 290. The retry rule ("nothing inside the window") doesn't catch *thin*. That's a possible future tweak, not changed here.
- **Depth matters for Electron apps.** claude.exe gives 30 controls at M9's depth limit of 12, but a depth of 30 finds 109. Electron nests deeply. Not changed here either (not in scope).

## Try this

1. In `ui_tree.walk`, change `except COMError:` to `except ValueError:` and run `pytest tests/test_ui_tree.py`. Which tests fail, and what does each one protect?
2. Make `is_overlay_style` always return `False` and run `pytest tests/test_windows.py tests/test_active_window.py`. Only the `test_windows.py` overlay tests fail. Why does the active-window overlay test still pass? (Hint: that test builds `RawWindow(overlay=True)` directly, so which function does it never call?) Undo it afterwards.
3. Start Obsidian, run `python -m pseudo_hands.show_active_window`, and click Obsidian within 3 seconds. Note `controls read` and the note. Run it again and compare: that's a cold read vs a warm one. (It prints to your own terminal only.)

## Check yourself

1. Why does a failing control skip everything inside it, and why is its line added only after all its calls succeed?
2. Why does `walk()` catch only `COMError`, not every `Exception`?
3. Why must the retry come *after* the blocked-apps check?
4. Why isn't `WS_EX_LAYERED` enough to call a window an overlay?
5. One change to `is_user_window()` fixed three tools. Which three, and which decision does that illustrate?

<details>
<summary>Answers</summary>

1. A vanished element's children are almost always gone too, and "skip it and what's inside" is already the off-screen rule, so there's one rule to remember. Adding the line only after success means we never keep a half-read control: its name, but not whether it was a password box, for example.
2. `COMError` is UI Automation saying "I can't answer", which is a fact about the window. Any other exception is probably a bug in our code, and hiding it would make broken code look like a quiet window. The `Buggy` test proves our bugs still fail.
3. The rule is "blocked apps are never read, not even once". A retry before the check would still be a read. After the check, only windows that were allowed anyway get a second try.
4. Many real apps use layered windows for their own frames: Electron apps (Claude, VS Code) do. The overlay signal is behaviour: clicks fall through (`TRANSPARENT`), or it's a tool window that can never become active (`TOOLWINDOW` + `NOACTIVATE`).
5. `list_open_windows` (not listed, no id), `read_active_window` (never picked as the window to read), and `focus_window` (`still_there` rejects it). That's D11: the rule lives in core, next to the tools, so every caller and every brain gets it.
</details>

## How this connects to Pseudo's final architecture

These are the first changes driven by **measuring the real desktop** instead of guessing: M11 measured, M12 fixed, and the *same* counts-only method re-measured. Every fix lives in core (D11), so Hermes, the Phase 1 loop, or any future brain gets the hardened readers without changing anything. The safety rules didn't move: blocked apps are checked before any read, password boxes are never read, and error messages never reach the model. Future readers (a smarter walk for Electron depth, or OCR if it's ever needed) should keep this shape: fail per item, not per window, and report what happened in fixed words and numbers.
