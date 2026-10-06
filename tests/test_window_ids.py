"""Tests for M10: the short ids list_open_windows() hands out for focus_window().

All windows here are fake (conftest's `desktop` fixture), and each test starts
with a fresh registry, so the first window listed is always "w1".
"""

import itertools
import os
from pathlib import Path

import pytest

from pseudo_hands.core import assistant_apps, window_ids
from pseudo_hands.core.windows import RawWindow, list_open_windows

HANDLES = itertools.count(101)


def fake_window(title: str = "notes.md - Notepad", app: str | None = "notepad.exe", *,
                handle: int | None = None, process_id: int = 4000) -> RawWindow:
    return RawWindow(title=title, app=app, visible=True, cloaked=False, focused=False,
                     handle=next(HANDLES) if handle is None else handle, process_id=process_id)


def test_each_listed_window_gets_its_own_short_id(desktop) -> None:
    desktop([fake_window("a - Notepad"), fake_window("b - Notepad")])
    assert [w["id"] for w in list_open_windows()] == ["w1", "w2"]


def test_the_same_window_keeps_its_id_when_the_order_changes(desktop) -> None:
    notepad, code = fake_window("a - Notepad"), fake_window("Home", "Code.exe")
    desktop([notepad, code])
    first = {w["title"]: w["id"] for w in list_open_windows()}
    desktop([code, notepad])  # Code.exe came to the front
    assert {w["title"]: w["id"] for w in list_open_windows()} == first


def test_an_id_is_never_reused_for_another_window(desktop) -> None:
    desktop([fake_window("a - Notepad")])
    [old] = list_open_windows()
    desktop([fake_window("b - Notepad")])  # the first window closed, a new one opened
    [new] = list_open_windows()
    assert (old["id"], new["id"]) == ("w1", "w2")


def test_a_reused_handle_in_another_program_gets_a_new_id(desktop) -> None:
    desktop([fake_window(handle=5, process_id=100)])
    [before] = list_open_windows()
    desktop([fake_window(handle=5, process_id=200)])  # Windows gave handle 5 to a new program
    [after] = list_open_windows()
    assert before["id"] != after["id"]


def test_blocked_unknown_and_pseudos_own_windows_get_no_id(desktop) -> None:
    desktop([fake_window("Vault", "KeePass.exe"), fake_window("Vault", None),
             fake_window("Pseudo: approve this action?", "python.exe", process_id=os.getpid())])  # D14
    assert [w["id"] for w in list_open_windows()] == [None, None, None]


def test_an_assistant_app_is_listed_but_gets_no_id(desktop) -> None:  # (P8-fix)
    desktop([fake_window("Pseudo", "Electron.exe"), fake_window("a - Notepad")])
    face, notes = list_open_windows()
    assert (face["title"], face["app"], face["id"]) == ("Pseudo", "Electron.exe", None)
    assert notes["id"] == "w1"  # the face didn't use up an id either


def test_an_unreadable_assistant_list_means_no_ids_at_all(desktop, monkeypatch: pytest.MonkeyPatch,
                                                          tmp_path: Path) -> None:  # (P8-fix)
    desktop([fake_window("Pseudo", "electron.exe"), fake_window("a - Notepad")])
    monkeypatch.setattr(assistant_apps, "ASSISTANT_APPS_FILE", tmp_path / "missing.txt")
    listed = list_open_windows()
    assert [w["id"] for w in listed] == [None, None]  # fail closed: we can't tell the face apart
    assert [w["title"] for w in listed] == ["Pseudo", "a - Notepad"]  # still listed


def test_the_registry_only_knows_ids_it_handed_out(desktop) -> None:
    desktop([fake_window(handle=7, process_id=4000)])
    list_open_windows()
    registry = window_ids.registry
    assert registry.find("w1") == (7, 4000) and registry.find(" W1 ") == (7, 4000)
    assert registry.find("w2") is None and registry.find("7") is None and registry.find("") is None
