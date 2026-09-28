# M9: read_active_window

## The concept in one paragraph

Every Windows app keeps an **accessibility tree** for screen readers. **UI Automation** (UIA) is the API for reading it. It's the desktop's DOM: each node is a **control** with a type (Button, Edit, Document…), a **Name** (like `aria-label`), and sometimes text you read through a **pattern** (`ValuePattern` is like `input.value`). `read_active_window` walks that tree for the front-most window and turns it into a short, indented text outline. It runs every privacy rule first: blocked apps are never read, password boxes are never read, the whole outline is redacted, then it's cut to fit Groq's free tier. Reading *text* instead of screenshots is what lets Pseudo see the screen without pixels ever leaving the laptop (D6, L3).

## Web-dev analogy

- The UIA tree is `document.body`; walking it is a DOM traversal with a budget.
- `Name` is `aria-label`, `IsOffscreen` is `display: none`, `ValuePattern.Value` is `input.value`, and `IsPassword` is `<input type="password">`, which we never read.
- The 1,200-character cap is like paginating an API response: the client gets a useful first page and `truncated: true`, not the whole database.

## What was built (file by file)

| File | What it does |
|---|---|
| `core/ui_tree.py` | **The only file that touches UIA.** Walks one window by handle → `(depth, type, text)` lines, within a budget. No privacy logic. |
| `core/active_window.py` | Picks the window, applies the blocked-apps rule, redacts, caps. All privacy decisions live here. |
| `core/windows.py` | `RawWindow` gained a `handle`, so the reader opens exactly the window it chose. |
| `core/redactor.py`, `india_recognizers.py`, `indian_places.txt` | Fixes found by M9's first real read (below). |
| `mcp_server.py` | One more `add_tool` line. Still no functions of its own (D11). |
| `show_active_window.py` | Demo: a 3-second countdown to click a window, then prints what a model would get. |
| `tests/test_active_window.py` + redactor tests | 13 + 9 new tests, all on fake trees and fake text. **143 pass**, 1 expected failure. |

Library: **`uiautomation` 2.0.29**, a thin wrapper over Windows' own UIA interface with one dependency, not pywinauto (last release claims Python ≤3.7). It works on our Python 3.13.3.

## Walkthrough of the key code

**1. COM per thread.** UIA is a COM interface, and COM must be set up in each thread that uses it. The MCP server runs tools in worker threads, so the walk is wrapped:
```python
with auto.UIAutomationInitializerInThread():
    root = auto.ControlFromHandle(handle)
```

**2. The walk and its budget** (`read_tree`): depth-first (screen reading order), skipping off-screen controls and everything inside them. It stops at **depth 12, 200 controls, 4,000 characters or 2 seconds**, whichever comes first, and sets `truncated`. A huge browser tree can't stall a call.

**3. Password boxes are never read:**
```python
if control.IsPassword:  # never read what's typed in a password box
    return f"{name} = [password field]"
```
A test uses a fake control whose `GetPattern` *fails the test if it's called at all*.

**4. Blocked apps are never walked.** `read_window` checks the app *before* touching the tree. A test asserts the (fake) walker was never called for `KeePass.exe` or for an unknown app.

**5. Redact first, then cut:**
```python
redacted = redact(outline(tree.lines))  # whole outline first, THEN cut (never half a secret)
content, was_cut = cap(redacted, MAX_CONTENT_CHARS)
```
If we cut first, `+91 98765 | 43210` could be split so that neither half looks like a phone number, and it would leak. The walker also never shortens a long text in the middle of a number.

**6. The assistant's own window is skipped** (`ASSISTANT_APPS = {"hermes.exe"}`), so Hermes Desktop doesn't read its own chat. Caveat: if you run Hermes' *CLI* in a terminal, the terminal is the front window and it will be read.

## What the first real read found (and what was fixed)

