"""Tests for M42: looking_at() (the look-at chip) and app_names.display_name().

The chip must name the app read_active_window WOULD read, and read nothing from it: no title, no text,
no tree, and the control ids from the last read stay as they were. Fake windows only; the app names
come from a fake lookup, except one check on this test's own Python.
"""

import json
import os
from pathlib import Path

import psutil
import pytest

from pseudo_hands.core import active_window, app_names, assistant_apps, blocked_apps, control_ids, looking_at
from pseudo_hands.core.looking_at import LISTS_UNREADABLE
from pseudo_hands.core.windows import RawWindow

SECRET_TITLE = "Fake bank statement for Rahul Verma"


def win(app: str | None, process_id: int = 4000, title: str = SECRET_TITLE) -> RawWindow:
    return RawWindow(title=title, app=app, visible=True, cloaked=False, focused=False, handle=101,
                     process_id=process_id)


@pytest.fixture
def screen(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """screen(windows) fakes the z-ordered windows; reading a tree or changing the ids fails the test."""
    (tmp_path / "blocked.txt").write_text("KeePass.exe\n", encoding="utf-8")
    (tmp_path / "assistants.txt").write_text("electron.exe\n", encoding="utf-8")
    monkeypatch.setattr(blocked_apps, "BLOCKED_APPS_FILE", tmp_path / "blocked.txt")
    monkeypatch.setattr(assistant_apps, "ASSISTANT_APPS_FILE", tmp_path / "assistants.txt")
    monkeypatch.setattr(looking_at, "display_name", lambda process_id, app: f"Name of {app}")

    def never(*args) -> None:
        raise AssertionError("looking_at must not read a window or touch the control ids")
    monkeypatch.setattr(active_window, "read_tree", never)
    monkeypatch.setattr(control_ids.registry, "replace", never)

    def set_screen(windows: list[RawWindow]) -> None:
        monkeypatch.setattr(active_window, "read_all_windows", lambda: windows)
    return set_screen


def test_it_names_the_window_behind_pseudo_and_the_assistant_apps(screen) -> None:
    screen([win("Pseudo.exe", os.getpid()), win("electron.exe"), win("Code.exe"), win("notepad.exe")])
    assert looking_at.looking_at() == {"app": "Name of Code.exe", "private": False, "note": ""}


@pytest.mark.parametrize("app", ["KeePass.exe", "keepass.EXE", None])  # an unknown owner counts as blocked
def test_a_blocked_app_is_private_and_has_no_name(screen, app) -> None:
    screen([win(app), win("Code.exe")])
    assert looking_at.looking_at() == {"app": "", "private": True, "note": ""}


def test_the_window_title_is_never_in_the_result(screen) -> None:
    screen([win("Code.exe")])
    assert "Rahul" not in json.dumps(looking_at.looking_at())


@pytest.mark.parametrize("module, setting", [(blocked_apps, "BLOCKED_APPS_FILE"),
                                             (assistant_apps, "ASSISTANT_APPS_FILE")])
def test_an_unreadable_list_shows_nothing(screen, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, module,
                                          setting: str) -> None:
    screen([win("Code.exe")])
    monkeypatch.setattr(module, setting, tmp_path / "missing.txt")
    assert looking_at.looking_at() == {"app": "", "private": False, "note": LISTS_UNREADABLE}


def test_no_window_shows_nothing(screen) -> None:
    screen([win("electron.exe")])
    assert looking_at.looking_at() == {"app": "", "private": False, "note": "no window"}


# ---------- the app's own name ----------

def test_this_tests_own_python_is_called_python() -> None:
    assert app_names.display_name(os.getpid(), "python.exe") == "Python"


def test_without_the_programs_path_the_exe_name_is_used(monkeypatch: pytest.MonkeyPatch) -> None:
    def gone(process_id: int):
        raise psutil.NoSuchProcess(process_id)
    monkeypatch.setattr(app_names.psutil, "Process", gone)
    assert app_names.display_name(4000, "Brave.EXE") == "Brave" and app_names.display_name(4000, None) == ""


def test_a_file_with_no_description_falls_back(tmp_path: Path) -> None:
    fake_exe = tmp_path / "fake.exe"
    fake_exe.write_text("not a program", encoding="utf-8")
    assert app_names.description(str(fake_exe)) == ""


def test_a_long_or_odd_description_becomes_one_short_line(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(app_names, "description", lambda path: "Fake\n\tBrowser\x00 " * 10)
    name = app_names.display_name(os.getpid(), "fake.exe")
    assert name.startswith("Fake Browser Fake") and len(name) <= app_names.MAX_CHARS and "\n" not in name
