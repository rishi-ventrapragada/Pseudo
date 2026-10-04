"""Tests for M28's outline order: a browser's page area first. Every line here is FAKE; no window is read."""

from pseudo_hands.core.outline import outline, page_first
from pseudo_hands.core.ui_tree import TreeLine

WINDOW = TreeLine(0, "Window", "Fake page - Brave", (400, 300))
TAB = TreeLine(3, "TabItem", "Fake tab", (100, 15))
FIELD = TreeLine(9, "Edit", "Subject", (300, 200))
NOWHERE = TreeLine(9, "Text", "No size", None)
PAGE = (0, 80, 800, 600)


def test_without_a_document_the_walk_order_is_kept() -> None:
    assert page_first([WINDOW, TAB, FIELD], []) == [WINDOW, TAB, FIELD]


def test_lines_inside_the_page_come_first_and_the_window_line_stays_on_top() -> None:
    assert page_first([WINDOW, TAB, FIELD], [PAGE]) == [WINDOW, FIELD, TAB]


def test_the_biggest_document_is_the_page() -> None:
    small = (0, 0, 200, 30)  # e.g. a toolbar widget that is a Document too
    assert page_first([WINDOW, FIELD, TAB], [small, PAGE]) == [WINDOW, FIELD, TAB]
    assert page_first([WINDOW, FIELD, TAB], [small]) == [WINDOW, TAB, FIELD]  # only the tab is inside the small one


def test_a_control_with_no_size_counts_as_outside() -> None:
    assert page_first([WINDOW, NOWHERE, FIELD], [PAGE]) == [WINDOW, FIELD, NOWHERE]


def test_without_a_window_line_every_line_is_sorted() -> None:
    assert page_first([TAB, FIELD], [PAGE]) == [FIELD, TAB]


def test_nothing_is_lost_or_doubled() -> None:
    lines = [WINDOW, TAB, NOWHERE, FIELD]
    ordered = page_first(lines, [PAGE])
    assert sorted(map(id, ordered)) == sorted(map(id, lines))


def test_the_outline_format_is_m9s() -> None:
    assert outline([WINDOW, FIELD]) == "Window: Fake page - Brave\n" + "  " * 9 + "Edit: Subject"
