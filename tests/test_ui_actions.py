"""Tests for M28's ui_actions.py: what a control can do, judged by its patterns (D25).

Every control here is FAKE (tests/uia_fakes.py); no real window is touched.
"""

import pytest
from uia_fakes import P, FakeControl, FakePattern

from pseudo_hands.core import ui_actions
from pseudo_hands.core.ui_actions import (CONTAINERS, DIFFERS, DONE, NO_ITEM, PRESSED, UNAVAILABLE, actions_of,
                                          name_of, perform)


def control(kind: str = "Button", **patterns: FakePattern) -> FakeControl:
    return FakeControl("Fake control", kind, patterns={getattr(P, name): pattern for name, pattern in patterns.items()})


# ---------- what a control can do ----------

@pytest.mark.parametrize(("patterns", "expected"), [
    ({"InvokePattern": FakePattern()}, {"press", "open"}),
    ({"LegacyIAccessiblePattern": FakePattern(DefaultAction="Press")}, {"press", "open"}),
    ({"ValuePattern": FakePattern()}, {"set_text", "insert_text"}),
    ({"TogglePattern": FakePattern()}, {"toggle"}),
    ({"SelectionItemPattern": FakePattern()}, {"select", "open"}),
    ({"ExpandCollapsePattern": FakePattern()}, {"choose"}),
    ({}, set()),
])
def test_each_pattern_offers_its_actions(patterns: dict, expected: set) -> None:
    assert actions_of(control(**patterns), "Button") == frozenset(expected)


def test_a_legacy_interface_without_a_default_action_offers_nothing() -> None:
    assert actions_of(control(LegacyIAccessiblePattern=FakePattern(DefaultAction="")), "Group") == frozenset()


def test_a_read_only_value_cannot_be_typed_into() -> None:
    assert actions_of(control(ValuePattern=FakePattern(IsReadOnly=True)), "Edit") == frozenset()


def test_patterns_add_up() -> None:  # e.g. a combo box you can type into and open
    found = actions_of(control(ValuePattern=FakePattern(), ExpandCollapsePattern=FakePattern()), "ComboBox")
    assert found == frozenset({"set_text", "insert_text", "choose"})


@pytest.mark.parametrize("kind", sorted(CONTAINERS))
def test_containers_never_get_actions(kind: str) -> None:
    assert actions_of(control(kind, InvokePattern=FakePattern()), kind) == frozenset()


def test_judging_actions_never_reads_a_value() -> None:
    value = FakePattern(value="fake-pass-123")
    actions_of(control(ValuePattern=value), "Edit")
    assert value.value_reads == 0


# ---------- naming an unnamed control ----------

def test_a_named_control_keeps_its_name() -> None:
    assert name_of(FakeControl("Save", "Button", (FakeControl("Inner text"),))) == "Save"


def test_an_unnamed_control_is_named_by_the_first_text_inside_it() -> None:
    group = FakeControl("", "Group", (FakeControl("", "Image"), FakeControl("", "Group", (FakeControl("New fake note"),))))
    assert name_of(group) == "New fake note"


def test_text_deeper_than_three_levels_is_not_used() -> None:
    deep = FakeControl("", "Group", (FakeControl("", "Group", (FakeControl("", "Group", (
        FakeControl("", "Group", (FakeControl("Too deep"),)),)),)),))
    assert name_of(deep) == ""


# ---------- acting, then reading the effect back ----------

class Stubborn(FakePattern):
    """An app that accepts every call and changes nothing."""

    def SetValue(self, value: str, waitTime: float = 0.5) -> bool:
        self.calls.append(("SetValue", value, waitTime))
        return True

    def Select(self, waitTime: float = 0.5) -> bool:
        self.calls.append(("Select", waitTime))
        return True


def test_press_invokes_once_without_uiautomations_half_second_wait() -> None:
    invoke = FakePattern()
    assert perform(control(InvokePattern=invoke), "press") == PRESSED and invoke.calls == [("Invoke", 0)]


