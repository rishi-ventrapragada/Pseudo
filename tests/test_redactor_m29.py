"""Tests for M29: the redactor never masks Pseudo's own control ids (an extension of D19).

Found in M29's structure check: read_active_window's outline is redacted as a whole, ids included, and
spaCy sometimes guessed an id like "c169" was a person ("RadioButton #[PERSON]: Pay now"). A masked id is
never registered, so no brain could act on that control. A sweep of c1-c3000 in five outline line shapes
found 702 masked (697 PERSON, 5 NRP). Every input here is FAKE.
"""

from pathlib import Path

import pytest
from presidio_analyzer import RecognizerResult

from pseudo_hands.core import redactor
from pseudo_hands.core.finding_filters import trim_codes
from pseudo_hands.core.redactor import redact

# Ids the sweep found masked before the fix, in at least one of these line shapes.
MASKED_BEFORE = [3, 7, 30, 132, 155, 169, 178, 196, 198, 279, 315, 332, 353, 381, 419, 480, 517, 613, 638,
                 713, 752, 786, 849, 962, 1012, 1157, 1172]
SHAPES = ["RadioButton #c{n}: Pay now", "Button #c{n}: Apply coupon", "CheckBox #c{n}: Text me updates",
          "Edit #c{n}: Subject"]


@pytest.fixture(autouse=True)
def empty_terms(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The owner's real private terms are never read by tests."""
    terms = tmp_path / "redaction_terms.txt"
    terms.write_text("# no terms\n", encoding="utf-8")
    monkeypatch.setattr(redactor, "TERMS_FILE", terms)


@pytest.mark.parametrize("shape", SHAPES)
def test_ids_masked_before_now_survive(shape: str) -> None:
    lost = [n for n in MASKED_BEFORE if f"#c{n}:" not in redact(shape.format(n=n))]
    assert lost == []


@pytest.mark.parametrize("text, secrets", [
    ("Button #c12: Call Rahul Verma", ["Rahul", "Verma"]),
    ("Edit #c7: Sneha Reddy", ["Sneha", "Reddy"]),
    ("CheckBox #c169: Remind Anil Kumar", ["Anil", "Kumar"]),
])
def test_names_next_to_an_id_are_still_masked(text: str, secrets: list[str]) -> None:
    out = redact(text)
    assert [secret for secret in secrets if secret in out] == []
    assert text.split(":")[0] in out  # the id itself survives


def kept(text: str) -> str | None:
    """trim_codes on a fake PERSON finding that covers the whole text; the text that stays masked."""
    result = trim_codes(text, RecognizerResult("PERSON", 0, len(text), 0.85))
    return None if result is None else text[result.start:result.end]


@pytest.mark.parametrize("text, expected", [
    ("c169", None),  # only an id: not a person at all
    ("c169:", None),  # the outline's colon came along once in 702
    ("c169 Anil Kumar", "Anil Kumar"),  # an id at the edge is trimmed off; the name stays masked
    ("Anil c169 Kumar", "Anil c169 Kumar"),  # in the middle: the whole finding stays masked
    ("rahul99", "rahul99"),  # not an id or a code: stays masked, as in M19
    ("C169", None),  # already code-shaped under M19's rule
])
def test_trim_codes_treats_a_control_id_like_a_code(text: str, expected: str | None) -> None:
    assert kept(text) == expected
