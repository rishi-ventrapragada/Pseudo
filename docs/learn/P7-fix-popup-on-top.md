# P7-fix: The approval popup stays on top

## The concept in one paragraph

Windows has two separate ideas that are easy to mix up.
- **The foreground window** is the one that gets your keyboard. Windows' **foreground rule** says only the program you're using may bring a window to the front. `pseudo_hands` isn't that program, so since M18 the face passes its right on with `AllowSetForegroundWindow`, just before each tool runs. Windows withdraws that right at your next input.
- **The always-on-top layer** (Windows calls it **topmost**) holds windows that stay above all normal windows *without* taking the keyboard, like Task Manager's "Always on top" setting.

The bug: when the face's grant was lost, Windows also dropped the popup's request for the topmost layer (`MB_TOPMOST`), so the popup opened behind the face and timed out as no. The fix adds one **flag** (an option bit passed to `MessageBoxW`), `MB_SYSTEMMODAL`, which keeps the popup in the topmost layer even then. The keyboard still moves to the popup only when the grant holds.

## Web-dev analogy

- **The foreground right is the browser's user activation.** `window.open` works right after a click, and the permission runs out at the next gesture.
- **The topmost layer is `position: fixed; z-index: 9999`.** The element stays visible above everything, but focus stays in the input you're typing in.
- **The lab probe is a minimal reproduction**, like a CodeSandbox with none of your app in it. If the bug shows up there, it's the platform. If it doesn't, it's your app.
- **Run 1's false failure is a flaky e2e test.** It checked `document.activeElement` after a fixed wait, and a modal had opened in between.

## What was built (file by file)

- **`pseudo_hands/core/approval.py`:** `FLAGS` gains `MB_SYSTEMMODAL`, and the docstring says why.
- **`tests/test_approval.py`:** one new test pins `MB_SYSTEMMODAL` and `MB_DEFBUTTON2` (Cancel is the default button).
- **Scratchpad only, not committed:**
  - `lab_face.py` is a plain window that grants, like `foreground.js`.
  - `lab_hands.py` shows the popup exactly as `approval.py` does.
  - `lab_probe.py` runs the variants.
  - `verify_popup.py` drives the real face.

## Walkthrough of the key code

**1. The flags** (`approval.py`):
```python
FLAGS = (win32con.MB_OKCANCEL | win32con.MB_ICONWARNING | win32con.MB_DEFBUTTON2 | win32con.MB_TOPMOST
         | win32con.MB_SYSTEMMODAL)
```
- Each flag is one bit of a number, and `|` (bitwise OR) switches several on at once, like combining options in a bitmask.
- `MB_SYSTEMMODAL` dates from 16-bit Windows, where it froze everything until you answered. Today it means "this box is topmost". With no owner window (`None`), it disables nothing.
- `MB_TOPMOST` stays because the lab measured exactly this combination.

**2. The test** (`test_approval.py`):
```python
assert approval.FLAGS & win32con.MB_SYSTEMMODAL  # on top even when Windows won't give it the keyboard (P7 lab)
assert approval.FLAGS & win32con.MB_DEFBUTTON2  # Cancel is the default button: Enter means no
```
`&` (bitwise AND) checks that one bit is on. If someone removes the flag, this test fails.

**3. The lab's grant and its broken variant** (`lab_face.py`, `lab_probe.py`):
```python
ok = user32.AllowSetForegroundWindow(int(parts[1])) != 0  # never ASFW_ANY
...
if key_between:
    row["key_sent"] = enter_to(face_hwnd)  # V3: one Enter to OUR fake face, between grant and popup
```
- The **stand-ins** are tiny programs that copy one behaviour of the real ones. Here that's a face that grants and a `pseudo_hands` that shows the real popup from a worker thread.
- V3 adds the one thing the theory blamed: a single key press after the grant.

**4. The input clock** (`verify_popup.py`):
```python
return now_ms() - ((win32api.GetTickCount() - win32api.GetLastInputInfo()) & 0xFFFFFFFF)
```
`GetLastInputInfo` tells *when* the last mouse or keyboard input happened, never what it was. Comparing that time with each grant shows whether any input arrived in between.

## What happens when you run it (real output, annotated)

