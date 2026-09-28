# M11: OCR fallback (evaluation)

## The concept in one paragraph

**OCR** (optical character recognition) turns pixels of text into text. The PRD said Pseudo might need it for windows whose UI Automation tree is empty, but to **measure first and build only if needed**. So M11 built nothing in the repo. It measured how often M9's reader comes back empty on real apps, using **counts only** (app names, control counts, character counts, never titles or text). It also **fixed the decision rule before looking at any numbers**. The result: **0 of 3 open windows and 0 of 6 other apps needed OCR**, so OCR is skipped. The failures it did find were bugs in M9's own reader, which M12 fixes.

## Web-dev analogy

- It's **profiling before optimizing**: you measure load time before adding a CDN, not after.
- Fixing the thresholds first is like writing down an **A/B test's success metric before you see the results**, so the numbers can't bend the rule.
- Most "empty" windows turned out to be like a 500 error caused by **your own handler**, not by the API. Swapping in a different API (OCR) wouldn't have fixed them.

## What was built (file by file)

Nothing in the repo except the PRD line. The measurement scripts lived in the session scratchpad and were **not committed**; the key code is quoted below.

| Script | What it did |
|---|---|
| `m11_measure.py` | The counts-only measurer. It reuses M9's own `read_tree`, `read_all_windows`, `is_user_window` and blocked-apps rules unchanged |
| `m11_fake_windows.ps1` | Calibration: two of **our own** windows with the same fake text |
| `m11_diagnose.py` | Window flags, an error-tolerant walk, repeated reads |
| `m11_launch.py` | Part B: launch apps that weren't open, measure, then close **only** the windows it opened (WM_CLOSE, never kill) |
| `m11_ocr_bench.ps1` | Windows' built-in OCR on **synthetic fake-text images**, zero install |
| `m11_ocr_redact.py` | OCR accuracy, plus whether `redact()` still masks the fake personal info |

## Walkthrough of the key code

