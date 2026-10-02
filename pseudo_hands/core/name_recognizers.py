"""M20: Indian names the redactor must know, from a committed list (D21). M22: looked up in a set.

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

M22: how the rules find names. M20 built one big regex per rule ("Amit|AMIT|Anil|..."). Python
tries those alternatives one by one, so 50,000 names took 12 s to compile and 17 ms per title.
Now each rule's regex only finds name-SHAPED words (Capitalized or ALL CAPS), and a set says
whether the word is listed: a hash lookup, like Set.has() in JS, equally fast for 500 or 150,000 names.
"""

import re
from pathlib import Path

from presidio_analyzer import EntityRecognizer, RecognizerResult

NAMES_FILE = Path(__file__).resolve().parent / "indian_names.txt"
SECTIONS = ("[first names]", "[surnames]")
SCORE = 0.85

# A name-shaped word: Capitalized ("Amit") or ALL CAPS ("AMIT"), with an optional "D'" prefix ("D'Souza").
WORD = r"(?:[A-Z]')?(?:[A-Z][a-z]+|[A-Z]{2,})"
INITIALS = r"(?:[A-Z]\.\s?){1,3}"  # "S." / "M.S." / "G. K."
# Each shape names the whole span to mask (<span>) and the word to look up (<name>). The (?=...)
# lookahead lets matches overlap, so a rejected candidate can't hide a real one right after it.
SHAPES = {
    "listed_name": rf"(?=(?P<span>\b(?P<name>{WORD})\b))",
    "initials_before_name": rf"(?=(?P<span>\b{INITIALS}\s?(?P<name>{WORD})\b))",
    "initial_after_name": rf"(?=(?P<span>\b(?P<name>{WORD})\s+[A-Z]\.(?!\w)))",
    "word_before_surname": rf"(?=(?P<span>\b(?:[A-Z][a-z]+|[A-Z]{{2,}})\s+(?P<name>{WORD})\b))",
}


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


def either_case(names: list[str]) -> frozenset[str]:
    """Each name as written (Title Case) and in ALL CAPS: the only two forms that count."""
    return frozenset(form for name in names for form in (name, name.upper()))


class ListedNameRecognizer(EntityRecognizer):
    """One rule: every match of `shape` whose <name> word is in `listed` is reported as PERSON."""

    def __init__(self, rule: str, shape: str, listed: frozenset[str]) -> None:
        self.shape, self.listed = re.compile(shape), listed
        super().__init__(supported_entities=["PERSON"], name=f"PseudoName{rule.title().replace('_', '')}Recognizer")

    def load(self) -> None:
        """Nothing to load: the names were read in name_recognizers()."""

    def analyze(self, text: str, entities: list[str], nlp_artifacts: object = None) -> list[RecognizerResult]:
        found = []
        for match in self.shape.finditer(text):
            if match.group("name") in self.listed:
                found.append(RecognizerResult("PERSON", match.start("span"), match.end("span"), SCORE,
                                              recognition_metadata={RecognizerResult.RECOGNIZER_NAME_KEY: self.name,
                                                                    RecognizerResult.RECOGNIZER_IDENTIFIER_KEY: self.id}))
        return found


def name_recognizers(path: Path | None = None) -> list[EntityRecognizer]:
    """The three rules above, as Presidio recognizers that report PERSON (from NAMES_FILE unless told otherwise)."""
    first, last = load_names(path or NAMES_FILE)
    any_name, surname = either_case(first + last), either_case(last)
    wanted = {"listed_name": any_name, "initials_before_name": any_name, "initial_after_name": any_name,
              "word_before_surname": surname}
    return [ListedNameRecognizer(rule, shape, wanted[rule]) for rule, shape in SHAPES.items()]
