"""Tests for M4: list_open_windows() and the blocked-apps privacy check.

Most tests swap read_all_windows() for fake data (monkeypatch), so they don't
depend on what happens to be open on the desktop. One smoke test calls the real
Windows API, and it is written so a failure never prints real window titles.
"""

import json
import sys
from pathlib import Path

import pytest

from pseudo_hands.core import blocked_apps, windows
from pseudo_hands.core.blocked_apps import RESTRICTED, BlockedAppsError, load_blocked_apps, parse_blocked_apps
from pseudo_hands.core.redactor import RedactionError
from pseudo_hands.core.windows import TITLE_WITHHELD, RawWindow, list_open_windows

SECRET_TITLE = "Vault: bank PIN 4321"


def fake_window(title: str = "notes.md - Notepad", app: str | None = "notepad.exe", *,
                visible: bool = True, cloaked: bool = False, focused: bool = False) -> RawWindow:
    return RawWindow(title=title, app=app, visible=visible, cloaked=cloaked, focused=focused)


# ---------- what comes back ----------

def test_a_normal_window_passes_through(desktop) -> None:
    desktop([fake_window(focused=True)])
    assert list_open_windows() == [{"title": "notes.md - Notepad", "app": "notepad.exe", "focused": True}]


def test_hidden_cloaked_and_untitled_windows_are_dropped(desktop) -> None:
    desktop([fake_window(visible=False), fake_window(cloaked=True), fake_window(title="   "),
             fake_window(title="kept")])
    assert [w["title"] for w in list_open_windows()] == ["kept"]


# ---------- the blocked-apps check (D6) ----------

def test_a_blocked_app_is_masked_but_keeps_focus(desktop) -> None:
    desktop([fake_window(SECRET_TITLE, "KeePass.exe", focused=True)])
    assert list_open_windows() == [{"title": RESTRICTED, "app": RESTRICTED, "focused": True}]


def test_matching_ignores_case(desktop) -> None:
    desktop([fake_window(SECRET_TITLE, "keepass.EXE")])
    assert list_open_windows()[0]["title"] == RESTRICTED


def test_the_process_name_decides_not_the_title(desktop) -> None:
    desktop([fake_window("Home", "KeePass.exe"), fake_window("KeePass passwords.txt", "notepad.exe")])
    result = list_open_windows()
    assert result[0]["title"] == RESTRICTED  # harmless title, blocked program
    assert result[1]["title"] == "KeePass passwords.txt"  # scary title, allowed program


def test_an_unknown_app_is_masked(desktop) -> None:
    desktop([fake_window(SECRET_TITLE, app=None)])
    assert list_open_windows() == [{"title": RESTRICTED, "app": RESTRICTED, "focused": False}]


def test_no_blocked_text_leaks_anywhere_in_the_output(desktop) -> None:
    desktop([fake_window(SECRET_TITLE, "KeePass.exe"), fake_window(SECRET_TITLE, None), fake_window()])
    as_json = json.dumps(list_open_windows())  # what an MCP server would send to a model
    assert "4321" not in as_json and "Vault" not in as_json and "KeePass" not in as_json


# ---------- loading the list ----------

def test_list_parsing_skips_comments_blanks_and_spaces() -> None:
    text = "# header\n\n  KeePass.exe  \nSignal.exe # messaging\n   # indented comment\n"
    assert parse_blocked_apps(text) == {"keepass.exe", "signal.exe"}


def test_a_missing_list_returns_nothing_at_all(desktop, monkeypatch: pytest.MonkeyPatch,
                                               tmp_path: Path) -> None:
    desktop([fake_window()])
    monkeypatch.setattr(blocked_apps, "BLOCKED_APPS_FILE", tmp_path / "missing.txt")
    with pytest.raises(BlockedAppsError):
        list_open_windows()


def test_the_real_list_file_loads() -> None:
    assert "keepass.exe" in load_blocked_apps()


# ---------- the real Windows API ----------

@pytest.mark.skipif(sys.platform != "win32", reason="needs Windows")
def test_real_desktop_smoke() -> None:
    # Only counts and booleans in the asserts, so a failure can't print window titles.
    result = list_open_windows()
    assert isinstance(result, list)
    assert all(set(w) == {"title", "app", "focused"} for w in result)
    assert all(isinstance(w["title"], str) and isinstance(w["app"], str) for w in result)
    assert all(isinstance(w["focused"], bool) for w in result)
    focused_count = sum(w["focused"] for w in result)
    assert focused_count <= 1


# ---------- M8: titles are redacted in core (all fake PII) ----------

def test_titles_are_redacted_before_they_leave_core(desktop, real_redaction) -> None:
    desktop([fake_window("Call +91 98765 43210 - Notepad", "notepad.exe", focused=True)])
    [window] = list_open_windows()
    assert window["title"].startswith("Call [IN_PHONE]") and window["title"].endswith("Notepad")
    assert "98765" not in window["title"]  # (a " - " next to a mask can be absorbed; see M8 lesson)
    assert window["app"] == "notepad.exe" and window["focused"] is True


def test_ordinary_titles_survive_redaction(desktop, real_redaction) -> None:
    desktop([fake_window("main.py - Pseudo - Visual Studio Code", "Code.exe")])
    assert list_open_windows()[0]["title"] == "main.py - Pseudo - Visual Studio Code"


def test_a_title_that_fails_redaction_is_withheld_not_shown(desktop, monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(title: str) -> str:
        raise RedactionError("simulated failure")
    monkeypatch.setattr(windows, "redact", broken)
    desktop([fake_window(SECRET_TITLE, "notepad.exe", focused=True), fake_window("todo.txt - Notepad")])
    result = list_open_windows()
    assert [w["title"] for w in result] == [TITLE_WITHHELD, TITLE_WITHHELD]  # every window still listed
    assert result[0]["app"] == "notepad.exe" and result[0]["focused"] is True
    assert "4321" not in json.dumps(result)


def test_blocked_titles_never_reach_the_redactor(desktop, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []
    monkeypatch.setattr(windows, "redact", lambda title: seen.append(title) or title)
    desktop([fake_window(SECRET_TITLE, "KeePass.exe"), fake_window("todo.txt - Notepad")])
    list_open_windows()
    assert seen == ["todo.txt - Notepad"]


def test_no_fake_pii_leaks_from_core(desktop, real_redaction) -> None:
    desktop([fake_window("Chat with Rahul Verma, UPI rahul.v@okaxis - WhatsApp Web - Google Chrome", "chrome.exe"),
             fake_window("PAN ABCPE1234F, Aadhaar 2345 6789 0123 - scan.pdf - Adobe Acrobat", "Acrobat.exe")])
    sent = json.dumps(list_open_windows())
    for secret in ["Rahul", "okaxis", "ABCPE1234F", "2345 6789"]:
        assert secret not in sent
