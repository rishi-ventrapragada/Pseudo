"""M19: corrections to what the recognizers find, applied in redactor.find_personal_info() (D19).

What it demonstrates: fixing a recognizer's known blind spot with a narrow rule you can
argue is safe, instead of switching the recognizer off. spaCy's NER guessed that codes like
"M15", "Q3" and "A-20931" were people's names. The rule: a CODE-SHAPED word (capital letters
plus digits) is never a name, so it is trimmed off the edges of a PERSON or NRP finding.
Why it can't release a real name:
  - only a word containing a digit can be trimmed, and a name word never contains one;
  - a code in the MIDDLE of a finding leaves the whole finding masked;
  - "rahul99" and "Rahul99" are not code-shaped (lower-case, or 5+ letters), so they stay masked;
  - LOCATION is left alone: "B-204" next to a building name is part of an address.
(M29) Pseudo's own control ids (c169, from read_active_window's outline) too: spaCy guessed some were
people, which hid those controls from the model. An id contains digits, so the same argument holds.

The second rule: Presidio's WEAK vehicle-plate shapes (1-3 letters + 4 digits, scored 0.01-0.2
by Presidio itself) are ignored, because in practice they are course codes (MA2201, CSE1001).
Full plates (MH12AB1234, the BH series) score 0.4 or more and stay masked, and so does a weak
shape next to a word like "vehicle" or "registration": Presidio's context boost lifts it to 0.4+.
"""

import re

from presidio_analyzer import RecognizerResult

# 1-4 CAPITAL letters, an optional hyphen, then digits (M15, Q3, CS101, PSD-142, A-20931, ECE-2),
# or digits, capitals, digits (21CS42), or (M29) a control id with its outline colon (c169, c169:).
# Matched case-sensitively, against a whole word.
CODE_WORD = re.compile(r"[A-Z]{1,4}-?\d{1,6}[A-Z]?|\d{1,3}[A-Z]{1,4}\d{1,4}|c\d{1,6}:?")
NAME_LIKE = {"PERSON", "NRP"}  # spaCy's guesses at people and groups (NRP: nationality, religion, politics)
WEAK_PLATE_SCORE = 0.4  # below this, a vehicle-plate finding is one of Presidio's weak shapes with no context


def is_weak_plate(finding: RecognizerResult) -> bool:
    return finding.entity_type == "IN_VEHICLE_REGISTRATION" and finding.score < WEAK_PLATE_SCORE


def trim_codes(text: str, finding: RecognizerResult) -> RecognizerResult | None:
    """The finding without code-shaped words at its edges; None if it was nothing but codes."""
    if finding.entity_type not in NAME_LIKE:
        return finding
    words = list(re.finditer(r"\S+", text[finding.start:finding.end]))
    while words and CODE_WORD.fullmatch(words[0].group()):
        words.pop(0)
    while words and CODE_WORD.fullmatch(words[-1].group()):
        words.pop()
    if not words:
        return None
    start, end = finding.start + words[0].start(), finding.start + words[-1].end()
    return RecognizerResult(finding.entity_type, start, end, finding.score,
                            recognition_metadata=finding.recognition_metadata)