The first read of a fake test window exposed M7 gaps that no title test had shown:
- **Leak: a UPI ID at the end of a sentence** (`UPI rahul.v@okaxis.`) wasn't masked. The pattern refused *any* dot after it, to keep emails out. It now only refuses `.letter` (a domain). The final check also refuses **any** leftover `word@word` token, and re-checks every Indian ID shape.
- **Over-masking:** "M9" was masked as `[US_DRIVER_LICENSE]`. All **five US-only recognizers** (SSN, driver's license, bank, ITIN, passport) are now off. Long ID numbers are **still masked by `LONG_NUMBER`** (any run of 8+ digits, spaces and hyphens allowed): a test checks that a US-SSN-shaped `123-45-6789` still loses its digits.
- **Missed place:** spaCy didn't know "Pune". A committed `indian_places.txt` (states, UTs, about 60 major cities) now masks them as `[LOCATION]`.
- The 30-title over-masking check stayed at **1/30 (3%)** after these changes.

## What happens when you run it (fake data only)

The test window is a small Windows Forms window made by our script, **all fake data**. Notepad wasn't used here, because Windows 11 Notepad can restore your previous tabs, whose names would show up in the tree. Every read was guarded: the result was printed only if our window was in front before *and* after, and the returned title was ours.
```
[core] took 2.01 s | controls 12 | truncated False | content chars 337
  Window: Pseudo M9 test - [PERSON] notes
    Text: Meeting with [PERSON] in [LOCATION]
    Edit: Phone = Call [IN_PHONE]
    Edit: Password = [password field]          <- never read
    Edit: Notes = PAN [IN_PAN]. [NRP] [IN_UPI]. Aadhaar [IN_AADHAAR].
    Button: Save
[mcp] same content as core: True
```

## Tokens on Groq's free tier (measured)

| Question (Hermes `pseudo` profile) | API calls | Input + output tokens |
|---|---|---|
| M8: `list_open_windows` only | 2 | 5,955 input |
| "what does the active window say?" | 2 | **6,109 + 227 = 6,336** |
| "Which windows do I have open, and what does the active one say?" (both tools) | 3 | **6,916 + 418 = 7,334** |

Our 337-character outline became a 910-character tool message after Hermes' wrappers. A window that fills the 1,200-character cap adds about 250 more tokens. A two-tool question therefore fits under 8,000/min **with only ~600 to spare, so one such question per minute.** The fixed cost is the harness: each call resends the system prompt and tool schemas.

## Try this

1. Run `python -m pseudo_hands.show_active_window`, click a window of your own within 3 seconds, and read what a model would get (only on your screen).
2. Add `notepad.exe` to `blocked_apps.txt`, focus Notepad, run the demo, and see `blocked app: nothing read`.
3. Lower `MAX_CONTENT_CHARS` to 300 and see where the cut lands (always at the end of a line).

## Check yourself

1. Why does `ui_tree.py` contain no privacy logic at all?
2. Why must the outline be redacted *before* it's cut to 1,200 characters?
3. What guarantees a password box's value is never read, and how does a test prove it?
4. Why did the M9 marker switch from Notepad to our own WinForms window?
5. Why does a two-tool question cost 3 API calls, and why does that matter on Groq's free tier?

<details>
<summary>Answers</summary>

1. So that it has one job (read the tree) and every privacy decision lives in one place (`active_window.py`), where it's checked *before* the walker is even called.
2. A cut can split a secret into pieces that no longer look like a phone or ID number, so they'd slip past redaction.
3. `control.IsPassword` is checked first, and the value pattern is never requested. The test's fake control fails if `GetPattern` is called.
4. Windows 11 Notepad can restore your previous tabs into the window we open, and their names would appear in the tree. Our own window holds only fake data.
5. Call 1 decides to use a tool, and each tool result needs another call. Each call resends about 2–3K tokens of prompt and schemas, so three calls use about 7.3K of the 8K/min budget.

</details>

## How this connects to Pseudo's final architecture

- **M10** adds the first *action* (`focus_window`) behind D13's native approval popup. Reading needed redaction; acting needs consent.
- **M11** measures how often the tree is empty (games, canvas apps) before deciding whether local OCR is needed. Whatever it reads goes through the same `redact()`.
