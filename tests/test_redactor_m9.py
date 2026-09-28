"""Tests for the M9 redactor fixes. Every input here is FAKE.

Split out of test_redactor.py (200-line limit). Covers: a UPI ID at the end of a
sentence, the word@word leak check, US-only recognizers switched off, Indian places.
"""

from pathlib import Path

import pytest

from pseudo_hands.core import redactor
from pseudo_hands.core.redactor import RedactionError, redact


@pytest.fixture(autouse=True)
def empty_terms(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The owner's real private terms are never read by tests."""
    terms = tmp_path / "redaction_terms.txt"
    terms.write_text("# no terms\n", encoding="utf-8")
    monkeypatch.setattr(redactor, "TERMS_FILE", terms)


# ---------- M9 fixes: UPI at a sentence end, word@word catch-all, US-only off, Indian places ----------

def test_a_upi_id_at_the_end_of_a_sentence_is_masked() -> None:
    out = redact("Notes: PAN on file. UPI rahul.v@okaxis. Aadhaar pending.")
    assert "okaxis" not in out and "[IN_UPI]" in out


def test_any_word_at_word_left_after_masking_is_a_leak(monkeypatch: pytest.MonkeyPatch) -> None:
    class LeavesAnAtToken:  # an anonymizer bug that leaves "someone@corp" behind
        def anonymize(self, text: str, **_ignored) -> object:
            return type("Result", (), {"text": "contact someone@corp"})()
    monkeypatch.setattr(redactor, "build_anonymizer", LeavesAnAtToken)
    with pytest.raises(RedactionError):
        redact("contact the team")


def test_us_only_recognizers_are_off_but_long_ids_are_still_masked() -> None:
    assert redact("Pseudo M9 test") == "Pseudo M9 test"  # was [US_DRIVER_LICENSE]
    assert not any(ch.isdigit() for ch in redact("Ref 123-45-6789 on file"))  # SSN-shaped: LONG_NUMBER


@pytest.mark.parametrize("place", ["Pune", "Maharashtra", "navi mumbai", "Tamil Nadu"])
def test_indian_places_are_masked(place: str) -> None:
    out = redact(f"Office in {place}")
    assert place.lower() not in out.lower() and "[LOCATION]" in out
    # next to a date-ish phrase a bigger [DATE_TIME] span may win the label, but it is still masked:
    assert place.lower() not in redact(f"Meeting in {place} next week").lower()


def test_a_missing_places_list_fails_closed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(redactor, "PLACES_FILE", tmp_path / "missing.txt")
    redactor.build_analyzer.cache_clear()  # force a rebuild that must read the (missing) list
    try:
        with pytest.raises(RedactionError):
            redact("Meeting in Pune")
    finally:
        redactor.build_analyzer.cache_clear()  # later tests rebuild with the real list
