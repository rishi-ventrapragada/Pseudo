"""Tests for M10: focus_window(). Every window here is FAKE, and nothing really moves.

The `screen` fixture lists fake windows (so they get ids), fakes reading them
live, and swaps the real action for a recorder: `fake.acted` lists every window
that would have been brought to the front. The person at the popup is faked too
(popup_yes / popup_no), and conftest fails any test that reaches the real popup.
"""

import dataclasses
import json
import os
from pathlib import Path

import pytest
import pywintypes
import win32con

from pseudo_hands.core import approval, blocked_apps, focus, window_ids
from pseudo_hands.core.blocked_apps import RESTRICTED, BlockedAppsError
from pseudo_hands.core.focus import focus_window
from pseudo_hands.core.windows import RawWindow, list_open_windows

A = RawWindow("todo.txt - Notepad", "notepad.exe", True, False, True, handle=101, process_id=4001)  # in front
B = RawWindow("notes.txt - Notepad", "notepad.exe", True, False, False, handle=102, process_id=4002)


class FakeScreen:
    def __init__(self, windows: list[RawWindow]) -> None:
        self.live = {w.handle: w for w in windows}  # what reading a window "now" returns
        self.foreground = next((w.handle for w in windows if w.focused), 0)
        self.acted: list[int] = []

    def read_window(self, handle: int, _focused: int) -> RawWindow | None:
        window = self.live.get(handle)
        return None if window is None else dataclasses.replace(window, focused=handle == self.foreground)

    def bring_to_front(self, handle: int) -> bool:
        self.acted.append(handle)
        self.foreground = handle
        return True


@pytest.fixture
def screen(desktop, monkeypatch: pytest.MonkeyPatch):
    """screen([windows]) -> (fake, ids in listing order)."""
    def set_screen(windows: list[RawWindow]) -> tuple[FakeScreen, list[str | None]]:
        desktop(windows)
        fake = FakeScreen(windows)
        monkeypatch.setattr(focus, "read_window", fake.read_window)
        monkeypatch.setattr(focus, "bring_to_front", fake.bring_to_front)
        return fake, [w["id"] for w in list_open_windows()]
    return set_screen


# ---------- approve, deny, timeout ----------

def test_approve_brings_the_window_to_the_front(screen, popup_yes) -> None:
    fake, [_, b] = screen([A, B])
    out = focus_window(b)
    assert out == {"window_id": b, "title": B.title, "app": "notepad.exe", "status": "focused"}
    assert fake.acted == [B.handle] and len(popup_yes.previews) == 1


@pytest.mark.parametrize("answer, seconds", [(win32con.IDCANCEL, 2.0), (win32con.IDCANCEL, 20.0),
                                             (win32con.IDOK, 25.0), (0, 0.0)],
                         ids=["cancel-esc-or-x", "timer-closed-it", "ok-too-late", "popup-failed"])
def test_anything_but_ok_in_time_changes_nothing(screen, monkeypatch: pytest.MonkeyPatch,
                                                 answer: int, seconds: float) -> None:
    fake, [_, b] = screen([A, B])
    monkeypatch.setattr(approval, "approver",
                        lambda _q: approval.approved(answer, seconds, approval.TIMEOUT_SECONDS))
    assert focus_window(b)["status"] == "not approved"
    assert fake.acted == [] and fake.foreground == A.handle  # denial leaves focus unchanged


def test_a_plain_no_changes_nothing(screen, popup_no) -> None:
    fake, [_, b] = screen([A, B])
    assert focus_window(b)["status"] == "not approved" and fake.acted == [] and fake.foreground == A.handle


# ---------- what the popup shows vs what the model gets ----------

def test_the_popup_shows_the_real_title_but_the_model_gets_it_redacted(screen, popup_yes, real_redaction) -> None:
    chat = dataclasses.replace(B, title="Chat with Rahul Verma - Notepad")
    _, [_, b] = screen([A, chat])
    out = focus_window(b)
    assert "Rahul Verma" in popup_yes.previews[0] and "notepad.exe" in popup_yes.previews[0]
    assert "[PERSON]" in out["title"] and "Rahul" not in json.dumps(out)


# ---------- targets that never reach the popup ----------

@pytest.mark.parametrize("bad_id", ["w99", "", "102", "notes.txt - Notepad"])
def test_ids_we_never_handed_out_are_refused(screen, popup_yes, bad_id: str) -> None:
    fake, _ = screen([A, B])
    assert focus_window(bad_id)["status"] == "unknown id"
    assert popup_yes.previews == [] and fake.acted == []


