# M20: Name recall

## The concept in one paragraph

M19 made the redactor more **precise** (less over-masking). Building its tests turned up a **recall** problem: spaCy's small English model missed many Indian names, so they reached the model unmasked. Recall is the share of real personal info that gets masked. M20 first *measured* it on fake names: **61%** overall, and only **25%** for a first name on its own. Then it compared two fixes against criteria fixed beforehand:
- a bigger spaCy model;
- a **gazetteer**: a plain list of known names, the same idea as M9's `indian_places.txt`.

The list won. It wasn't a full pass: on names held back from the list's author it reached **86%, short of the 90% target**, and that miss is recorded rather than hidden.

## Web-dev analogy

- **A gazetteer next to a model** is an allowlist of known spam domains next to an ML spam filter. The list catches everything on it instantly and predictably, and the model guesses about the rest.
- **A held-out set** is a test suite you write *before* the code and never edit to make it pass. Tests written after the code tend to test what the code already does.
- **Case-sensitive matching** is `===` vs a loose comparison. "Ram" (a name) and "ram usage" (memory) only differ by case, so the case carries meaning.
- **"Unachievable threshold"** is a performance budget set before you measured the page: if the framework alone already exceeds it, no change of yours can pass.

## What was built (file by file)

- **`pseudo_hands/core/indian_names.txt`** (new): common first names and surnames by region. The header explains what was left out and why.
- **`pseudo_hands/core/name_recognizers.py`** (new): reads the list and builds three case-sensitive Presidio recognizers.
- **`pseudo_hands/core/redactor.py`:** registers them. A missing or broken list fails closed.
- **`tests/name_cases.py`** (new, committed *first*): the fake sets N1 (68 names), N2 (40 held-out names plus ALL-CAPS versions), lowercase names, N3 (words that are also names) and cue phrases.
- **`tests/test_redactor_m20.py`** (new). M19's three known-leak tests became normal tests.
- **Docs:** D21, the PRD result, ARCHITECTURE and the `pseudo_hands` README.

## Walkthrough of the key code

**1. Case-sensitive on purpose** (`name_recognizers.py`):
```python
FLAGS = re.DOTALL | re.MULTILINE  # Presidio's default adds IGNORECASE; leaving it out keeps lower case visible
```
Presidio patterns ignore case by default. Here that would turn "ram usage" and "pooja holidays" into names. The cost is a known gap: "chat with amit" in lower case isn't matched (test pinned as `xfail`).

**2. The three rules:**
```python
("listed_name", rf"\b(?:{any_name})\b"),                                   # "Amit", "SHARMA"
("initials_and_name", rf"\b{INITIALS}\s?(?:{any_name})\b|..."),            # "M.S. Reddy", "Ramesh S."
("word_before_surname", rf"\b(?:[A-Z][a-z]+|[A-Z]{{2,}})\s+(?:{surname})\b"),  # "Yashwanth Chowdary"
```
Rule 3 covers first names the list doesn't have, as long as the surname is listed. The missing mirror rule, a word *after* a listed first name ("Keerthana **Boddu**"), is exactly the remaining gap. That's M21.

**3. Why it can't cause a leak:** the list only *adds* findings. spaCy still runs and masks whatever it finds. So the only risk is over-masking, which R5 and R6 measure.

## What happens when you run it (real output, annotated)

All fake names; your terms file was replaced by an empty list in memory.
```
===== sm + nolist =====        (today)
R1 N1 recall 334/544 (61%)  ...  first name only 22/80 (28%)
R2 N2 held-out recall 182/384 (47%) (incl. ALL CAPS 9/64 (14%)) | lowercase 2/48 (4%)
R6 N3 over-masked 4/17          <- spaCy's own guesses: Jasmine, Bill, Amar, Raja
===== sm + list =====           (chosen)
R1 N1 recall 544/544 (100%)     <- the list was written after measuring N1: this proves little
R2 N2 held-out recall 330/384 (86%) (incl. ALL CAPS 48/64 (75%))     <- MISSED: target 90%
R3 first names alone 112/112 (100%) | initials 95/96 (99%)
R6 N3 over-masked 4/17          <- no new over-masking
R7 median redaction 9.9 ms | R9 redactor RAM: 147 MB
===== sm + list-n2out =====     (every held-out name removed from the list)
R2 N2 held-out recall 182/384 (47%)   <- back to spaCy alone: the list only knows its own names
===== md + list =====
R2 88% | R9 redactor RAM: 353 MB (+206 MB)   <- over the 150 MB cap; also masked "M18" as a place
```
**The M15 battery after the change:** 12/12 on `gpt-oss-120b`, and the fake name, phone and place never reached the model.

**Two honest corrections, both recorded in the PRD:**
- **R6** ("at most 2 of 17 over-masked") was set before N3 was measured, and spaCy alone already over-masks 4. A list can only add masks, so R6 became "no new over-masking versus before M20".
- **R2 stays at 90%** and is recorded as missed. Its test is a strict `xfail`, so pytest will say so the day M21 passes it.

## Try this

1. Add a fake surname such as `Boddu` to the `[surnames]` section and run `redact("Chat with Keerthana Boddu")` before and after. Then remove it again. (Don't tune on N2 for real: that's what held-out means.)
2. In `name_recognizers.py`, add `re.IGNORECASE` to `FLAGS` and run `pytest tests/test_redactor_m20.py`. Which precision tests fail, and why?
3. Predict, then check: `redact("Durga Puja holidays")`, `redact("RAM usage 80%")`, `redact("Call ANIL KUMAR")`.

## Check yourself

1. What's the difference between precision and recall, and which did M19 and M20 each improve?
2. Why was N2 committed before the list was written, and why does "list with N2's names removed" matter?
3. Why is the list case-sensitive, and what does that cost?
4. Why was the medium spaCy model rejected even though it caught lowercase names better?
5. Why was R6 changed but R2 not lowered?

<details>
<summary>Answers</summary>

1. Precision: how rarely harmless text is masked. Recall: how rarely personal info gets through. M19 raised precision (41% → 10% over-masked) and kept recall. M20 raised recall (47% → 86% held-out) and kept precision.
2. A set written after the list would only test names the author already had in mind. Committing N2 first fixes it in git history. Removing N2's names shows what the list does for names it has *never* seen, here nothing beyond spaCy. So real-world recall depends on how many real names are on the list.
3. So that ordinary lowercase words ("ram", "pooja") stay visible. The cost: a name typed in lower case is caught only if spaCy catches it, which it rarely does (4%).
4. It needed about 205 MB more RAM, against a 150 MB cap set because of D20, and still scored lower on held-out names. It also over-masked more ordinary text, including "M18".
5. R6's threshold was impossible by construction: the baseline was already above it, and nothing in M20 removes masks. Changing it to "no new over-masking" keeps its intent. R2 was achievable in principle and simply wasn't reached; lowering it would hide a real gap.
</details>

## How this connects to Pseudo's final architecture

- **M21** adds the mirror rule (a word after a listed first name) and measures it on a *new* held-out set. N2 can't be used again, because M21's rule was designed after seeing N2's misses.
- **The list is yours:** adding the names that matter to you (family, colleagues) is the most reliable fix for them, and the private terms list (M7) still works for anything that must never leave.
- **Memory (roadmap 6)** will pass notes through the same `redact()`. Notes are full of names, so recall matters even more there.
