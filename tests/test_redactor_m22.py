"""Tests for M22: a large names list from Wikidata (CC0, D22), looked up in a set. Every name is FAKE (name_cases.py).

The criteria, fixed before N6 was measured: R2 N6 held-out recall >= 90% (measured 99%); R3 first names alone
and initials on N1 + N6 >= 90% each (measured 100%). R5/R6 (no new over-masked lines) are test_redactor_m20.py's.
R10, word-level over-masking, had no threshold: the words it measured on O6 and N5 are pinned here as a CEILING,
so a rebuilt list that hides more ordinary words fails loudly instead of slipping through.
"""

import re
from pathlib import Path

import pytest

from name_cases import CONTEXTS, N1, N5, N6, N6_CAPS, O6, names
from pseudo_hands.build_names_list import HONORIFICS, LEFT_OUT
from pseudo_hands.core import name_recognizers, redactor
from pseudo_hands.core.redactor import RedactionError, redact

# Every word masked on O6 and N5 when M22 was measured (spaCy, the hand list and the Wikidata list together).
O6_MASKED_M22 = {"Aarti", "Andolan", "Ashoka", "Bachao", "Bahubali", "Balaji", "Bharat", "Bhavan", "Chennai", "Gandhi",
                 "Ganga", "Golden", "India", "Indian", "Indians", "Jayanti", "Kalki", "Kerala", "Mahal", "Meenakshi",
                 "Mumbai", "Narmada", "Saravana", "Sundaram", "Taj", "Temple", "Tirupati", "Udupi", "Vande"}
N5_MASKED_M22 = {"Aditya", "Arjun", "Baba", "Birla", "Capital", "Dhan", "Ganesh", "Gita", "Hari", "Jewellers", "Kalyan",
                 "Krishna", "Lakshmi", "Prem", "Ratan", "River", "Sahasranamam", "Sai", "Temple", "Uday", "Vilas", "Vishnu"}
WORD = re.compile(r"[A-Za-z][A-Za-z']*")


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


def masked_words(lines: list[str]) -> set[str]:
    return {word for line in lines for word in set(WORD.findall(line)) - set(WORD.findall(redact(line)))}


def test_r2_held_out_recall_on_n6_is_at_least_90_percent() -> None:
    assert recall(names(N6) + N6_CAPS) >= 0.90


@pytest.mark.parametrize("group", ["first name only", "initials"])
def test_r3_first_names_alone_and_initials_on_n1_and_n6(group: str) -> None:
    assert recall(N1[group] + N6[group]) >= 0.90


def test_the_large_list_is_cc0_and_has_both_sections() -> None:
    header = name_recognizers.LARGE_NAMES_FILE.read_text(encoding="utf-8")[:2000]
    assert "CC0" in header and "Wikidata" in header
    first, last = name_recognizers.load_names(name_recognizers.LARGE_NAMES_FILE)
    assert len(first) > 20_000 and len(last) > 10_000


def test_the_large_list_cannot_put_back_what_the_hand_list_leaves_out() -> None:
    first, last = name_recognizers.load_names(name_recognizers.LARGE_NAMES_FILE)
    assert not (set(first) | set(last)) & (LEFT_OUT | HONORIFICS)


def test_a_missing_large_list_fails_closed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(name_recognizers, "LARGE_NAMES_FILE", tmp_path / "missing.txt")
    redactor.build_analyzer.cache_clear()  # force a rebuild that must read the (missing) list
    try:
        with pytest.raises(RedactionError):
            redact("Chat with Amit Sharma")
    finally:
        redactor.build_analyzer.cache_clear()


@pytest.mark.parametrize("lines, ceiling", [(O6, O6_MASKED_M22), (N5, N5_MASKED_M22)], ids=["O6", "N5"])
def test_r10_ordinary_words_masked_stay_within_what_m22_measured(lines: list[str], ceiling: set[str]) -> None:
    assert masked_words(lines) <= ceiling


@pytest.mark.xfail(strict=True, reason="known cost (D22): a surname that is also an English word ('lone') is filtered out")
def test_a_surname_that_is_also_an_english_word_is_a_known_gap() -> None:
    assert caught("Irfan Lone", redact("Call Irfan Lone"))
