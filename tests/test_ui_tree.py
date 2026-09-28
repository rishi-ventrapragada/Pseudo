"""Tests for M12: the UI tree walk skips a control that fails and keeps going.

Every tree here is FAKE: FakeControl stands in for a uiautomation Control and
raises the same COMError real UI Automation raises when an element vanishes
(0x80040201, UIA_E_ELEMENTNOTAVAILABLE, the error M11 found in claude.exe).
No real window is read.
"""

import pytest
from comtypes import COMError

from pseudo_hands.core import ui_tree
from pseudo_hands.core.ui_tree import TreeRead, walk

ELEMENT_NOT_AVAILABLE = -2147220991  # 0x80040201 as a signed 32-bit number, the way COM reports it


def gone() -> COMError:
    return COMError(ELEMENT_NOT_AVAILABLE, "element not available", (None, None, None, 0, None))


class FakeControl:
    """A fake UI Automation control.

    fail="props"    every question raises, like a control that vanished mid-read
    fail="children" only GetChildren() raises
    fail="password" only IsPassword raises
    GetPattern (reading a control's value) fails the test if it's ever called.
    """

    def __init__(self, name: str = "", kind: str = "Text", children: tuple = (), *,
                 fail: str | None = None, offscreen: bool = False) -> None:
        self._name, self._kind, self._children = name, kind, list(children)
        self._fail, self._offscreen = fail, offscreen

    def _answer(self, value: object) -> object:
        if self._fail == "props":
            raise gone()
        return value

    @property
    def Name(self) -> str:
        return self._answer(self._name)

    @property
    def ControlTypeName(self) -> str:
        return self._answer(f"{self._kind}Control")

    @property
    def IsOffscreen(self) -> bool:
        return self._answer(self._offscreen)

    @property
    def IsPassword(self) -> bool:
        if self._fail == "password":
            raise gone()
        return self._answer(False)

    def GetChildren(self) -> list["FakeControl"]:
        if self._fail == "children":
            raise gone()
        return self._answer(self._children)

    def GetFirstChildControl(self) -> "FakeControl | None":
        return self._children[0] if self._children else None

    def GetPattern(self, _pattern_id: int) -> None:
        raise AssertionError("this control's value must never be read")


def texts(read: TreeRead) -> list[str]:
    return [line.text for line in read.lines]


def window(*children: FakeControl) -> FakeControl:
    return FakeControl("Fake window", "Window", children)


# ---------- a failing control is skipped, the rest is still read ----------

def test_a_failing_control_is_skipped_and_the_walk_goes_on() -> None:
    read = walk(window(FakeControl("Before"), FakeControl("Vanished", fail="props"), FakeControl("After")))
    assert texts(read) == ["Fake window", "Before", "After"]
    assert read.skipped == 1 and read.controls_read == 4 and not read.truncated


def test_everything_inside_a_failing_control_is_skipped_too() -> None:
    group = FakeControl("Group", "Group", (FakeControl("Inside the group"),), fail="props")
    read = walk(window(group, FakeControl("Sibling")))
    assert texts(read) == ["Fake window", "Sibling"] and read.skipped == 1


def test_a_control_whose_children_cant_be_listed_is_dropped_whole() -> None:
    toolbar = FakeControl("Toolbar", "ToolBar", (FakeControl("Unreachable"),), fail="children")
    read = walk(window(toolbar, FakeControl("Sibling")))
    assert texts(read) == ["Fake window", "Sibling"]  # its name was read, but half-read isn't kept
    assert read.skipped == 1


def test_a_password_box_whose_check_fails_is_skipped_never_read() -> None:
    read = walk(window(FakeControl("Password", "Edit", fail="password")))  # GetPattern would fail the test
    assert texts(read) == ["Fake window"] and read.skipped == 1


def test_if_the_window_itself_fails_the_read_is_empty() -> None:
    read = walk(FakeControl("Fake window", "Window", (FakeControl("Never reached"),), fail="props"))
    assert read.lines == [] and read.skipped == 1 and read.controls_read == 1  # M12's retry takes it from here


def test_only_com_errors_are_skipped_our_own_bugs_still_fail() -> None:
    class Buggy(FakeControl):
        @property
        def Name(self) -> str:
            raise ValueError("a bug in our code, not a vanished control")

    with pytest.raises(ValueError):
        walk(window(Buggy("x")))


# ---------- what M9 already did still holds ----------

def test_a_healthy_tree_reads_in_screen_order_with_nothing_skipped() -> None:
    read = walk(window(FakeControl("Menu", "Group", (FakeControl("File"),)), FakeControl("Save", "Button")))
    assert [(line.depth, line.kind, line.text) for line in read.lines] == [
        (0, "Window", "Fake window"), (1, "Group", "Menu"), (2, "Text", "File"), (1, "Button", "Save")]
    assert read.skipped == 0 and read.controls_read == 4


def test_an_offscreen_control_and_its_children_are_skipped_but_not_counted_as_failures() -> None:
    hidden = FakeControl("Hidden tab", "Group", (FakeControl("Hidden text"),), offscreen=True)
    read = walk(window(hidden, FakeControl("Shown")))
    assert texts(read) == ["Fake window", "Shown"] and read.skipped == 0


def test_the_control_budget_still_truncates() -> None:
    read = walk(window(*(FakeControl(f"Row {i}") for i in range(300))))
    assert read.truncated and read.controls_read == ui_tree.MAX_CONTROLS and read.skipped == 0
