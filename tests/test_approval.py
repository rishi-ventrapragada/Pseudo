"""Tests for M10: the approval gate in core/approval.py.

Most tests use the fake person from conftest (popup_yes / popup_no). One test
shows a REAL popup for about a second and lets its timer close it, to prove
that "nobody answered" really comes back as no.
"""

import sys
import threading
import time

import pytest
import win32api
import win32con
import win32gui

from pseudo_hands.core import approval
from pseudo_hands.core.approval import approved, ask, show_popup


def test_only_ok_in_time_counts_as_yes() -> None:
    assert approved(win32con.IDOK, 3.0, 20.0) is True
    assert approved(win32con.IDOK, 20.5, 20.0) is False  # clicked after the timer fired: too late
    assert approved(win32con.IDCANCEL, 3.0, 20.0) is False  # Cancel, Esc, the X and the timeout
    assert approved(0, 0.1, 20.0) is False  # 0 = Windows couldn't show the popup at all


def test_a_yes_is_passed_on_with_the_question(popup_yes) -> None:
    assert ask("Allow it?") is True
    assert popup_yes.previews == ["Allow it?"]


def test_a_no_is_passed_on(popup_no) -> None:
    assert ask("Allow it?") is False


def test_a_broken_popup_means_no(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(_question: str) -> bool:
        raise OSError("no desktop to show it on")
    monkeypatch.setattr(approval, "approver", broken)
    assert ask("Allow it?") is False


def test_only_a_real_true_means_yes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(approval, "approver", lambda _question: "yes")  # truthy, but not True
    assert ask("Allow it?") is False


def test_a_second_request_while_a_popup_is_open_is_refused(popup_yes) -> None:
    with approval._one_at_a_time:  # pretend a popup is already open
        assert ask("Allow it?") is False
    assert popup_yes.previews == []  # the second popup was never even shown
    assert ask("Allow it?") is True  # once the first one is gone, asking works again


def test_the_timeout_is_shorter_than_hermes_tool_timeout() -> None:
    assert approval.TIMEOUT_SECONDS == 20.0  # Hermes' pseudo profile waits 30 s (see the M10 lesson)


def test_pinning_asks_for_always_on_top_without_taking_focus(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple] = []
    monkeypatch.setattr(approval, "find_popup", lambda _thread: 77)
    monkeypatch.setattr(approval.win32gui, "IsWindowVisible", lambda _h: True)
    monkeypatch.setattr(approval.win32gui, "SetWindowPos", lambda *args: calls.append(args))
    approval.pin_on_top(1234)
    [(handle, insert_after, *_position, flags)] = calls
    assert handle == 77 and insert_after == win32con.HWND_TOPMOST
    assert flags & win32con.SWP_NOACTIVATE  # pinned in front, but never grabs the keyboard


@pytest.mark.skipif(sys.platform != "win32", reason="needs Windows")
def test_a_real_popup_is_pinned_on_top_and_closes_itself_as_no() -> None:
    # A REAL popup, on screen for about 1 second. Nobody clicks it; its timer closes it.
    this_thread, seen = win32api.GetCurrentThreadId(), {}

    def look() -> None:  # halfway through, read our own popup's always-on-top flag
        time.sleep(0.5)
        box = approval.find_popup(this_thread)
        seen["topmost"] = bool(box) and bool(win32gui.GetWindowLong(box, win32con.GWL_EXSTYLE)
                                             & win32con.WS_EX_TOPMOST)
    checker = threading.Thread(target=look)
    checker.start()
    started = time.monotonic()
    answer = show_popup("Pseudo test: this closes itself in 1 second. Nothing will happen.", timeout=1.0)
    checker.join()
    assert answer is False and seen["topmost"] is True
    assert 0.9 <= time.monotonic() - started < 5.0
