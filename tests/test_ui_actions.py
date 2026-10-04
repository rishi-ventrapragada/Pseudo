"""Tests for M28's ui_actions.py: what a control can do, judged by its patterns (D25).

Every control here is FAKE (tests/uia_fakes.py); no real window is touched.
"""

import pytest
from uia_fakes import P, FakeControl, FakePattern

from pseudo_hands.core.ui_actions import CONTAINERS, actions_of, name_of


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