@pytest.mark.parametrize("change", ["closed", "handle-reused", "hidden"])
def test_a_window_that_is_gone_or_changed_is_refused(screen, popup_yes, change: str) -> None:
    fake, [_, b] = screen([A, B])
    if change == "closed":
        del fake.live[B.handle]
    elif change == "handle-reused":
        fake.live[B.handle] = dataclasses.replace(B, process_id=9999)  # same handle, another program
    else:
        fake.live[B.handle] = dataclasses.replace(B, visible=False)
    assert focus_window(b)["status"] == "window gone"
    assert popup_yes.previews == [] and fake.acted == []


def test_a_blocked_app_is_never_shown_or_touched(screen, popup_yes, monkeypatch: pytest.MonkeyPatch,
                                                  tmp_path: Path) -> None:
    fake, [_, b] = screen([A, B])
    now_blocked = tmp_path / "now_blocked.txt"  # the list changed after the model got its id
    now_blocked.write_text("notepad.exe\n", encoding="utf-8")
    monkeypatch.setattr(blocked_apps, "BLOCKED_APPS_FILE", now_blocked)
    out = focus_window(b)
    assert out == {"window_id": b, "title": RESTRICTED, "app": RESTRICTED, "status": "restricted"}
    assert popup_yes.previews == [] and fake.acted == []


def test_pseudos_own_windows_are_never_touched_d14(screen, popup_yes) -> None:
    popup = RawWindow(approval.POPUP_TITLE, "python.exe", True, False, False, handle=103, process_id=os.getpid())
    fake, ids = screen([A, B, popup])
    assert ids[2] is None  # list_open_windows gives it no id...
    forced = window_ids.registry.id_for(popup.handle, popup.process_id)  # ...and even if it had one:
    assert focus_window(forced)["status"] == "own window"
    assert popup_yes.previews == [] and fake.acted == []


def test_a_window_already_in_front_needs_no_popup(screen, popup_yes) -> None:
    fake, [a, _] = screen([A, B])
    assert focus_window(a)["status"] == "already in front"
    assert popup_yes.previews == [] and fake.acted == []


def test_a_missing_blocked_list_stops_everything(screen, popup_yes, monkeypatch: pytest.MonkeyPatch,
                                                 tmp_path: Path) -> None:
    fake, [_, b] = screen([A, B])
    monkeypatch.setattr(blocked_apps, "BLOCKED_APPS_FILE", tmp_path / "missing.txt")
    with pytest.raises(BlockedAppsError):
        focus_window(b)
    assert popup_yes.previews == [] and fake.acted == []


# ---------- after the popup ----------

def test_a_window_that_closes_while_the_popup_is_open_is_not_touched(screen, monkeypatch: pytest.MonkeyPatch) -> None:
    fake, [_, b] = screen([A, B])

    def closes_then_says_yes(_question: str) -> bool:
        del fake.live[B.handle]  # the person closed it during the 20 s, then clicked OK
        return True
    monkeypatch.setattr(approval, "approver", closes_then_says_yes)
    assert focus_window(b)["status"] == "window gone" and fake.acted == []


def test_a_refusal_by_windows_is_reported(screen, popup_yes, monkeypatch: pytest.MonkeyPatch) -> None:
    _, [_, b] = screen([A, B])
    monkeypatch.setattr(focus, "bring_to_front", lambda _handle: False)
    assert focus_window(b)["status"] == "focus refused"


# ---------- the action itself (Windows calls faked) ----------

def test_a_minimized_window_is_restored_only_after_focusing_worked(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(focus.win32gui, "SetForegroundWindow", lambda h: calls.append("focus"))
    monkeypatch.setattr(focus.win32gui, "IsIconic", lambda h: True)
    monkeypatch.setattr(focus.win32gui, "ShowWindow", lambda h, how: calls.append("restore"))
    monkeypatch.setattr(focus.win32gui, "GetForegroundWindow", lambda: 102)
    assert focus.bring_to_front(102) is True and calls == ["focus", "restore"]


def test_a_switch_that_lands_a_moment_later_still_counts(monkeypatch: pytest.MonkeyPatch) -> None:
    # Found in the real run: right after SetForegroundWindow, Windows can still report the old window.
    reported = iter([55, 55, 102])  # old window twice, then ours
    monkeypatch.setattr(focus.win32gui, "SetForegroundWindow", lambda h: None)
    monkeypatch.setattr(focus.win32gui, "IsIconic", lambda h: False)
    monkeypatch.setattr(focus.win32gui, "GetForegroundWindow", lambda: next(reported, 102))
    assert focus.bring_to_front(102) is True


def test_when_windows_refuses_nothing_is_half_done(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(_handle: int) -> None:
        raise pywintypes.error(0, "SetForegroundWindow", "refused")
    monkeypatch.setattr(focus.win32gui, "SetForegroundWindow", refuse)
    monkeypatch.setattr(focus.win32gui, "ShowWindow", lambda h, how: pytest.fail("must not restore"))
    assert focus.bring_to_front(102) is False
