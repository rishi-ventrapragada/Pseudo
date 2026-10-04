"""Tests for the UI tree walk: M12 skips a control that fails and keeps going; M28 goes deeper,
notes positions, and notes what each control can do.

Every tree here is FAKE (tests/uia_fakes.py): FakeControl stands in for a uiautomation Control
and raises the same COMError real UI Automation raises when an element vanishes (0x80040201,
UIA_E_ELEMENTNOTAVAILABLE, the error M11 found in claude.exe). No real window is read.
"""

import pytest
from uia_fakes import P, FakeControl, FakePattern

from pseudo_hands.core import ui_tree
from pseudo_hands.core.ui_tree import TreeRead, search, walk


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
    read = walk(window(FakeControl("Password", "Edit", fail="password")))
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


def test_documents_below_the_window_are_noted_with_their_rectangles() -> None:
    page = FakeControl("", "Document", (FakeControl("Fake page text", box=(50, 150, 300, 170)),), box=(0, 100, 800, 600))
    read = walk(FakeControl("Fake browser", "Document", (page,), box=(0, 0, 800, 600)))  # depth 0 is not a page
    assert read.documents == [(0, 100, 800, 600)]
    assert texts(read) == ["Fake browser", "Fake page text"]  # an unnamed Document still adds no line


# ---------- M28: what each control can do ----------

def test_a_control_that_can_act_notes_its_actions_runtime_id_and_raw_name() -> None:
    save = FakeControl("Save fake draft", "Button", patterns={P.InvokePattern: FakePattern()}, runtime_id=(42, 7))
    line = walk(window(save)).lines[1]
    assert (line.actions, line.runtime_id, line.name) == (frozenset({"press", "open"}), (42, 7), "Save fake draft")


def test_controls_that_cannot_act_and_containers_note_nothing() -> None:
    pane = FakeControl("Fake pane", "Pane", patterns={P.InvokePattern: FakePattern()}, runtime_id=(1,))
    read = walk(window(pane, FakeControl("Plain text")))
    assert [(line.actions, line.runtime_id, line.name) for line in read.lines] == [(frozenset(), (), "")] * 3


def test_an_unnamed_button_is_named_by_the_text_inside_it() -> None:  # M27: Obsidian's buttons
    button = FakeControl("", "Group", (FakeControl("", "Image"), FakeControl("New fake note")),
                         patterns={P.LegacyIAccessiblePattern: FakePattern(DefaultAction="Press")})
    line = walk(window(button)).lines[1]
    assert (line.kind, line.text, line.name, line.actions) == ("Group", "New fake note", "New fake note",
                                                              frozenset({"press", "open"}))


def test_a_control_that_can_act_gets_a_line_even_with_no_name_at_all() -> None:
    read = walk(window(FakeControl("", "Button", patterns={P.InvokePattern: FakePattern()})))
    assert [(line.kind, line.text) for line in read.lines] == [("Window", "Fake window"), ("Button", "")]


def test_a_password_fields_value_is_never_read_even_though_it_can_act() -> None:
    value = FakePattern(value="fake-pass-123")
    box = FakeControl("Portal password", "Edit", patterns={P.ValuePattern: value}, password=True)
    line = walk(window(box)).lines[1]
    assert line.text == "Portal password = [password field]" and "set_text" in line.actions
    assert value.value_reads == 0  # act_on_control refuses it later; the read never touches its value


# ---------- M28: finding a control again by its runtime id ----------

def test_a_control_is_found_again_by_its_runtime_id() -> None:
    target = FakeControl("Subject", "Edit", runtime_id=(42, 2))
    tree = window(FakeControl("Group", "Group", (FakeControl("Other", runtime_id=(42, 1)), target)))
    assert search(tree, (42, 2)) is target and search(tree, (42, 9)) is None


def bottom_of(tree: FakeControl) -> FakeControl:
    while tree.GetChildren():
        tree = tree.GetChildren()[0]
    return tree


def test_finding_skips_hidden_vanished_and_too_deep_controls() -> None:
    hidden = FakeControl("Hidden", "Group", (FakeControl("x", runtime_id=(1,)),), offscreen=True)
    vanished = FakeControl("Gone", runtime_id=(2,), fail="props")
    assert search(window(hidden, vanished), (1,)) is None and search(window(hidden, vanished), (2,)) is None
    reachable, too_deep = nested(28), nested(32)
    bottom_of(reachable).runtime_id = bottom_of(too_deep).runtime_id = (3,)
    assert search(reachable, (3,)) is bottom_of(reachable) and search(too_deep, (3,)) is None
