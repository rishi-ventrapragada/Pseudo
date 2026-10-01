# M19: Redactor precision

## The concept in one paragraph

A privacy filter can be wrong in two directions.
- A **false positive** masks something harmless: "Pseudo M15 notes" became "Pseudo [PERSON] notes".
- A **false negative** lets personal info through: a name that isn't masked.

**Precision** is how rarely the first happens, and **recall** is how rarely the second does. D6 says "when unsure, mask", so Pseudo trades precision for recall. Over-masking is annoying; a leak is a failure. M19 improves precision **without losing any recall**. The method: write the test sets and pass rules *before* measuring, then change only what the measurements point at. The measurements pointed at spaCy's **NER** (named-entity recognition, the language model that guesses names, places and dates): 11 of the 18 wrong masks were its date guesses. Building the guards also uncovered a recall problem: some Indian names leak. That is M20.

## Web-dev analogy

- **Precision vs recall** is a spam filter: a false positive hides a real email, and a false negative lets spam in.
- **Fixed criteria before measuring** is writing the failing test before the fix, so the fix can't quietly redefine "passing".
- **Presidio's de-duplication** is like a CSS cascade: two rules match the same element, the more specific (higher-scoring) one wins, and the other is gone. Removing the winner afterwards doesn't bring the loser back.
- **NER vs patterns** is an ML-based input classifier vs a `zod` schema. Use the classifier for fuzzy things (names), and the schema for things with a shape (dates).
- **Strict `xfail` tests** are like `it.fails()` in Vitest: a test that *must* fail today, so you're told the day it starts passing.

## What was built (file by file)

- **`pseudo_hands/core/date_recognizers.py`** (new): birthday-shaped dates and ages as regex patterns.
- **`pseudo_hands/core/finding_filters.py`** (new): `trim_codes()` (codes are never names) and `is_weak_plate()`.
- **`pseudo_hands/core/redactor.py`:** spaCy's DATE and TIME labels switched off, the new patterns registered, the filters applied in `find_personal_info()`, and numeric dates added to the leak check.
- **`tests/redaction_cases.py`** (new): the fixed fake sets (41 ordinary lines, 37 sensitive cases, 18 guards, 4 residuals, 3 known leaks).
- **`tests/test_redactor_m19.py`** (new): 137 tests plus 7 strict `xfail`.
- **`pseudo_hands/show_redaction.py`:** 3 new demo titles.
- **Docs:** D19, PRD (the M19 result and M20 as a live leak), ARCHITECTURE, and the `pseudo_hands` README.

## Walkthrough of the key code

**1. Switching spaCy's date guesses off, at the source** (`redactor.py`):
```python
SPACY_LABELS_IGNORED = ["DATE", "TIME"]
...
"ner_model_configuration": {"labels_to_ignore": SPACY_LABELS_IGNORED},
```
The obvious fix would have been to drop DATE_TIME findings that came from spaCy *after* analysis. That would have leaked birth dates. When two recognizers find the same span, Presidio keeps only the higher score. Measured before M19:
```
'DOB 12/03/1998'  [('Spacy', 'DATE_TIME', '12/03/1998', 0.85)]   <- the date pattern's finding (0.6) was already gone
```
Dropping that spaCy finding would have left the date with no finding at all.

**2. Dates by shape** (`date_recognizers.py`). Each pattern is written out with examples:
```python
# 3 March / 3rd March 1998 / 15 August / the third of March 1998: a day, then a month name
("DATE_TIME", "day_month", rf"\b(?:the\s+)?(?:{DAY}|{DAY_WORD})\s+(?:of\s+)?{MONTH}\b(?:,?\s+{YEAR}\b)?"),
# born in 1998 / DOB: 1998 / birth year 1998: a year right after a birth word
("DATE_TIME", "birth_year", rf"\b{BIRTH_WORD}[\s:,\-]*(?:in\s+|on\s+)?{YEAR}\b"),
```
The rule (D19): mask a date when it could be a birthday, meaning a day and a month, or a year next to a birth word. "10:30", "Monday", "tomorrow", "order 4471" and "March 2026" stay visible. Presidio's own `DateRecognizer` still catches numeric dates.

**3. Codes are never names** (`finding_filters.py`):
```python
CODE_WORD = re.compile(r"[A-Z]{1,4}-?\d{1,6}[A-Z]?|\d{1,3}[A-Z]{1,4}\d{1,4}")
...
while words and CODE_WORD.fullmatch(words[0].group()):
    words.pop(0)
```
Code-shaped words are trimmed only from the *edges* of a PERSON or NRP finding. Why that can't release a name:
- a name word never contains a digit;
- "Rahul M15 Verma" stays fully masked, because the code is in the middle;
- "rahul99" isn't code-shaped, so it stays masked.

