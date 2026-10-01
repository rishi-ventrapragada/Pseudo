"""Tests for M19: the redactor stops masking ordinary text, without weakening real detection (D19).

Every input is FAKE, from redaction_cases.py: the sets were fixed before the fix was measured.
"""

from pathlib import Path

import pytest
from presidio_analyzer import RecognizerResult

from pseudo_hands.core import redactor
from pseudo_hands.core.finding_filters import is_weak_plate, trim_codes
from pseudo_hands.core.redactor import RedactionError, redact
from redaction_cases import GUARDS, KNOWN_LEAKS, ORDINARY, ORDINARY_LINES, RESIDUALS, SENSITIVE


@pytest.fixture(autouse=True)
def empty_terms(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The owner's real private terms are never read by tests."""
    terms = tmp_path / "redaction_terms.txt"
    terms.write_text("# no terms\n", encoding="utf-8")
    monkeypatch.setattr(redactor, "TERMS_FILE", terms)


def leaked(text: str, secrets: list[str]) -> list[str]:
    out = redact(text).lower()
    return [secret for secret in secrets if secret.lower() in out]


# ---------- P1: every sensitive fake case from M7-M18 is still fully masked ----------

@pytest.mark.parametrize("text, secrets", SENSITIVE)
def test_every_earlier_sensitive_case_is_still_masked(text: str, secrets: list[str]) -> None:
    assert leaked(text, secrets) == []


# ---------- change 1: dates and ages by pattern, not spaCy's guesses ----------

@pytest.mark.parametrize("text, secrets", GUARDS["birth dates"] + GUARDS["ages"])
def test_birth_dates_and_ages_are_masked(text: str, secrets: list[str]) -> None:
    assert leaked(text, secrets) == []


def test_a_numeric_birth_date_survives_presidios_duplicate_removal() -> None:
    # The trap: on "12/03/1998" spaCy's guess (0.85) used to win over Presidio's date pattern (0.6),
    # so dropping spaCy's findings afterwards would have unmasked it. Our own pattern catches it.
    assert redact("DOB 12/03/1998") == "DOB [DATE_TIME]"


def test_spacy_makes_no_date_guesses_any_more() -> None:
    findings = redactor.find_personal_info("Standup at 10:30 on Monday, order 4471, due tomorrow")
    assert findings == []


@pytest.mark.parametrize("line, token", ORDINARY["times"] + ORDINARY["weekdays and relative dates"]
                         + [("Notes: order 4471 shipped", "4471"), ("Build 2041 failed", "2041")])
def test_times_weekdays_and_bare_numbers_survive(line: str, token: str) -> None:
    assert token in redact(line)


@pytest.mark.parametrize("line", ["March 2026 planner", "Release v1.2.10", "Python 3.11 setup guide"])
def test_a_month_without_a_day_and_version_numbers_survive(line: str) -> None:
    assert redact(line) == line


def test_a_year_is_masked_only_next_to_a_birth_word() -> None:
    assert redact("Build 2041 failed") == "Build 2041 failed"
    assert "1998" not in redact("Born in 1998") and "1998" not in redact("DOB: 1998")


def test_may_the_word_can_look_like_may_the_month() -> None:
    # Accepted over-masking, failing closed: "may 3" has the shape of a date.
    assert redact("You may 3 times") == "You [DATE_TIME] times"


def test_a_numeric_date_left_after_masking_is_a_leak(monkeypatch: pytest.MonkeyPatch) -> None:
    class DoesNothing:  # an anonymizer bug that returns the input unchanged
        def anonymize(self, text: str, **_ignored) -> object:
            return type("Result", (), {"text": text})()
    monkeypatch.setattr(redactor, "build_anonymizer", DoesNothing)
    with pytest.raises(RedactionError):
        redact("DOB 12/03/1998")


@pytest.mark.parametrize("text, secrets", GUARDS["names next to codes and times"])
def test_names_next_to_codes_and_times_are_still_masked(text: str, secrets: list[str]) -> None:
    assert leaked(text, secrets) == []


# ---------- change 2: code-shaped words are never names ----------

def trimmed(text: str, entity: str = "PERSON") -> str | None:
    """trim_codes on a fake finding that covers the whole text; the text that stays masked."""
    result = trim_codes(text, RecognizerResult(entity, 0, len(text), 0.85))
    return None if result is None else text[result.start:result.end]


def test_a_finding_made_only_of_codes_is_dropped() -> None:
    assert trimmed("M15") is None and trimmed("A-20931") is None and trimmed("CS101 21CS42") is None


def test_codes_are_trimmed_off_the_edges_and_the_name_stays_masked() -> None:
    assert trimmed("Q3 OKR") == "OKR"
    assert trimmed("Rahul Verma M15") == "Rahul Verma"
    assert trimmed("ECE-2 section", "NRP") == "section"


@pytest.mark.parametrize("text", ["Rahul M15 Verma", "rahul99", "Rahul99", "M15,"])
def test_a_code_in_the_middle_handles_and_glued_punctuation_stay_masked(text: str) -> None:
    assert trimmed(text) == text


def test_locations_are_never_trimmed() -> None:
    assert trimmed("B-204 Sunrise Apartments", "LOCATION") == "B-204 Sunrise Apartments"


@pytest.mark.parametrize("line", ["Pseudo M15 notes", "Pseudo M15 target", "Order #A-20931 tracking"])
def test_lines_with_codes_are_no_longer_masked(line: str) -> None:
    assert redact(line) == line


# ---------- change 3: Presidio's weak vehicle-plate shapes are ignored ----------

@pytest.mark.parametrize("line", ["MA2201 assignment 3", "CSE1001 lab", "A1234 form"])
def test_course_codes_shaped_like_old_plates_survive(line: str) -> None:
    assert redact(line) == line


@pytest.mark.parametrize("text, plate", [("Vehicle MH12AB1234 parked", "MH12AB1234"), ("Plate 22BH1234AA", "22BH1234AA"),
                                         ("Vehicle no. DL1234 parked", "DL1234")])  # a weak shape WITH context
def test_full_plates_and_plates_with_context_are_still_masked(text: str, plate: str) -> None:
    assert plate not in redact(text)


def test_only_weak_plate_findings_are_dropped() -> None:
    assert is_weak_plate(RecognizerResult("IN_VEHICLE_REGISTRATION", 0, 6, 0.2))
    assert not is_weak_plate(RecognizerResult("IN_VEHICLE_REGISTRATION", 0, 10, 0.4))
    assert not is_weak_plate(RecognizerResult("PERSON", 0, 5, 0.01))


# ---------- the fixed criteria, all three changes together ----------

@pytest.mark.parametrize("line, token", [(line, token) for line, token in ORDINARY_LINES if token])
def test_p3_every_ordinary_token_survives(line: str, token: str) -> None:
    assert token in redact(line)


def test_p4_at_least_37_of_41_ordinary_lines_are_unchanged() -> None:
    assert len(ORDINARY_LINES) == 41
    assert sum(redact(line) == line for line, _ in ORDINARY_LINES) >= 37


@pytest.mark.parametrize("text, secrets", [case for cases in GUARDS.values() for case in cases])
def test_p2_every_guard_is_masked(text: str, secrets: list[str]) -> None:
    assert leaked(text, secrets) == []


@pytest.mark.xfail(strict=True, reason="known over-masking left after M19 (spaCy NER guesses), named in advance")
@pytest.mark.parametrize("line", RESIDUALS)
def test_known_residuals(line: str) -> None:
    assert redact(line) == line


@pytest.mark.parametrize("text, secrets", KNOWN_LEAKS)
def test_the_name_leaks_found_in_m19_are_fixed(text: str, secrets: list[str]) -> None:  # fixed by M20's names list
    assert leaked(text, secrets) == []