**1. Counting without reading.** The text is summed in memory and thrown away. Two things are excluded: the depth-0 line (that's the **window title**, which `list_open_windows` already handles) and the title bar with its Minimize/Maximize/Close buttons. Otherwise every window would look "readable".
```python
if line.depth == 0 or line.kind == "TitleBar" or line.text.strip().lower() in FRAME_NAMES:
    continue
count += 1
chars += len(line.text)
```

**2. Three reads per window.**
- **Cold**: the first read.
- **Warm**: 2 s later. Chromium/Electron apps build their accessibility tree lazily, the first time a reader asks.
- **Deep**: a big budget of 3,000 controls and 15 s, to tell "the app exposes nothing" apart from "M9's 200-control budget ran out first".

Below 40 content characters (about one sentence) counts as near-empty.

**3. Calibration: a positive and a negative control.** One window has the fake text in real Label controls; the other *paints* the same text as pixels. A correct classifier must call the first READABLE and the second EMPTY. If it can't tell those apart, its numbers mean nothing.

**4. Rule O (overlays)**, from each window's **extended style** bits (`GWL_EXSTYLE`):
```python
unactivatable_tool = ex & win32con.WS_EX_TOOLWINDOW and ex & win32con.WS_EX_NOACTIVATE
return bool(ex & win32con.WS_EX_TRANSPARENT or unactivatable_tool)
```
- `WS_EX_TRANSPARENT` means **click-through**: mouse clicks pass through to whatever is behind.
- `WS_EX_NOACTIVATE` means the window can never become the active window.
- `WS_EX_LAYERED` alone isn't enough to count as an overlay: Electron apps like claude.exe are layered too.

**5. The error-tolerant walk.** It's the same loop as `read_tree`, with a `try` around each control. It keeps only the **HRESULT**, Windows' numeric error code, and never the message, because a message could contain text.
```python
except COMError as error:
    errors[hex(error.hresult & 0xFFFFFFFF)] += 1
```

**6. Windows OCR with zero install.** Windows PowerShell 5.1 can call WinRT APIs directly. WinRT calls are async; `AsTask` turns one into a .NET Task we can wait on:
```powershell
$task = $asTask.MakeGenericMethod($resultType).Invoke($null, @($operation)); $null = $task.Wait(-1)
```

## What happens when you run it (real output, counts only)

**Calibration: pass.**
```
label      11/194   READABLE     <- text in real controls: 194 chars
painted     7/0     EMPTY        <- the same text as pixels: nothing in the tree
```

**Part A, the windows that were open** (first run; columns are controls/chars):
```
brave.exe           cold ERR COMError   warm 200/989   COLD-ONLY
Code.exe            cold ERR COMError   warm  24/296   COLD-ONLY
claude.exe          ERR on every read                  READ-FAILED
cua-driver.exe      1/0                                EMPTY
NVIDIA Overlay.exe  ERR on every read                  READ-FAILED
OCR candidates: 3/5 windows = 60%, 3 distinct apps
```

**The diagnosis** (flags and HRESULTs only):
```
cua-driver.exe      3840x1080  LAYERED,TRANSPARENT,TOOL,NOACTIVATE   <- click-through, spans both monitors
NVIDIA Overlay.exe  1919x1080  LAYERED,TOOL,NOACTIVATE               <- can never be activated
claude.exe  tolerant walk: 104 controls, 464 chars | errors {'0x80040201': 1} at depth 9
            M9 read_tree x5: 0x80040201 0x80040201 0x80040201 0x80040201 0x80040201
```
`0x80040201` is `UIA_E_ELEMENTNOTAVAILABLE`: "that element is gone". **One** vanished control, 9 levels deep, made M9 throw away the whole read, every time.

**Part B, apps that weren't open** (launched, measured, closed; nothing killed):
```
Calculator 529 · Settings 2,224 · Paint 1,149 · File Explorer 968   READABLE
Obsidian        cold ERR COMError, warm 290                          COLD-ONLY
DaVinci Resolve 53 controls, 44 chars                                READABLE, only just (a candidate at 100)
```

## The thresholds, and the correction

These were fixed before measuring:
- **Build** if ≥ 20% of open windows, or ≥ 2 apps, are OCR candidates.
- **Skip** if under 10% and ≤ 1 app.

Read literally, Part A said **60%: build**. The diagnosis showed all three candidates were false:
- The two overlays aren't windows anyone reads, just as the desktop isn't. **Rule O** now leaves them out.
- claude.exe's text *is* readable through UI Automation. A read that fails on one control but works when that control is skipped is **an M9 bug, not an OCR case** (**Rule B**).

Rishi accepted the corrected rules **before** Part B. They were written into the code and re-run on Part A, which reproduced the same classification. **Final: 0/3 open windows, 0 apps. Skip OCR.**

## OCR engines (research, nothing installed)

| | Windows OCR (built in) | RapidOCR 3.9.2 | Tesseract 5 |
|---|---|---|---|
| On this laptop | Yes, `en-US` | No | No |
| Size | ~0.7 MB of Python bindings (pywinrt) | ~88 MB (models + onnxruntime + OpenCV) | 50 MB .exe, outside pip |
| Speed | **53–105 ms** per image (measured) | ~0.5–2 s (estimate) | ~0.5–2 s (estimate) |
| Confidence scores | none | per line | per word |

Measured accuracy on fake text was 100% at 11 pt (light and dark) and ~98% at 9 pt. If OCR is ever needed, Windows OCR is the pick: tiny, already installed, and updated by Windows.

## The OCR redaction risk

At 9 pt, OCR read the fake PAN `ABCPV1234K` as **`A8CPV1234K`**, and `redact()` let it through:
```
'PAN A8CPV1234K forthe invoice'  ->  'PAN A8CPV1234K forthe invoice'
```
The Indian recognizers match **shapes** (5 letters, 4 digits, 1 letter). One `B`→`8` swap breaks the shape, but a human, or a model, still reads the PAN. OCR text needs protections UI-tree text doesn't:
- **Undo lookalike swaps** (O↔0, l/I↔1, S↔5, B↔8) before `redact()`.
- **Capture only the target window**, with `PrintWindow`, so a blocked app lying on top can't leak into the image.
- **Check blocked apps before capture**, not after.

## Try this

1. Feed OCR-style mistakes to the redactor. Run `python -c "from pseudo_hands.core.redactor import redact; print(redact('PAN ABCPV1234K')); print(redact('PAN A8CPV1234K'))"` and compare. Try `Call 98765 4321O`, with a letter O.
2. Open **Inspect.exe** (it comes with the Windows SDK you have installed; look under `C:\Program Files (x86)\Windows Kits\10\bin\<version>\x64\`). Hover over Calculator, then over DaVinci Resolve, and compare how much of each tree has names.
3. Print the style flags of your front window (no title): `python -c "import win32gui, win32con as c; ex = win32gui.GetWindowLong(win32gui.GetForegroundWindow(), c.GWL_EXSTYLE); print({n: bool(ex & getattr(c, n)) for n in ['WS_EX_TOPMOST', 'WS_EX_LAYERED', 'WS_EX_TRANSPARENT', 'WS_EX_TOOLWINDOW', 'WS_EX_NOACTIVATE']})"`

## Check yourself

1. Why were the build/skip thresholds written down before any window was measured?
2. Why doesn't the depth-0 line count toward a window's content characters?
3. Why did calibration use two windows with the *same* text?
4. claude.exe's read failed every time. Why wasn't it an OCR candidate?
5. Why can OCR text slip past a redactor that works on UI-tree text, and what would fix it?

<details>
<summary>Answers</summary>

1. So the numbers can't bend the rule. Once you see "60%", it's tempting to pick whichever threshold confirms what you already believe. Changing a rule after the numbers are in must be explicit and justified, as the Rule O / Rule B correction was, and accepted before the next measurement.
2. It's the window title, which is always there. Counting it would make a completely empty window look readable. Titles are already handled (and redacted) by `list_open_windows`.
3. With the same text, the only difference is *how* it's drawn: in controls, or as pixels. If the classifier calls the first READABLE and the second EMPTY, it's measuring what we care about. It's a positive and a negative control, as in a lab test.
4. The tolerant walk read 464 characters from it once one vanished control (`0x80040201`) was skipped. The text is in the tree; M9 just gave up on the whole read because of one element. That's a reader bug (fixed in M12), and OCR would have hidden it instead of fixing it.
5. The recognizers match exact shapes, and OCR changes characters (`B`→`8`, `0`→`O`) while keeping the meaning readable. Fix: undo lookalike swaps in digit-heavy tokens before `redact()`, keep the long-number rule fail-closed, and test on fake images with deliberate mix-ups.
</details>

## How this connects to Pseudo's final architecture

The perception order (L3) is **UI tree first, OCR second, a local vision model last**. M11 showed that on this laptop, today, the first tier covers everything that matters. If OCR is built later, it sits *behind* the same gates as the UI tree: the assistant's own window is skipped, blocked apps are checked **before** capture, Pseudo's own windows are refused (D14), and the text goes through `redact()` with lookalike-normalizing. The pixels never leave the laptop (D6). M11's real payoff was the three reader bugs it found, which M12 fixes.
