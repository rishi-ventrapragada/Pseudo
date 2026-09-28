"""Tests for M7: redact(). Every input here is FAKE: invented names, numbers and IDs.

The first test that runs loads spaCy (a few seconds); later tests reuse the cached engine.
"""

import socket
from pathlib import Path

import pytest

from pseudo_hands.core import redactor
from pseudo_hands.core.redactor import RedactionError, redact


@pytest.fixture(autouse=True)
def empty_terms(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Every test gets its own empty terms file; the owner's real list is never read."""
    terms = tmp_path / "redaction_terms.txt"
    terms.write_text("# no terms\n", encoding="utf-8")
    monkeypatch.setattr(redactor, "TERMS_FILE", terms)
    return terms


# Verhoeff check digit (the checksum Aadhaar uses), so we can build a checksum-VALID fake.
_D = [[0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 2, 3, 4, 0, 6, 7, 8, 9, 5], [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
      [3, 4, 0, 1, 2, 8, 9, 5, 6, 7], [4, 0, 1, 2, 3, 9, 5, 6, 7, 8], [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
      [6, 5, 9, 8, 7, 1, 0, 4, 3, 2], [7, 6, 5, 9, 8, 2, 1, 0, 4, 3], [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
      [9, 8, 7, 6, 5, 4, 3, 2, 1, 0]]
_P = [[0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 5, 7, 6, 2, 8, 3, 0, 9, 4], [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
      [8, 9, 1, 6, 0, 4, 3, 5, 2, 7], [9, 4, 5, 3, 1, 2, 6, 8, 7, 0], [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
      [2, 7, 9, 3, 8, 0, 6, 4, 1, 5], [7, 0, 4, 6, 9, 1, 3, 2, 5, 8]]
_INV = [0, 4, 3, 2, 1, 5, 6, 7, 8, 9]


def with_verhoeff_digit(first_eleven: str) -> str:
    check = 0
    for i, digit in enumerate(reversed(first_eleven)):
        check = _D[check][_P[(i + 1) % 8][int(digit)]]
    return first_eleven + str(_INV[check])


# ---------- what gets masked ----------

def test_global_patterns_are_masked() -> None:
    text = "Mail a.b@example.com, card 4111 1111 1111 1111, host 192.168.10.20, see https://example.org/x"
    out = redact(text)
    for secret in ["a.b@example.com", "4111", "192.168.10.20", "example.org"]:
        assert secret not in out


def test_names_are_masked() -> None:
    assert "Rahul" not in redact("Chat with Rahul Verma about the invoice")


@pytest.mark.parametrize("phone", ["+91 98765 43210", "+91-9876543210", "09876543210", "98765-43210"])
def test_indian_phone_numbers_are_masked(phone: str) -> None:
    out = redact(f"Call me on {phone} tomorrow")
    assert "[IN_PHONE]" in out and "98765" not in out and "43210" not in out


def test_aadhaar_is_masked_with_or_without_a_valid_checksum() -> None:
    valid = with_verhoeff_digit("23456789012")
    invalid = valid[:-1] + str((int(valid[-1]) + 1) % 10)  # one digit off: checksum now fails
    for number in (valid, invalid):
        spaced = f"{number[:4]} {number[4:8]} {number[8:]}"
        assert redact(f"Aadhaar {spaced}") == "Aadhaar [IN_AADHAAR]"


@pytest.mark.parametrize("pan", ["ABCPE1234F", "abcpe1234f"])
def test_pan_is_masked_in_any_case(pan: str) -> None:
    assert redact(f"PAN {pan}") == "PAN [IN_PAN]"


def test_upi_and_email_are_told_apart_and_both_masked() -> None:
    out = redact("Pay rahul.v@okaxis or 9876543210@ybl, receipt to a.b@example.com")
    assert "[IN_UPI]" in out and "[EMAIL_ADDRESS]" in out
    assert "okaxis" not in out and "ybl" not in out and "example.com" not in out


@pytest.mark.parametrize("number", ["123456789012345", "12-3456-7890"])
def test_long_numbers_are_masked(number: str) -> None:
    assert not any(ch.isdigit() for ch in redact(f"Ref {number}"))


def test_private_terms_are_masked_as_whole_words(empty_terms: Path) -> None:
    empty_terms.write_text("# fake private terms\nZorblax Industries\n", encoding="utf-8")
    assert redact("Contract with zorblax industries") == "Contract with [PRIVATE]"
    assert redact("The Zorblax Industriesque style") == "The Zorblax Industriesque style"


# ---------- over-masking: ordinary titles should survive ----------

@pytest.mark.parametrize("title", ["Untitled - Notepad", "Task Manager", "Downloads - File Explorer",
                                   "Discover Weekly - Spotify", "Supabase Dashboard - Google Chrome",
                                   "notes.md - Notepad", "main.py - Pseudo - Visual Studio Code",
                                   "New Tab - Google Chrome", "Windows PowerShell"])
def test_ordinary_titles_are_unchanged(title: str) -> None:
    assert redact(title) == title


# ---------- the allowlist (M8): exempts app names, never personal info ----------

def test_a_name_that_is_also_an_app_is_still_masked() -> None:
    # "Claude" (and "Hermes") are deliberately NOT allowlisted: they are first names too.
    assert "Claude" not in redact("Chat with Claude Martin") and "Martin" not in redact("Chat with Claude Martin")


def test_personal_info_next_to_an_allowed_name_is_masked() -> None:
    out = redact("Chat with Rahul Verma, +91 98765 43210 - WhatsApp Web - Google Chrome")
    assert out.endswith("WhatsApp Web - Google Chrome")  # a separator next to a mask may be absorbed
    assert "Rahul" not in out and "98765" not in out


@pytest.mark.parametrize("glued", ["notepad@okaxis", "github.com/someone", "spotify.example.org"])
def test_an_allowed_name_glued_into_a_bigger_token_is_not_exempted(glued: str) -> None:
    assert glued not in redact(f"Open {glued} - Google Chrome")


def test_a_private_term_beats_the_allowlist(empty_terms: Path) -> None:
    empty_terms.write_text("Zorblax Notepad Plan\n", encoding="utf-8")  # contains an allowed name
    assert redact("Zorblax Notepad Plan - Notepad") == "[PRIVATE] - Notepad"


def test_a_missing_allowlist_fails_closed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(redactor, "ALLOWED_NAMES_FILE", tmp_path / "missing.txt")
    with pytest.raises(RedactionError):
        redact("New Tab - Google Chrome")


def test_real_web_addresses_are_still_masked() -> None:
    out = redact("see example.org, www.example.net and github.com/someone")
    assert "example.org" not in out and "example.net" not in out and "someone" not in out


@pytest.mark.xfail(strict=True, reason="known over-masking (M8 lesson): spaCy tags 'Lofi' as a person")
@pytest.mark.parametrize("title", ["Lofi hip hop radio - beats to relax/study to - YouTube - Google Chrome"])
def test_known_false_positives(title: str) -> None:
    assert redact(title) == title


# ---------- fail closed ----------

def test_a_missing_terms_file_fails_closed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(redactor, "TERMS_FILE", tmp_path / "missing.txt")
    with pytest.raises(RedactionError):
        redact("Chat with Rahul Verma")


def test_an_engine_failure_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken() -> None:
        raise OSError("model files missing")
    monkeypatch.setattr(redactor, "build_analyzer", broken)
    with pytest.raises(RedactionError) as caught:
        redact("Call +91 98765 43210")
    assert "98765" not in str(caught.value)  # the error message never carries the text


def test_a_leak_after_masking_is_caught(monkeypatch: pytest.MonkeyPatch) -> None:
    class DoesNothing:  # an anonymizer bug that returns the input unchanged
        def anonymize(self, text: str, **_ignored) -> object:
            return type("Result", (), {"text": text})()
    monkeypatch.setattr(redactor, "build_anonymizer", DoesNothing)
    with pytest.raises(RedactionError):
        redact("Call +91 98765 43210")


def test_redaction_works_with_the_network_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    def no_network(*_args, **_kwargs) -> None:
        raise OSError("network blocked by test")
    monkeypatch.setattr(socket.socket, "connect", no_network)
    redactor.build_analyzer.cache_clear()  # rebuild the engine too, with no network available
    assert redact("Mail a.b@example.com or visit https://example.org") == "Mail [EMAIL_ADDRESS] or visit [URL]"


def test_edge_cases() -> None:
    assert redact("") == ""
    with pytest.raises(TypeError):
        redact(None)  # type: ignore[arg-type]
