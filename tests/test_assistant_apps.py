"""Tests for M18's self-read fix: read_active_window skips assistant apps (assistant_apps.txt).

The bug (found in M15, measured in M17): when you switch to Pseudo to ask about a window,
Pseudo's own window is in front, so it would read its own chat. Every window here is FAKE,
and the UI tree reads are faked too; no real window is ever read.
"""

from pathlib import Path

import pytest

from pseudo_hands.core import active_window, blocked_apps, redactor
from pseudo_hands.core.active_window import ASSISTANT_LIST_UNREADABLE, load_assistant_apps, pick_window, read_active_window
from pseudo_hands.core.ui_tree import TreeLine, TreeRead
from pseudo_hands.core.windows import RawWindow

NOTES_TREE = TreeRead([TreeLine(0, "Window", "Fake notes"), TreeLine(1, "Text", "Project status: BLUE (fake)")], False, 2)


def window(app: str, handle: int) -> RawWindow:
    return RawWindow(title=f"fake {app}", app=app, visible=True, cloaked=False, focused=False, handle=handle)


@pytest.fixture
def screen(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """screen(windows, assistant list text) fakes the z-ordered windows and the list. Returns the handles read."""
    (tmp_path / "blocked.txt").write_text("KeePass.exe\n", encoding="utf-8")
    (tmp_path / "terms.txt").write_text("# none\n", encoding="utf-8")
    monkeypatch.setattr(blocked_apps, "BLOCKED_APPS_FILE", tmp_path / "blocked.txt")
    monkeypatch.setattr(redactor, "TERMS_FILE", tmp_path / "terms.txt")
    reads: list[int] = []

    def fake_read_tree(handle: int) -> TreeRead:
        reads.append(handle)
        return NOTES_TREE

    def set_screen(windows: list[RawWindow], assistants: str | None) -> list[int]:
        listed = tmp_path / "assistant_apps.txt"
        if assistants is not None:
            listed.write_text(assistants, encoding="utf-8")
        monkeypatch.setattr(active_window, "ASSISTANT_APPS_FILE", listed)  # a missing file if assistants is None
        monkeypatch.setattr(active_window, "read_all_windows", lambda: windows)
        monkeypatch.setattr(active_window, "read_tree", fake_read_tree)
        return reads
    return set_screen


def test_every_listed_app_is_skipped(screen) -> None:
    front_to_back = [window("electron.exe", 1), window("claude.exe", 2), window("hermes.exe", 3), window("notepad.exe", 4)]
    screen(front_to_back, "electron.exe\nclaude.exe\nhermes.exe\n")
    assert pick_window().handle == 4


def test_matching_ignores_upper_and_lower_case(screen) -> None:
    screen([window("Electron.EXE", 1), window("notepad.exe", 2)], "ELECTRON.exe\n")
    assert pick_window().handle == 2


def test_comments_and_blank_lines_are_allowed(screen) -> None:
    screen([window("claude.exe", 1), window("notepad.exe", 2)], "# my assistants\n\nclaude.exe   # the Claude app\n")
    assert load_assistant_apps() == {"claude.exe"} and pick_window().handle == 2


def test_an_unlisted_app_in_front_is_read(screen) -> None:
    screen([window("notepad.exe", 1), window("electron.exe", 2)], "electron.exe\n")
    assert pick_window().handle == 1  # only the listed apps are skipped


def test_the_committed_list_holds_the_three_assistants() -> None:
    assert load_assistant_apps() == {"hermes.exe", "claude.exe", "electron.exe"}


def test_an_unreadable_list_withholds_the_content(screen) -> None:
    reads = screen([window("electron.exe", 1), window("notepad.exe", 2)], None)
    result = read_active_window()
    assert result["note"] == ASSISTANT_LIST_UNREADABLE and result["content"] == "" and result["app"] == ""
    assert reads == []  # fail closed: no window was read at all


def test_with_the_face_in_front_the_notes_behind_it_are_read(screen) -> None:
    """The M18 case: you were on your notes, then switched to the face (electron.exe) to ask."""
    reads = screen([window("electron.exe", 7), window("notepad.exe", 101)], "electron.exe\n")
    result = read_active_window()
    assert result["app"] == "notepad.exe" and "BLUE" in result["content"] and reads == [101]
