# M7: Local redactor

## The concept in one paragraph

**Redaction** means finding personal information in text and replacing it with a label, so `Call +91 98765 43210` becomes `Call [IN_PHONE]`, *before* any cloud model sees the text. There are two ways to find it: **patterns** (regular expressions for things with a fixed shape: phone numbers, PAN, emails) and **NER**, *named-entity recognition*: a small trained language model that guesses which words are names or places. Microsoft's open-source **Presidio** combines both, and it runs entirely on this laptop. M7 wraps it in one core function, `redact(text)`, that **fails closed**: when unsure, it masks, and when anything goes wrong, it raises instead of returning the original text.

## Web-dev analogy

- Presidio's **analyzer** is a linter: it reports problems (spans of personal info) without changing anything.
- A **recognizer** is one lint rule, and its **score** is the rule's confidence.
- The **anonymizer** is `eslint --fix`: it rewrites each reported span into a mask.
- The **spaCy model** (`en_core_web_sm`) is a pretrained dependency shipped as a package, like bundling a small ML model with your app.
- **Fail closed** is like a form validator that rejects input when the validator itself crashes, instead of letting the input through.

## What was built (file by file)

| File | What it does |
|---|---|
| `pseudo_hands/core/redactor.py` | `redact(text)`: builds the engine once, finds and masks, re-checks the output, raises `RedactionError` on any failure. |
| `pseudo_hands/core/india_recognizers.py` | Five shape-only regex recognizers: `IN_PHONE`, `IN_AADHAAR`, `IN_PAN`, `IN_UPI`, `LONG_NUMBER`. |
| `pseudo_hands/core/redaction_terms.example.txt` | Format for your private terms. The real `redaction_terms.txt` is **gitignored** (it would hold exactly what we protect) and starts empty. |
| `pseudo_hands/show_redaction.py` | Thin demo on **fake** titles: before → after, plus timings. |
| `tests/test_redactor.py` | 27 tests on fake data: 23 pass, and 4 are documented false positives marked `xfail` (expected to fail). |
| `requirements.txt` | Presidio 2.2.364, spaCy 3.8.16, `en_core_web_sm` 3.8.0 (12.8 MB). The venv grew by **259 MB**, mostly spaCy's numerical libraries. |

## Walkthrough of the key code

**1. Build the engine once** (`build_analyzer`, cached with `@lru_cache`). We ask for the *small* spaCy model instead of Presidio's default `en_core_web_lg` (400 MB for barely better accuracy), load Presidio's standard recognizers, then add Presidio's own Indian ones, which ship **switched off**, plus our five.

**2. Our Indian recognizers match by shape** (`india_recognizers.py`):
```python
("IN_AADHAAR", r"(?<!\d)\d{4}[\s-]?\d{4}[\s-]?\d{4}(?!\d)", 1.0),   # 12 digits, NO checksum
("IN_UPI", r"\b[\w.\-]{2,256}@[A-Z][A-Z0-9]{1,63}\b(?!\.)", 1.0),  # like email, but no dot after @
("LONG_NUMBER", r"(?<!\d)\d(?:[\s-]?\d){7,}(?!\d)", 0.3),           # catch-all: 8+ digits
```
Presidio *has* an Aadhaar recognizer, but it only fires when the number **passes the Verhoeff checksum**. For validating a form, that's right. For privacy, it's backwards: a real Aadhaar with one typo is still someone's Aadhaar. A test builds a checksum-valid and a checksum-invalid fake and requires **both** to be masked.

**3. Find, then replace** (`redact`):
```python
findings = analyzer.analyze(text=text, language="en", entities=entities, score_threshold=0.0, ...)
masked = build_anonymizer().anonymize(text=text, analyzer_results=findings, operators=operators).text
```
`score_threshold=0.0` means even a low-confidence guess gets masked. When two findings cover the same text, the higher score names the mask. That's why our exact Indian shapes score 1.0: at first, `98765-43210` came out as `[DATE_TIME]`, because Presidio's date guesser scored higher. (Still masked, just mislabelled.)

**4. The six fail-closed rules:** mask at any confidence; shapes not checksums; the `LONG_NUMBER` catch-all; **re-check the output** (a phone, Aadhaar or long-number shape left over raises); **any error raises** `RedactionError` (the model, the analyzer, the anonymizer, or a missing terms file); and **no network** (a test blocks all sockets and rebuilds the engine).