def test_press_falls_back_to_the_legacy_default_action() -> None:  # M27 v2: Obsidian's Group buttons
    legacy = FakePattern(DefaultAction="Press")
    assert perform(control("Group", LegacyIAccessiblePattern=legacy), "press") == PRESSED
    assert legacy.calls == [("DoDefaultAction", 0)]


def test_open_presses_if_it_can_and_otherwise_selects() -> None:
    invoke, item = FakePattern(), FakePattern()
    assert perform(control(InvokePattern=invoke, SelectionItemPattern=FakePattern()), "open") == PRESSED
    assert perform(control("TreeItem", SelectionItemPattern=item), "open") == DONE and item.IsSelected


def test_toggle_flips_the_box_and_reads_it_back() -> None:
    box = FakePattern(ToggleState=0)
    assert perform(control("CheckBox", TogglePattern=box), "toggle") == DONE and box.ToggleState == 1


def test_set_text_replaces_and_insert_text_appends() -> None:
    value = FakePattern(value="Old fake text")
    assert perform(control("Edit", ValuePattern=value), "set_text", "Lab report draft") == DONE
    assert perform(control("Edit", ValuePattern=value), "insert_text", " (v2)") == DONE
    assert value.Value == "Lab report draft (v2)" and value.calls[0] == ("SetValue", "Lab report draft", 0)


class Late(FakePattern):
    """An app like Chromium (M28 Live A): the new value shows up a moment after the change."""

    @property
    def Value(self) -> str:
        self.value_reads += 1
        return self._value if self.value_reads > 3 else "old fake value"


def test_a_value_that_shows_up_a_moment_later_still_reads_back_as_done() -> None:
    late = Late()
    assert perform(control("Edit", ValuePattern=late), "set_text", "Fake") == DONE and late.value_reads == 4


def test_a_read_back_that_differs_is_reported_honestly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ui_actions, "READ_BACK_SECONDS", 0.05)  # keeps asking this long, then gives up
    assert perform(control("Edit", ValuePattern=Stubborn()), "set_text", "Fake") == DIFFERS
    assert perform(control("ListItem", SelectionItemPattern=Stubborn()), "select") == DIFFERS


def test_a_missing_or_read_only_pattern_does_nothing() -> None:
    read_only = FakePattern(IsReadOnly=True)
    assert perform(control("Edit", ValuePattern=read_only), "set_text", "x") == UNAVAILABLE and read_only.calls == []
    assert perform(control(), "toggle") == UNAVAILABLE


def dropdown(*names: str) -> tuple[FakeControl, dict[str, FakePattern], FakePattern]:
    items = {name: FakePattern() for name in names}
    listbox = FakeControl("", "List", tuple(FakeControl(name, "ListItem", patterns={P.SelectionItemPattern: pattern})
                                         for name, pattern in items.items()))
    expand = FakePattern()
    return FakeControl("Room", "ComboBox", (listbox,), patterns={P.ExpandCollapsePattern: expand}), items, expand


def test_choose_selects_the_item_with_exactly_that_name_and_closes_the_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ui_actions, "CHOOSE_WAIT_SECONDS", 0)
    combo, items, expand = dropdown("Room 101", "Room 204", "Room 2045")
    assert perform(combo, "choose", "Room 204") == DONE
    assert items["Room 204"].IsSelected and not items["Room 2045"].IsSelected
    assert [call[0] for call in expand.calls] == ["Expand", "Collapse"]


def test_choose_never_picks_a_partial_match(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ui_actions, "CHOOSE_WAIT_SECONDS", 0)
    combo, items, expand = dropdown("Room 101", "Room 204")
    assert perform(combo, "choose", "Room 2") == NO_ITEM
    assert not any(item.IsSelected for item in items.values()) and expand.ExpandCollapseState == 0