**The lab, before the fix** (no face, no model, 3 runs each):
```
V1 no grant (control)          in front 0/3 | topmost 0/3
V2 grant (today's fix)         in front 3/3 | topmost 3/3      <- Windows' rules still work on this laptop
V3 grant, then a key           in front 0/3 | topmost 0/3      <- the 2026-10-02 symptom, reproduced
V4 grant + MB_SETFOREGROUND    in front 3/3 | topmost 3/3      <- adds nothing
V5 no grant + MB_SYSTEMMODAL   in front 0/3 | topmost 3/3      <- above the face; the keyboard stays put
V6 grant + MB_SYSTEMMODAL      in front 3/3 | topmost 3/3
```
**The lab, after the fix** (it imports the real `FLAGS`, so V1 and V3 now carry the new flag):
```
V1 no grant (control)          in front 0/3 | topmost 3/3 | above face 3/3
V3 grant, then a key           in front 0/3 | topmost 3/3 | above face 3/3
```
**The real face, run 2** (real Enter, real Groq, fake windows, temporary vault; lines shortened):
```
 3. focus  | grant True +42 ms | last input -6443 ms vs grant | keyboard popup | on top True | above face True
           | clicked OK | in front after: target@0 -> next popup@411
 4. memory | grant False +1676 ms | last input -386 ms vs grant | keyboard popup | on top True | above face True
           | clicked Cancel
--- popups: 12 (6 focus, 6 memory) | on top AND above the face: 12/12 | clickable: 12/12
--- OK -> target in front: 3/3 | Cancel -> target NOT in front: 3/3 | input between grant and popup: 0/12
notes saved in the temp vault: 0
```
- **Line 3:** after OK, the target was in front at once (`target@0`). The memory popup took over 411 ms later.
- **Line 4:** the grant failed because the target, not the face, was in front, yet the popup still got the keyboard. Your OK click was the last input, and it went to `pseudo_hands`, so it could come forward by itself (M10's rule).

**Run 1 said OK worked 0/3.** That was the test's fault: it looked 1.5 s after OK, and by then the memory popup was in front. The timeline in run 2 settled it.

**Not reproduced:** on 2026-10-02, all 9 popups opened behind the face. Today, 24 of 24 real popups kept their grant. What took the grant away that day is still unknown. With the fix, the popup is on top either way.

## Try this

1. Delete `| win32con.MB_SYSTEMMODAL` in `approval.py` and run `.\.venv\Scripts\python.exe -m pytest tests/test_approval.py`. Which test fails? Put the flag back.
2. Run a popup that waits 3 s, closes itself after 8 s and does nothing:
   ```powershell
   .\.venv\Scripts\python.exe -c "import time, pseudo_hands.core.approval as a; time.sleep(3); print(a.show_popup('Test popup: closes in 8 s. Nothing happens.', timeout=8))"
   ```
   While it waits, click into another window. The popup should appear on top, while your typing still goes to your window. It prints `False`.
3. Do the same without the fix, changing nothing on disk: add `a.FLAGS &= ~0x1000;` (switch the `MB_SYSTEMMODAL` bit off) right after the imports. Where does the popup open now, and does it carry the topmost flag?

## Check yourself

1. What's the difference between the foreground window and the always-on-top layer?
2. On 2026-10-02 Windows accepted every grant, yet the popups opened behind the face. How can both be true?
3. If `MB_SYSTEMMODAL` already keeps the popup on top, why keep the grant in `foreground.js`?
4. Why is it safe that the popup sometimes doesn't get the keyboard?
5. Run 1 said OK worked 0/3. Why wasn't that a real failure, and how was that shown?

<details>
<summary>Answers</summary>

1. The foreground window gets your keyboard, and only the program you're using may change it. The topmost layer only decides what is drawn above what. A window there stays visible without taking the keyboard.
2. A grant lasts only until the next input. Windows accepted it, but something took it back in the 50-78 ms before the popup asked for the front; the lab's V3 shows one key press is enough. With the right gone, Windows also dropped `MB_TOPMOST`.
3. The grant decides the keyboard. With it, the popup is ready for Esc or Tab at once. Without it, you have to click the popup. Both are safe; the grant is just more convenient.
4. Default no (D13): your typing never answers the popup, Enter means Cancel even when it does have the keyboard, and an unanswered popup times out as no. A popup you can see but can't type into is the safe direction.
5. A 20 ms timeline after each OK showed the target in front at once, then the memory popup taking over 0.4-1.2 s later. Run 1's single check at 1.5 s landed on the memory popup.
</details>

## How this connects to Pseudo's final architecture

- **Click and type (Phase 8)** puts every action behind this popup, so it has to be seen. It is now on top whatever happens to the grant.
- **The fix lives in core (D11).** Any brain and any face gets it, including a face that never grants, like a terminal or Claude Code over MCP.
- **D13 and D14 are unchanged.** It's still Pseudo's own popup, the default is still no, and no action may touch it.
