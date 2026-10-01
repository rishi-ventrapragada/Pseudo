"""Tests for M19: the redactor stops masking ordinary text, without weakening real detection (D19).

Every input is FAKE, from redaction_cases.py: the sets were fixed before the fix was measured.
"""

from pathlib import Path

import pytest

from pseudo_hands.core import redactor
from pseudo_hands.core.redactor import RedactionError, redact
from redaction_cases import GUARDS, ORDINARY, SENSITIVE


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
