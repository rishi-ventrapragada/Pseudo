"""Tests for M20: common Indian names are masked from a committed list (D21). Every name is FAKE (name_cases.py).

The criteria, as finally approved: R1 N1 recall 100%; R2 held-out recall >= 90% was MISSED in M20 (86%) and
passes since M22's Wikidata list (N2 is spent by now, so test_redactor_m22.py's N6 is the real check);
R3 first names alone and initials >= 90%;
R5 cue phrases no worse than before M20 (2/16); R6 no new over-masking versus before M20.
"""

import re
from pathlib import Path

import pytest

from name_cases import CONTEXTS, CUE_PHRASES, LOWERCASE, N1, N2, N2_CAPS, N3_FESTIVALS, N3_ORDINARY, names
from pseudo_hands.core import name_recognizers, redactor
from pseudo_hands.core.redactor import RedactionError, redact

# Over-masked by spaCy alone before M20 (measured): the list must add none to these.
N3_BEFORE_M20 = {"Jasmine tests passing", "Bill payment due", "Amar Chitra Katha comics", "Raja Rani serial episode 5"}
CUE_BEFORE_M20 = {"Built with React", "Meeting with Team Alpha"}


@pytest.fixture(autouse=True)
def empty_terms(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The owner's real private terms are never read by tests."""
    terms = tmp_path / "redaction_terms.txt"
    terms.write_text("# no terms\n", encoding="utf-8")
    monkeypatch.setattr(redactor, "TERMS_FILE", terms)


def caught(name: str, out: str) -> bool:
    """Every word of the name with 2+ letters is masked (a lone initial identifies nobody)."""
    return not any(re.search(rf"\b{word}\b", out) for word in re.findall(r"[A-Za-z]+", name) if len(word) >= 2)


def recall(name_list: list[str]) -> float:
    cases = [(name, context.format(n=name)) for name in name_list for context in CONTEXTS]
    return sum(caught(name, redact(text)) for name, text in cases) / len(cases)


def test_r1_every_name_in_n1_is_masked_in_every_context() -> None:
    assert recall(names(N1)) == 1.0


def test_r2_held_out_recall_is_at_least_90_percent() -> None:  # missed in M20 (86%), passes since M22
    assert recall(names(N2) + N2_CAPS) >= 0.90


@pytest.mark.parametrize("group", ["first name only", "initials"])
def test_r3_first_names_alone_and_initials(group: str) -> None:
    assert recall(N1[group] + N2[group]) >= 0.90


def test_r5_cue_phrases_are_no_worse_than_before() -> None:
    assert {line for line in CUE_PHRASES if redact(line) != line} <= CUE_BEFORE_M20


def test_r6_no_new_over_masking_of_words_that_are_also_names() -> None:
    assert {line for line in N3_ORDINARY if redact(line) != line} <= N3_BEFORE_M20


def test_festival_names_are_masked_failing_closed() -> None:
    assert redact("Durga Puja holidays") == "[PERSON] holidays"  # since M22 "Puja" is a Wikidata surname too
    assert all(redact(line) != line for line in N3_FESTIVALS)


@pytest.mark.parametrize("text, hidden", [("Keerthana Boddu", "Keerthana"), ("YASHWANTH CHOWDARY", "CHOWDARY"),
                                          ("Call Yashwanth Chowdary", "Yashwanth"), ("Sent by M.S. Reddy", "Reddy")])
def test_the_three_list_rules(text: str, hidden: str) -> None:
    assert hidden not in redact(text)  # listed name / ALL CAPS / word before a listed surname / initials


@pytest.mark.xfail(strict=True, reason="known gap (D21): the list matches Capitalized and ALL CAPS only")
def test_lowercase_names_are_a_known_gap() -> None:
    assert caught(LOWERCASE[0], redact(f"Call {LOWERCASE[0]}"))


def test_a_missing_or_broken_names_list_fails_closed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    broken = tmp_path / "names.txt"
    broken.write_text("Amit, Priya\n", encoding="utf-8")  # no [first names] section
    with pytest.raises(ValueError):
        name_recognizers.load_names(broken)
    monkeypatch.setattr(name_recognizers, "NAMES_FILE", tmp_path / "missing.txt")
    redactor.build_analyzer.cache_clear()  # force a rebuild that must read the (missing) list
    try:
        with pytest.raises(RedactionError):
            redact("Chat with Amit Sharma")
    finally:
        redactor.build_analyzer.cache_clear()
