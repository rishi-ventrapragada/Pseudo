"""M20: Indian names the redactor must know, from a committed list (D21).

What it demonstrates: a GAZETTEER (a plain list of known names) next to a statistical model.
spaCy's small English model learned names from English text, and missed 39% of fake Indian
names in window titles (M20). A list can't miss a name that's on it, and you can read every
entry in git. Three rules, all case-sensitive, so a name counts only when it's Capitalized or
in ALL CAPS ("ram usage" and "pooja holidays" written in lower case stay visible):
  1. a listed first name or surname, as a whole word:   "Amit", "SHARMA"
  2. initials next to a listed name:                    "S. Ramesh", "M.S. Reddy", "Ramesh S."
  3. any Capitalized word right before a listed SURNAME: "Yashwanth Chowdary" (even if Yashwanth isn't listed)
Why it can't cause a leak: it only ADDS findings, and spaCy still masks every name it finds.
Its risk is over-masking (a listed name used as an ordinary word), which M20 measured.
"""

import re
from pathlib import Path

from presidio_analyzer import Pattern, PatternRecognizer

NAMES_FILE = Path(__file__).resolve().parent / "indian_names.txt"
SECTIONS = ("[first names]", "[surnames]")
FLAGS = re.DOTALL | re.MULTILINE  # Presidio's default adds IGNORECASE; leaving it out keeps lower case visible
INITIALS = r"(?:[A-Z]\.\s?){1,3}"  # "S." / "M.S." / "G. K."


def load_names(path: Path) -> tuple[list[str], list[str]]:
    """(first names, surnames). Raises OSError or ValueError if the list can't be used (redact() then fails closed)."""
    found: dict[str, list[str]] = {section: [] for section in SECTIONS}
    section = None
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        if line in SECTIONS:
            section = line
        elif section is None:
            raise ValueError("a name before [first names] or [surnames]")
        else:
            found[section] += [name.strip() for name in line.split(",") if name.strip()]
    if not all(found.values()):
        raise ValueError("the names list needs both sections, each with names")
    return found["[first names]"], found["[surnames]"]


def either_case(names: list[str]) -> str:
    """Regex alternatives for each name as written (Title Case) and in ALL CAPS, longest first."""
    forms = sorted({form for name in names for form in (name, name.upper())}, key=len, reverse=True)
    return "|".join(re.escape(form) for form in forms)


def name_recognizers(path: Path | None = None) -> list[PatternRecognizer]:
    """The three rules above, as Presidio recognizers that report PERSON (from NAMES_FILE unless told otherwise)."""
    first, last = load_names(path or NAMES_FILE)
    any_name, surname = either_case(first + last), either_case(last)
    shapes = [
        ("listed_name", rf"\b(?:{any_name})\b"),
        ("initials_and_name", rf"\b{INITIALS}\s?(?:{any_name})\b|\b(?:{any_name})\s+[A-Z]\.(?!\w)"),
        ("word_before_surname", rf"\b(?:[A-Z][a-z]+|[A-Z]{{2,}})\s+(?:{surname})\b"),
    ]
    return [PatternRecognizer(supported_entity="PERSON", name=f"PseudoName{name.title().replace('_', '')}Recognizer",
                              patterns=[Pattern(name=name, regex=regex, score=0.85)], global_regex_flags=FLAGS)
            for name, regex in shapes]
