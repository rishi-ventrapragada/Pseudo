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


class FakeRect:
    """(M28) Like uiautomation's Rect: a rectangle on screen."""

    def __init__(self, left: int, top: int, right: int, bottom: int) -> None:
        self.left, self.top, self.right, self.bottom = left, top, right, bottom

    def width(self) -> int:
        return self.right - self.left

    def height(self) -> int:
        return self.bottom - self.top


class FakeControl:
    """A fake UI Automation control.

    fail="props"    every question raises, like a control that vanished mid-read
    fail="children" only GetChildren() raises
    fail="password" only IsPassword raises
    box             (M28) its rectangle on screen: left, top, right, bottom
    GetPattern (reading a control's value) fails the test if it's ever called.
    """

    def __init__(self, name: str = "", kind: str = "Text", children: tuple = (), *,
                 fail: str | None = None, offscreen: bool = False, box: tuple = (0, 0, 100, 20)) -> None:
        self._name, self._kind, self._children = name, kind, list(children)
        self._fail, self._offscreen, self._box = fail, offscreen, box

    @property
    def BoundingRectangle(self) -> FakeRect:
        return self._answer(FakeRect(*self._box))

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
    read = walk(window(*(FakeControl(f"Row {i}") for i in range(500))))
    assert read.truncated and read.controls_read == ui_tree.MAX_CONTROLS and read.skipped == 0


# ---------- M28: deeper, and where each control is ----------

def nested(levels: int) -> FakeControl:
    """A window with one chain of Groups `levels` deep, a "Deep" text at the bottom."""
    control = FakeControl("Deep")
    for level in range(levels - 1, 0, -1):
        control = FakeControl(f"Level {level}", "Group", (control,))
    return window(control)


def test_controls_as_deep_as_vs_codes_are_read() -> None:
    read = walk(nested(28))  # M27: VS Code's controls sit at depth 22-28
    assert read.lines[-1].text == "Deep" and read.lines[-1].depth == 28 and not read.truncated


def test_controls_beyond_depth_30_mark_the_read_truncated() -> None:
    read = walk(nested(32))
    assert "Deep" not in texts(read) and read.truncated and max(line.depth for line in read.lines) == 30


def test_each_line_notes_its_controls_centre_and_no_size_means_nowhere() -> None:
    read = walk(window(FakeControl("Save", "Button", box=(10, 20, 110, 40)), FakeControl("Ghost", box=(5, 5, 5, 5))))
    assert [(line.text, line.center) for line in read.lines[1:]] == [("Save", (60, 30)), ("Ghost", None)]


class FakeDocument(FakeControl):
    def GetPattern(self, _pattern_id: int) -> None:
        return None  # no value and no text pattern: an empty document


def test_documents_below_the_window_are_noted_with_their_rectangles() -> None:
    page = FakeDocument("", "Document", (FakeControl("Fake page text", box=(50, 150, 300, 170)),), box=(0, 100, 800, 600))
    read = walk(FakeDocument("Fake browser", "Document", (page,), box=(0, 0, 800, 600)))  # depth 0 is not a page
    assert read.documents == [(0, 100, 800, 600)]
    assert texts(read) == ["Fake browser", "Fake page text"]  # an unnamed Document still adds no line