**4. Weak plates** (`finding_filters.py`): `score < 0.4` drops Presidio's 0.01-0.2 shapes, like MA2201 and CSE1001. Presidio's own context boost lifts a weak shape next to "vehicle" or "registration" to 0.4 or more, so that one stays masked:
```
'MA2201 assignment 3'          [('MA2201', 0.01)]   -> dropped
'Vehicle no. DL1234 parked'    [('DL1234', 0.4)]    -> still masked (context)
```

## What happens when you run it (real output, annotated)

All of it is fake text; your terms file was replaced by an empty list in memory.
```
BEFORE  ORDINARY changed today: 17 of 41 (41%)
        spaCy DATE_TIME 11 | spaCy PERSON 5 | spaCy NRP 1 | spaCy LOCATION 1 | InVehicleRegistration 1
AFTER   P4 ordinary lines changed: 4 of 41 (10%)       <- the 4 residuals named in the plan, nothing else
        P3 target tokens surviving: 29 of 29
        P1 sensitive fully masked: 37 of 37            <- every sensitive fake case since M7
        P2 guards fully masked: 18 of 18               <- birth dates, ages, names next to codes, plates
        known name leaks still leaking (M20): 3 of 3
P5      M8's 30 titles: changed 1 of 30 (3%)           <- only "Lofi", as in M8
P7      median per title: 9.3-9.8 ms before -> 8.2-8.7 ms after   (two rounds each)
```
**The M15 battery** (`gpt-oss-120b`, 2 rounds, the real loop and the real `pseudo_hands`):
```
T1 PASS ... {'read': True, 'says BLUE': True, '(says 4471)': True}
   answer: '... "Meeting with [PERSON] in [LOCATION] on Friday" ... "Notes: order 4471 ships on Monday" ...'
total: 12/12 | answered by: ['openai/gpt-oss-120b'] | fallbacks: 0
```
The model can now say "order 4471", and T4 found the target by its real fake name "Pseudo M15 target". Two runs during verification went wrong:
- **My check, not the redactor:** one summary line printed "False" because I'd required "Project status: BLUE" in every read, and T2's reads correctly say GREEN. A separate core-level read confirmed every expected line visible, with the name, phone and place still hidden.
- **`show_redaction`:** "CS101 lecture notes - DOB 12/03/1998 on the form" became "CS101 lecture notes - DOB [DATE_TIME] on the form".

## Try this

1. In `redactor.py`, set `SPACY_LABELS_IGNORED = []` and run `pytest tests/test_redactor_m19.py`. Which tests fail, and which line of the "before" table does each one match? Put it back.
2. In `finding_filters.py`, change `[A-Z]` to `[A-Za-z]` in `CODE_WORD` and run the same tests. The `rahul99` test fails. That's why the code shape only allows capital letters.
3. Run `python -c "from pseudo_hands.core.redactor import redact; print(redact('Exam on 5 May, CS101 at 10:30, born in 1998'))"` and predict the output first.

## Check yourself

1. Which is worse for Pseudo, a false positive or a false negative, and which DECISIONS entry says so?
2. Why switch spaCy's DATE label off instead of dropping its DATE_TIME findings after analysis?
3. Why can't trimming code-shaped words release a real name? What happens to "Rahul M15 Verma"?
4. Why does "Vehicle no. DL1234" stay masked when "MA2201" doesn't?
5. Why pin the residuals and the name leaks as strict `xfail` tests instead of just leaving them out?

<details>
<summary>Answers</summary>

1. A false negative, a leak. D6: when the redactor is unsure, it masks. M19 was only allowed to improve precision with recall held at 100% on every earlier sensitive case.
2. Presidio removes duplicates before you see the results. On "12/03/1998" spaCy's finding (0.85) had replaced the date pattern's (0.6), so dropping spaCy's afterwards would leave the date unmasked. Switching the label off means spaCy never competes.
3. Only a word containing a digit can be trimmed, and it has to be at the edge of the finding. Name words have no digits. In "Rahul M15 Verma" the code is in the middle, so nothing is trimmed and the whole span stays masked.
4. Presidio's context enhancer raises a weak shape's score to at least 0.4 when a word like "vehicle" is nearby. The rule drops only findings below 0.4, so a shape with plate context survives the filter and is masked.
5. A strict `xfail` must fail. If a later change fixes a residual or a leak, the test passes and pytest reports it, so the list can't silently go stale. Leaving cases out would hide what's still wrong.
</details>

## How this connects to Pseudo's final architecture

- **M20 is next and urgent:** it measures name recall on fake Indian names (first names, surnames, initials, transliterations) before choosing a fix.
- **Memory (roadmap 6)** will send redacted notes to the model through this same `redact()`. Over-masked notes would be useless, and leaky ones dangerous, so both numbers matter more there.
- **The method carries over:** fixed fake sets in `redaction_cases.py`, pass rules first, and every change argued against "can this release real personal info?"