**5. What is deliberately NOT masked: `ORGANIZATION`.** spaCy guesses organization names, and in window titles those are app and site names ("Visual Studio Code", "GitHub", "Spotify"). Masking them would make titles useless. We measured it: 8 of our 30 fake titles contain an ORGANIZATION guess.

## What happens when you run it (fake data only)

```
--- LOADING THE REDACTOR (spaCy model + recognizers, once per process) ---
loaded in 1.05 s                      <- plus ~9 s of importing Presidio/spaCy on a cold start
  changed  Chat with Rahul Verma, UPI rahul.v@okaxis - WhatsApp Web - Google Chrome
           -> Chat with [PERSON], [LOCATION] [IN_UPI] - WhatsApp Web - Google Chrome
  changed  PAN ABCPE1234F, Aadhaar 2345 6789 0123 - scan.pdf - Adobe Acrobat
           -> PAN [IN_PAN], Aadhaar [IN_AADHAAR] - scan.pdf - [PERSON]      <- "Adobe Acrobat" as a name: over-masking
  changed  Bank statement acct 123456789012345 - Google Chrome
           -> Bank statement acct [DATE_TIME] - Google Chrome               <- masked, label imperfect
  same     Downloads - File Explorer
mean 14.5 ms | median 14.3 ms | 95th percentile 20.3 ms | slowest 26.5 ms
```
About 15 ms per title: a list of 10 windows costs about 0.15 s. The whole process takes about 10.5 s to start, which matters in M8, because Hermes gives the MCP server 30 s to connect.

## False-positive rate (over-masking)

We ran 30 realistic **fake** titles with no personal info (VS Code files, YouTube, GitHub, Notepad, File Explorer, Spotify, Settings…). **8 of 30 changed: a 27% false-positive rate.**

| Recognizer | Titles | Example |
|---|---|---|
| `UrlRecognizer` | 4 | `main.py`, `README.md`, `notes.md` → `[URL]` (`.py` and `.md` are real country domains: Paraguay, Moldova) |
| spaCy `PERSON` | 3 | `Lofi`, `New Tab - Google Chrome`, `Vercel - Deployments - Google Chrome` |
| spaCy `LOCATION` | 1 | `Windows PowerShell` |
| US-only recognizers (SSN, license, bank, ITIN, passport) | 0 | none triggered |

Over-masking is the *safe* direction of failure (D6), but 27% would make M8's titles noticeably less useful. Fixing it is a decision for the owner, not something to do silently. The 4 cases are pinned as strict `xfail` tests, so any fix shows up immediately.

## Try this

1. Rename `pseudo_hands/core/redaction_terms.txt` and run the demo. Every call raises `RedactionError`. Rename it back.
2. Add a fake term like `Zorblax` to your terms file and redact `"Zorblax quarterly plan"`.
3. Change `SPACY_MODEL` to `en_core_web_lg` (after installing it) and compare the false positives and timings. Then change it back.

## Check yourself

1. Why is a checksum the wrong test for deciding whether to mask an Aadhaar number?
2. What does `score_threshold=0.0` change, and why is that "fail closed"?
3. Why does `redact()` re-check its own output?
4. Why is ORGANIZATION not masked, and what would it cost to mask it?
5. Where does the 27% false-positive rate come from, and which direction of error does fail-closed choose?

<details>
<summary>Answers</summary>

1. A checksum answers "is this a valid ID?", but privacy asks "could this be someone's ID?". A typo'd real number fails the checksum and would leak.
2. Every finding, however unsure, gets masked. An uncertain guess costs a little readability, while a missed one costs privacy.
3. As a last net: if a recognizer or the anonymizer misbehaves, a phone, Aadhaar or long-number shape in the output raises instead of leaking (a test simulates a do-nothing anonymizer).
4. In titles, organizations are mostly app and site names, which aren't personal. Masking them would blank out the useful part of 8 of 30 ordinary titles.
5. From the URL recognizer reading `.py`/`.md` filenames as domains (4) and the small spaCy model guessing names and places in titles (4). Fail-closed accepts over-masking over leaking.

</details>

## How this connects to Pseudo's final architecture

- **M8** calls `redact()` on every title inside `list_open_windows()` (core), so every brain gets redacted titles, and a `RedactionError` means the title is withheld.
- **Phase 4** (UI Automation text, OCR) sends everything it reads through the same `redact()` before it can leave the laptop: that's why the privacy layer came first.
- **Limits stay real:** the small model misses unusual names and invents some. The blocked-apps list (M4) and your private terms list remain the strongest guarantees for what you care about most.
