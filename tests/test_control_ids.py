"""Tests for M28's control ids (control_ids.py). Every key here is FAKE; no window is read."""

import pytest

from pseudo_hands.core.control_ids import ControlIds, ControlKey, normal, shown_ids

KEY = ControlKey(handle=101, process_id=4120, runtime_id=(42, 7), kind="Button", name="Save fake draft")


def test_ids_only_go_up_and_never_repeat() -> None:
    ids = ControlIds()
    assert [ids.new_id() for _ in range(3)] == ["c1", "c2", "c3"]


def test_an_id_works_only_once_a_read_keeps_it() -> None:
    ids = ControlIds()
    cid = ids.new_id()
    assert ids.find(cid) is None
    ids.replace({cid: KEY})
    assert ids.find(cid) == KEY


def test_a_new_read_retires_every_older_id() -> None:
    ids = ControlIds()
    old = ids.new_id()
    ids.replace({old: KEY})
    new = ids.new_id()
    ids.replace({new: KEY})
    assert ids.find(old) is None and ids.was_handed_out(old)  # -> "old id: read the window again"
    assert ids.find(new) == KEY


@pytest.mark.parametrize("given", ["#c1", "C1", " c1 ", "#C1"])
def test_models_copying_the_hash_or_changing_case_still_match(given: str) -> None:
    ids = ControlIds()
    ids.replace({ids.new_id(): KEY})
    assert normal(given) == "c1" and ids.find(given) == KEY


@pytest.mark.parametrize("given", ["c2", "c0", "w1", "", "c01", "1", "c1; c2", "../c1"])
def test_ids_never_handed_out_are_unknown(given: str) -> None:
    ids = ControlIds()
    ids.replace({ids.new_id(): KEY})
    assert ids.find(given) is None and not ids.was_handed_out(given)


def test_shown_ids_are_read_from_an_outline() -> None:
    text = "Window: Fake form\n  Button #c12: [PERSON] as done\n  Edit #c13: Subject\n  Text: price #42"
    assert shown_ids(text) == {"c12", "c13"}
