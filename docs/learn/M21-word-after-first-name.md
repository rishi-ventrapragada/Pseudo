# M21: A word after a listed first name (tried, not shipped)

## The concept in one paragraph

M20's names list missed rare surnames like "Boddu" in "Keerthana Boddu". M21 tried **rule 4**: mask any Capitalized word right after a *listed* first name. On M20's held-out set N2 it looked like a fix (86% → 95%). On a **fresh** held-out set, N4, written before any measurement, it changed nothing: **57% → 57%**. The reason is structural, not a bug. Rule 4 is **anchored** on the list: it only fires when a name *on the list* sits next to the unknown word. N4's names are mostly not on the list, so there is nothing to anchor on. A rule built on a list can't reach names the list doesn't know. So the rule was not shipped, and the name leak is recorded as only partly fixed.

## Web-dev analogy

- **An anchored rule** is like a CSS sibling selector, `.known + span`. It styles the span after a `.known` element, and it does nothing on a page with no `.known` elements, however many spans there are.
- **A spent held-out set** is a test you've already looked at while writing the fix. Once you've tuned against it, passing it says little about code you haven't seen yet, so you need a fresh one, written first.
- **Not shipping a measured change** is a feature flag you leave off: the code exists (here as a patch outside the repo), the metrics said no, so users never get it.

## What was built (file by file)

- **`tests/name_cases.py`:** N4 (40 new fake held-out names in the same groups as N2, 8 of them also in ALL CAPS), N4_LOWERCASE (reported only) and N5 (12 ordinary lines that start with a listed first name, like "Uday Express timetable"). Committed in `fad70b4`, before any M21 measurement.
- **`PRD.md`, `DECISIONS.md`:** the M21 result, and M20's result and D21 now say plainly that recall on fresh held-out names is 57%.
- **Nothing in `pseudo_hands`:** rule 4 lives as a patch outside the repo. Shipping it would have cost precision for no recall.

## Walkthrough of the key code

**1. The rule that was tried** (one more shape next to M20's three in `name_recognizers.py`):
```python
("word_after_first_name", rf"\b(?:{first_name})\s+(?:[A-Z][a-z]+|[A-Z]{{2,}})\b"),
```
Read it left to right: a *listed* first name, a space, then any Capitalized (or ALL CAPS) word. The first group is the **anchor**. The second group is what the rule is meant to catch. If the first group never matches, the second group never gets a chance.

**2. Why N4 gave it nothing to anchor on.** Counting N4's name words against the 513 names on the list (339 first names, 174 surnames):
```
first names on list: ['Pallavi'] /36
other words on list: ['Pillai', 'Rao'] /37
```
Rule 4 needs the *first* word on the list. In N4 that's true for one name out of 36.

**3. Why N2 fooled us.** M20's list was written while looking at N1, and common first names appear in N2 too: 25 of N2's 36 first names are on the list, so in N2 the anchor usually existed. M21's rule was also designed *after* seeing which N2 names leaked. Both make N2 optimistic, and that's why N4 was written and committed before measuring.

## What happens when you run it (real output, annotated)

Fake names only; your private terms file was replaced by an empty list in memory.
```
===== sm + nolist =====          (spaCy alone, no list)
M21 R2 N4 held-out recall 217/384 (57%)
===== sm + list =====            (today, M20's list)
R2 N2 held-out recall 330/384 (86%)
M21 R2 N4 held-out recall 218/384 (57%) (incl. ALL CAPS 8/64 (12%))     <- the list adds 1 of 384
M21 R10 N5 ordinary words masked besides the listed name: 6
===== sm + list + rule 4 =====
R2 N2 held-out recall 366/384 (95%) (incl. ALL CAPS 64/64 (100%))      <- looks like a fix...
M21 R2 N4 held-out recall 219/384 (57%) (incl. ALL CAPS 8/64 (12%))     <- ...but on fresh names: +1
M21 R3 first alone 95/112 (85%), initials 81/96 (84%)                   <- missed (>= 90%), with or without rule 4
M21 R10 N5 ordinary words masked besides the listed name: 14 ['Vilas', ..., 'Express', ..., 'Talkies']
R4 sensitive 37/37 | R5 cue phrases 2/16 | R6 N3 4/17 | R7 8.9 ms | R9 147 MB   <- no regressions
```
Three lines tell the whole story: spaCy alone 217, the list 218, the list plus rule 4 219. Meanwhile rule 4 more than doubles the ordinary words it hides on N5 (6 → 14): "Uday **Express**", "Gita **Press**", "Ganesh **Talkies**". A cost with no benefit on unseen names, so R2's miss decides it.

## Try this

1. Pick a fake name whose first name *is* on the list (say "Rahul Boddapati") and one whose first name isn't ("Lahari Boddapati"). Predict which one rule 4 would fully mask, then check with `redact()` today (no rule 4): which word does spaCy catch?
2. Run `redact("Chat with Pallavi Gadiraju")`, then temporarily delete `Pallavi` from `indian_names.txt` and run it again. Which words survive each time, and was the list or spaCy catching them? Restore the list afterwards. (Use your own fake surname, not one from N4: held-out names stay untouched.)
3. Write three fake names from your own region *without* looking at the list, then check how many of their words are on it. That's a tiny held-out set of your own.

## Check yourself

1. What does "anchored on the list" mean for rule 4?
2. Why did rule 4 score 95% on N2 but 57% on N4?
3. Why was N4 committed before any M21 measurement?
4. Rule 4 didn't lose any names. Why not ship it anyway?
5. What would actually raise recall on names like N4's?

<details>
<summary>Answers</summary>

1. It only fires when a word that's already on the list (a first name) is present. The list is the starting point, so the rule can't do anything for names whose first word isn't listed.
2. N2 was spent: the list was written with common names in mind, and rule 4 was designed after seeing N2's misses. Many N2 names had a listed first name as an anchor. N4's names were chosen without checking the list, and only 1 of 36 first names is on it.
3. So that neither the list nor the rule could be tuned to it. A held-out set written after seeing results tends to measure what you already fixed.
4. It hides more ordinary words (6 → 14 on N5) and gives one extra name-context out of 384 on fresh names. Over-masking has a cost: the model can't read "Uday Express" or "Gita Press".
5. Something that knows more names: a much larger names list (for example from a public dataset), or a different model. M22 plans the larger list, measured on a new held-out set.
</details>

## How this connects to Pseudo's final architecture

- **Recall on unseen names is the open problem.** D21 now says so: names on the list are masked, names off it fare as well as spaCy alone (57% on N4). Your own additions to `indian_names.txt` and `redaction_terms.txt` remain the most reliable fix for the people who matter to you.
- **The method held up.** A fresh held-out set caught a change that looked good on a spent one. Every future redactor change gets the same treatment: held-out set first, thresholds fixed, then measure.
- **M22** (to be planned) tries the other lever: a list large enough to know most names, which raises new questions about licences, size, RAM and speed.
