# M8: Redact window titles

## The concept in one paragraph

**Redact at the source.** `list_open_windows()` now runs every title through M7's `redact()` *inside core*, before the result is returned to anyone. The MCP server, the terminal demo and Hermes didn't change a line, yet all of them now receive redacted titles. This closes the Phase 2 gap where browser tab titles reached Groq unredacted. Two fixes from M7's over-masking report came first: file names like `main.py` are no longer treated as web addresses, and a committed **allowlist** of app and site names ("Google Chrome", "Notepad"…) is never analyzed. Together they cut false positives on ordinary titles from **27% to 3%**, while every sensitive fake case stays fully masked.

## Web-dev analogy

- Redacting in core is **sanitizing on the server**: like escaping HTML in the API response, not trusting each frontend to do it.
- The allowlist is like a **CSP allowlist**: a short, explicit, reviewed list of trusted names. Everything not on it gets the strict treatment.
- `[title withheld]` is like returning `200` with a placeholder field instead of crashing the whole response or leaking the raw value in an error.

## What was built (file by file)

| File | Change |
|---|---|
| `pseudo_hands/core/windows.py` | `safe_title()` + one `if` in `list_open_windows()`: blocked-apps mask first, then redaction; failure → `[title withheld]`. |
| `pseudo_hands/core/redactor.py` | File-name rule for URLs; allowlist split; private terms now masked **first** by a plain regex (Presidio's deny-list recognizer removed). |
| `pseudo_hands/core/allowed_names.txt` | Committed list of about 30 app and site names, with the rules for adding one. |
| `tests/` | +15 test cases (123 total): allowlist safety, withheld titles, blocked titles never reach the redactor, redaction through MCP. |
| Hermes `pseudo` profile (outside repo) | `connect_timeout: 30 → 60`, after a verified backup. |

## Walkthrough of the key code

**1. Where redaction happens** (`windows.py`):
```python
title, app = mask_if_blocked(raw.title, raw.app, blocked)
if title != RESTRICTED:  # blocked apps' titles never even reach the redactor
    title = safe_title(title)
```
The order matters. A blocked app is hidden completely (M4), so its title is never processed, not even by local code. Everything else is redacted.

**2. Withhold, don't crash, don't leak:**
```python
def safe_title(title: str) -> str:
    try:
        return redact(title)
    except RedactionError:  # one bad title is withheld; the other windows are still listed
        return TITLE_WITHHELD
```
M7's `redact()` raises instead of returning unprocessed text. M8 decides what a *caller* shows: `[title withheld]` for that window, and the other windows are still useful. (A missing blocked-apps list still fails the whole call, because then *no* window can be trusted.)

**3. The allowlist split** (`redactor.py`): the text is cut at each allowed name, and only the *other* pieces go through Presidio. That's needed because spaCy tagged the whole string `New Tab - Google Chrome` as one PERSON, and Presidio's built-in `allow_list` can only drop findings that exactly equal a listed word. Three safety rules:
- **The glue guard:** a name glued to `@ . / -` or letters isn't exempted. `notepad@okaxis` is a UPI ID, not the Notepad app, and is still masked.
- **No personal names on the list.** The Claude and Hermes desktop apps are left off, because their product names (read from the `.exe` metadata) are just "Claude" and "Hermes", which are also first names. A test checks that "Chat with Claude Martin" loses the name. "Claude Code" is on the list, because that's its full product name.
- **Private terms win.** Your terms are masked *before* the split. Otherwise a term containing an allowed word, like the fake "Zorblax Notepad Plan", would be cut apart and leak.

**4. The file-name rule:** a `URL` finding with no `://`, `/` or `www.` that ends in `.py`, `.md`, `.pdf` and so on is a file name. `example.org` and `github.com/x` are still masked. The trade-off: a file like `rahul_verma.pdf` used to be masked whole *by accident*, and now depends on NER, which can miss underscore-joined names. Your private terms list is the reliable guard for names that matter.

## What happens when you run it

**Over-masking, the same 30 fake ordinary titles:** **before 8/30 (27%) → after 1/30 (3%).** Only `Lofi` → `[PERSON]` remains (pinned as a strict `xfail` test). **Sensitive fake cases: 10 of 10 fully masked** (names, UPI, +91, PAN, Aadhaar, account number, email, card, IP, and `notepad@okaxis`).

**End to end, with a fake-PII marker:** a scratchpad file named `Rahul Verma +91 98765 43210.txt`, opened in Notepad:
```
[core] titles changed by redaction: 3 of 7 | withheld: 0 | mask labels: {'[PERSON]': 2, '[IN_PHONE]': 1, '[URL]': 1}
[core] marker window (fake data) redacted title: ['[PERSON][IN_PHONE].txt - Notepad']
[mcp] call incl. server start: 10.5 s | same_as_core: True
[hermes] exit 0 | 30.2 s | completed True | failed False | input tokens 5955 | api calls 2
[hermes] fake secrets absent from whole tool message: True | absent from answer: True
```
The fake name and number never reached Groq; Hermes answered from `[PERSON][IN_PHONE].txt - Notepad`. Two of the six *real* titles were changed too (one `[PERSON]`, one `[URL]`). We counted them without reading them, so we can't tell a true catch from over-masking there. That's the price of never looking.

**Cosmetic artifact:** Presidio's date recognizer sometimes swallows a ` - ` next to a number (`Call [IN_PHONE][DATE_TIME] Notepad`). Nothing leaks; the tests check privacy, not punctuation.

**Timing:** about 15 ms per title. Starting the MCP server now includes loading Presidio and spaCy. `hermes mcp test` connected in **12.75 s**, so `connect_timeout: 60` leaves plenty of room.

## Privacy ledger (updated)

- **Reaches Groq:** redacted titles, app exe names, and the focus flag.
- **Never leaves:** blocked apps (masked in M4), anything the redactor masks, your private terms, and titles it can't process (withheld).
- **Known gaps:** NER misses unusual names and names joined by underscores; the allowlist trusts its entries (so keep it to real app names). Phase 4 must route everything it reads through the same `redact()`.

## Try this

1. Add a fake term like `Zorblax` to `redaction_terms.txt`, open a Notepad file named `Zorblax plan.txt`, and run `python -m pseudo_hands.show_windows`.
2. Add `Lofi` to `allowed_names.txt`, run `pytest`, and watch the strict xfail turn into a failure. Then decide whether it should stay.
3. Rename `allowed_names.txt` and run the demo. Every title becomes `[title withheld]`.

## Check yourself

1. Why is redaction applied inside `list_open_windows()` rather than in `mcp_server.py`?
2. What does a caller get when redaction fails for one title, and why not raise?
3. Why can't "Claude" or "Hermes" go on the allowlist?
4. How does `notepad@okaxis` stay masked even though "Notepad" is allowlisted?
5. Why are private terms masked before the allowlist split?

<details>
<summary>Answers</summary>

1. D11: every brain and wrapper gets redacted titles automatically. A wrapper-level check would protect only that wrapper.
2. `[title withheld]` for that window, with the others still listed. Raising would throw away every window's useful info; returning raw would leak.
3. Allowlisted text is never analyzed. "Claude Martin" would pass through unmasked. Only full forms that can't be a person's name are safe.
4. The glue guard: an allowed name touching `@ . / -` or letters is part of a bigger token and doesn't get exempted.
5. A term that contains an allowed word would be split into pieces that no longer match the term, and would leak.

</details>

## How this connects to Pseudo's final architecture

- **Phase 3 is complete:** no title leaves the laptop without passing the blocked-apps mask and the redactor.
- **Phase 4** (UI Automation text, OCR, actions) reuses `redact()` for everything it reads, and adds D13's native approval popups for everything it does.
