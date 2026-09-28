"""M7: custom recognizers for Indian formats, matched by SHAPE only (fail closed).

What it demonstrates: a Presidio "recognizer" can be as simple as a named regex.
Presidio ships PAN and Aadhaar recognizers, but they only fire on numbers that
pass a checksum or sit near words like "aadhaar". For privacy that's backwards:
a real number with one typo is still someone's number. These match the shape
alone, so anything that LOOKS like an ID is masked (DECISIONS.md D6).

Each regex is written out below with what it matches, so you can test it by eye.
"""

import re

from presidio_analyzer import Pattern, PatternRecognizer

# (entity, regex, score). Scores only matter when two findings cover the same text: the
# higher one names the mask. Exact Indian shapes get 1.0 so they beat Presidio's date guesses
# ("98765-43210" also looks like a date to it); the catch-all stays low.
SHAPES = [
    # +91 98765 43210 / 0091-9876543210 / 09876543210 / 98765-43210: 10 digits starting 6-9
    ("IN_PHONE", r"(?<!\d)(?:(?:\+|00)91[\s-]?|0)?[6-9]\d{4}[\s-]?\d{5}(?!\d)", 1.0),
    # 1234 5678 9012 / 1234-5678-9012 / 123456789012: 12 digits, checksum NOT required
    ("IN_AADHAAR", r"(?<!\d)\d{4}[\s-]?\d{4}[\s-]?\d{4}(?!\d)", 1.0),
    # ABCPE1234F: 5 letters, 4 digits, 1 letter (any case, via Presidio's IGNORECASE flag)
    ("IN_PAN", r"\b[A-Z]{5}\d{4}[A-Z]\b", 1.0),
    # rahul.v@okaxis / 9876543210@ybl: like an email, but the part after @ has no dot
    ("IN_UPI", r"\b[\w.\-]{2,256}@[A-Z][A-Z0-9]{1,63}\b(?!\.)", 1.0),
    # Catch-all: any run of 8+ digits, single spaces/hyphens allowed between them
    ("LONG_NUMBER", r"(?<!\d)\d(?:[\s-]?\d){7,}(?!\d)", 0.3),
]

# The shapes that must never survive redaction; redactor.py re-checks its output with these.
LEAK_CHECKS = {name: re.compile(regex) for name, regex, _ in SHAPES if name in ("IN_PHONE", "IN_AADHAAR", "LONG_NUMBER")}


def india_recognizers() -> list[PatternRecognizer]:
    """One Presidio PatternRecognizer per shape above."""
    return [
        PatternRecognizer(supported_entity=name, name=f"Pseudo{name.title().replace('_', '')}Recognizer",
                          patterns=[Pattern(name=name.lower(), regex=regex, score=score)])
        for name, regex, score in SHAPES
    ]
