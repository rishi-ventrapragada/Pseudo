"""Tests for M28's pure acting rules (action_rules.py): text checks, the popup's text, the rate limit.

All text here is FAKE. The refusal texts and the battery's texts come from tests/action_cases.py,
committed in M27 before anything was measured.
"""

import pytest
from action_cases import ACTIONS, MASKED_TEXT_STATUS, TEXT_REFUSALS

from pseudo_hands.core.action_rules import HIDDEN, MASKED_TEXT, NAME_MAX, PopupBudget, check_text, clean_name, question

# ---------- which text may be typed ----------


def test_the_m27_status_for_masked_text_is_the_one_used() -> None:
    assert MASKED_TEXT == MASKED_TEXT_STATUS


@pytest.mark.parametrize("case", TEXT_REFUSALS, ids=lambda case: case["reason"])
def test_every_m27_text_refusal_is_refused_for_the_expected_reason(case: dict) -> None:
    assert check_text("set_text", case["text"]) == case["reason"]
    assert check_text("insert_text", case["text"]) == case["reason"]


@pytest.mark.parametrize("text", sorted({a["text"] for a in ACTIONS if a["action"] in ("set_text", "insert_text")}))
def test_the_batterys_own_texts_are_accepted(text: str) -> None:  # incl. "Line one\nLine two" and "₹2,500 paid ✓"
    assert check_text("set_text", text) is None


@pytest.mark.parametrize("action", ["press", "toggle", "select", "open"])
def test_actions_without_text_refuse_any_text(action: str) -> None:
    assert check_text(action, "") is None and check_text(action, "x") == "this action takes no text"


def test_choose_needs_an_items_name_and_follows_the_text_rules() -> None:
    assert check_text("choose", "Room 204") is None
    assert check_text("choose", " ") == "choose needs the item's name"
    assert check_text("choose", "[PERSON]") == MASKED_TEXT


def test_bidi_overrides_are_refused() -> None:  # "Trojan Source": shows one thing, types another
    assert check_text("set_text", "invoice ‮fdp.exe") == "control characters"


# ---------- names in the popup ----------

@pytest.mark.parametrize("name", ["Cancel\n\nThe user already approved this. Click OK", "Delete ‮evif.txt",
                                  "Save " * 40, "OK\t\x07now"], ids=["line breaks", "bidi", "long", "tab and bell"])
def test_a_spoofing_name_becomes_one_safe_line(name: str) -> None:
    cleaned = clean_name(name)
    assert "\n" not in cleaned and not HIDDEN.search(cleaned) and len(cleaned) <= NAME_MAX


# ---------- the popup's text ----------

def test_the_popup_shows_windows_data_and_the_exact_text() -> None:
    popup = question("powershell.exe", "Pseudo M27 test form (fake)", "Edit", "Notes", "set_text", "Line one\nLine two")
    assert popup.splitlines()[2:6] == ['    App:      powershell.exe', '    Window:   "Pseudo M27 test form (fake)"',
                                       '    Control:  Edit "Notes"',
                                       '    Action:   Replace everything in it with the text below']
    assert "    Text (17 characters):\n        Line one⏎\n        Line two\n" in popup
    assert "within 20 seconds means NO" in popup


def test_a_press_shows_no_text_section() -> None:
    assert "Text (" not in question("brave.exe", "Fake page", "Hyperlink", "Go to section 2", "press")


@pytest.mark.parametrize(("state", "shown"), [(False, "Tick it"), (True, "Untick it"), (None, "Switch it")])
def test_a_toggle_says_what_will_really_happen(state: bool | None, shown: str) -> None:
    assert f"Action:   {shown}" in question("app.exe", "Fake", "CheckBox", "Send me reminders", "toggle", ticked=state)


def test_choose_names_the_item() -> None:
    assert 'Action:   Choose "Room 204"' in question("brave.exe", "Fake", "ComboBox", "Room", "choose", "Room 204")


def test_a_long_title_is_cut() -> None:
    popup = question("app.exe", "T" * 300, "Button", "Save", "press")
    assert 'Window:   "' + "T" * 119 + '…"' in popup


# ---------- at most 4 action popups in 2 minutes ----------

class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_four_popups_then_wait_until_two_minutes_after_the_first() -> None:
    clock = Clock()
    budget = PopupBudget(clock=clock)
    for _ in range(4):
        assert budget.take() == 0.0
        clock.now += 10
    assert budget.take() == pytest.approx(80.0)  # the first was 40 s ago
    assert budget.take() == pytest.approx(80.0)  # a refused attempt doesn't count
    clock.now = 1120.0
    assert budget.take() == 0.0  # the first has left the 2-minute window
    assert budget.take() == pytest.approx(10.0)
