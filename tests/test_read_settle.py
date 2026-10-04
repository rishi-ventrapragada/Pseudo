"""Tests for M28's reads: read again until the number of lines settles, a browser's page first,
and ids on the controls that can act.

Every window, tree and string here is FAKE; the UI Automation walk is replaced with fake reads
(the `screen` fixture from test_active_window.py), so no real window is ever read.
"""

import json

import pytest
from test_active_window import FAKE_TREE, screen, window  # noqa: F401 - screen is a pytest fixture

from pseudo_hands.core import active_window, control_ids
from pseudo_hands.core.active_window import read_active_window
from pseudo_hands.core.control_ids import ControlIds, shown_ids
from pseudo_hands.core.redactor import RedactionError
from pseudo_hands.core.ui_tree import TreeLine, TreeRead


@pytest.fixture(autouse=True)
def fresh_ids(monkeypatch: pytest.MonkeyPatch) -> ControlIds:
    ids = ControlIds()
    monkeypatch.setattr(control_ids, "registry", ids)
    return ids

# ---------- M28: read again until the number of lines settles ----------

GOOD = TreeRead(FAKE_TREE, False, 3)
WINDOW_ONLY = TreeRead([TreeLine(0, "Window", "notes.txt - Notepad")], False, 1)  # nothing inside


def rows(count: int, skipped: int = 0) -> TreeRead:
    """A read that found `count` fake rows inside the window."""
    lines = [TreeLine(0, "Window", "notes.txt - Notepad")] + [TreeLine(1, "ListItem", f"Fake row {i}") for i in range(count)]
    return TreeRead(lines, False, count + 1, skipped)


def test_a_warm_window_is_read_twice_and_settles(screen) -> None:
    reads = screen([window()], GOOD)
    assert read_active_window()["note"] == "" and reads == [101, 101]


def test_a_cold_window_is_read_until_the_count_stops_changing(screen) -> None:
    reads = screen([window()], [rows(4), rows(59), rows(59), OSError("a fourth read must not happen")])
    result = read_active_window()  # M27: VS Code's first read found 4 controls, then 59
    assert reads == [101] * 3 and result["controls_read"] == 60 and result["note"] == ""


def test_a_failed_read_counts_as_nothing_and_the_window_is_read_again(screen) -> None:
    reads = screen([window()], [OSError("cold start"), GOOD])
    result = read_active_window()
    assert reads == [101] * 3 and result["note"] == ""
    assert "[PERSON]" in result["content"]  # the later read went through redaction as usual


def test_a_window_that_keeps_changing_is_read_at_most_four_times(screen) -> None:
    reads = screen([window()], [rows(1), rows(2), rows(3), rows(4), OSError("a fifth read must not happen")])
    result = read_active_window()
    assert reads == [101] * 4 and result["note"] == active_window.STILL_CHANGING
    assert "Fake row 3" in result["content"]  # the last read is the one used


def test_a_window_with_nothing_inside_is_shown_as_it_is(screen) -> None:
    reads = screen([window()], WINDOW_ONLY)
    result = read_active_window()
    assert reads == [101] * 4 and result["note"] == "" and result["content"] == "Window: notes.txt - Notepad"


def test_failures_still_report_only_the_type(screen) -> None:
    reads = screen([window()], OSError("Rahul Verma +91 98765 43210"))
    result = read_active_window()
    assert reads == [101] * 4 and result["note"] == "read failed (OSError)"
    assert "Rahul" not in json.dumps(result) and "98765" not in json.dumps(result)


def test_skipped_controls_are_counted_in_the_note(screen) -> None:
    screen([window()], TreeRead(FAKE_TREE, False, 5, skipped=2))
    assert read_active_window()["note"] == "2 controls skipped (read errors)"
    screen([window()], [rows(1), rows(2), rows(3), rows(4, skipped=1)])
    assert read_active_window()["note"] == f"{active_window.STILL_CHANGING}; 1 control skipped (read errors)"


# ---------- M28: a browser's page area first ----------

