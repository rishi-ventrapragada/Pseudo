"""Tests for M10: bring_to_front(), the one line of focus_window() that acts.

Every Windows call here is FAKE, so nothing really moves. These tests lived in
test_focus_window.py until P8-fix, when that file passed 200 lines.
"""

import pytest
import pywintypes

from pseudo_hands.core import focus


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
