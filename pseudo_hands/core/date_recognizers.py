"""M19: dates and ages found by PATTERN, replacing spaCy's date guesses (D19).

What it demonstrates: picking the right tool for each kind of personal info. spaCy's
named-entity model (NER) is good at names, but for dates it guessed. It masked times
("10:30"), weekdays ("Monday") and plain numbers ("order 4471", read as a year). A date
only matters for privacy when it could be a birthday, and a birthday has a SHAPE, which a
regex never misses. So redactor.py switches spaCy's DATE and TIME labels off, and:
  - Presidio's own DateRecognizer keeps catching numeric dates (12.03.1998, 1998-03-12, 05/11);
  - this file adds the shapes Presidio doesn't know, written out below so you can test them by eye.
No longer masked: times, weekdays, relative words ("tomorrow"), bare numbers, and a year
with no birth word next to it. None of those says who a person is on its own.
"""

import re

from presidio_analyzer import Pattern, PatternRecognizer

MONTH = (r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?"
         r"|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)")
DAY = r"(?:[12]\d|3[01]|0?[1-9])(?:st|nd|rd|th)?"  # 1-31, optionally 1st/2nd/3rd/4th...
DAY_WORD = (r"(?:(?:(?:twenty|thirty)[\s-]?)?(?:first|second|third|fourth|fifth|sixth|seventh|eighth|ninth)"
            r"|tenth|eleventh|twelfth|thirteenth|fourteenth|fifteenth|sixteenth|seventeenth|eighteenth"
            r"|nineteenth|twentieth|thirtieth)")
YEAR = r"(?:19|20)\d{2}"
BIRTH_WORD = r"(?:born|birth\s*(?:day|date|year)?|date\s+of\s+birth|d\.?o\.?b\.?)"

# (entity, name, regex). Presidio matches these ignoring case.
SHAPES = [
    # 3 March / 3rd March 1998 / 15 August / the third of March 1998: a day, then a month name
    ("DATE_TIME", "day_month", rf"\b(?:the\s+)?(?:{DAY}|{DAY_WORD})\s+(?:of\s+)?{MONTH}\b(?:,?\s+{YEAR}\b)?"),
    # March 3 / Mar 3rd, 1998: a month name, then a day ("March 2026" has no day, so it's not matched)
    ("DATE_TIME", "month_day", rf"\b{MONTH}\.?\s+{DAY}\b(?:,?\s+{YEAR}\b)?"),
    # 12/03/1998 / 12-03-1998 / 12.03.1998 / 1998-03-12: numeric, always with a 4-digit year
    ("DATE_TIME", "numeric_date", rf"\b(?:\d{{1,2}}[/.\-]\d{{1,2}}[/.\-]{YEAR}|{YEAR}[/.\-]\d{{1,2}}[/.\-]\d{{1,2}})\b"),
    # born in 1998 / DOB: 1998 / birth year 1998: a year right after a birth word
    ("DATE_TIME", "birth_year", rf"\b{BIRTH_WORD}[\s:,\-]*(?:in\s+|on\s+)?{YEAR}\b"),
    # 34 years old / 34-year-old / 34 yrs old / age 34 / aged: 34
    ("AGE", "age", r"\b\d{1,3}[\s-]?(?:years?|yrs?)[\s-]?old\b|\b(?:age|aged)\s*:?\s*\d{1,3}\b"),
]

# Numeric full dates must never survive redaction; redactor.py re-checks its output with this.
DATE_LEAK_CHECKS = {"numeric date": re.compile(SHAPES[2][2], re.IGNORECASE)}


def date_recognizers() -> list[PatternRecognizer]:
    """One Presidio PatternRecognizer per shape above (score 0.85, what spaCy's guesses had)."""
    return [
        PatternRecognizer(supported_entity=entity, name=f"Pseudo{name.title().replace('_', '')}Recognizer",
                          patterns=[Pattern(name=name, regex=regex, score=0.85)])
        for entity, name, regex in SHAPES
    ]