def test_the_page_comes_before_the_browsers_own_controls(screen) -> None:
    lines = [TreeLine(0, "Window", "Fake page - Brave", (400, 300)),
             TreeLine(3, "TabItem", "Fake tab", (100, 15)),  # the browser's own controls come first in the walk
             TreeLine(4, "Button", "Reload", (60, 50)),
             TreeLine(9, "Edit", "Subject", (300, 200)),  # inside the page
             TreeLine(9, "Button", "Save fake draft", (300, 260))]
    screen([window(app="brave.exe")], TreeRead(lines, False, 5, documents=[(0, 80, 800, 600), (0, 80, 40, 90)]))
    kinds = [line.strip().split(":")[0] for line in read_active_window()["content"].splitlines()]
    assert kinds == ["Window", "Edit", "Button", "TabItem", "Button"]


# ---------- M28: ids on the controls that can act ----------

FORM = [TreeLine(0, "Window", "Fake form"),
        TreeLine(1, "Button", "Mark as done", actions=frozenset({"press", "open"}), runtime_id=(42, 1), name="Mark as done"),
        TreeLine(1, "Edit", "Subject", actions=frozenset({"set_text", "insert_text"}), runtime_id=(42, 2), name="Subject"),
        TreeLine(1, "Text", "From: Rahul Verma")]


def test_controls_that_can_act_get_ids_that_point_back_at_them(screen, fresh_ids: ControlIds) -> None:
    screen([window(handle=101)], TreeRead(FORM, False, 4))
    content = read_active_window()["content"]
    button = next(line for line in content.splitlines() if line.startswith("  Button #c"))
    assert button.endswith(" as done") and "Rahul" not in content  # the id survives redaction; names don't
    keys = {fresh_ids.find(cid).kind: fresh_ids.find(cid) for cid in shown_ids(content)}
    assert set(keys) == {"Button", "Edit"} and "Text: " in content  # plain text gets no id
    assert (keys["Button"].handle, keys["Button"].runtime_id, keys["Button"].name) == (101, (42, 1), "Mark as done")


def test_ids_cut_off_by_the_cap_never_work(screen, fresh_ids: ControlIds) -> None:
    many = [TreeLine(0, "Window", "Fake list")] + [
        TreeLine(1, "ListItem", f"Fake item {i}", actions=frozenset({"select"}), runtime_id=(42, i), name=f"Fake item {i}")
        for i in range(200)]
    screen([window()], TreeRead(many, False, 201))
    shown = shown_ids(read_active_window()["content"])
    assert 0 < len(shown) < 200 and all(fresh_ids.find(cid) for cid in shown)
    assert fresh_ids.was_handed_out("c200") and fresh_ids.find("c200") is None


def test_every_read_retires_the_last_reads_ids(screen, fresh_ids: ControlIds) -> None:
    screen([window()], TreeRead(FORM, False, 4))
    first = shown_ids(read_active_window()["content"])
    second = shown_ids(read_active_window()["content"])
    assert first and second and not first & second
    assert all(fresh_ids.find(cid) is None for cid in first) and all(fresh_ids.find(cid) for cid in second)


def test_a_blocked_app_or_a_failed_redaction_leaves_no_working_ids(screen, fresh_ids: ControlIds,
                                                                   monkeypatch: pytest.MonkeyPatch) -> None:
    screen([window()], TreeRead(FORM, False, 4))
    earlier = shown_ids(read_active_window()["content"])
    screen([window(app="KeePass.exe")], TreeRead(FORM, False, 4))
    read_active_window()
    assert all(fresh_ids.find(cid) is None for cid in earlier)

    def broken(_text: str) -> str:
        raise RedactionError("simulated")
    screen([window()], TreeRead(FORM, False, 4))
    monkeypatch.setattr(active_window, "redact", broken)
    assert read_active_window()["content"] == active_window.CONTENT_WITHHELD
    assert not any(fresh_ids.find(f"c{n}") for n in range(1, 10))
