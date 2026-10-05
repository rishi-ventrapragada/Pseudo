"""M30: the routing rules (pseudo_brain/routing.py).

What it checks:
  - M29's focus rule is still word for word what M29 measured (it moved files in M30);
  - the routing questions are what the M30 plan says (20 + 20, no repeats, none reused from M29);
  - the parts of is_action_request the plan spells out: a plain question is never an action
    request, a polite request still is, and "open the ... window" is a switch.
The 40 routing questions themselves are a MEASUREMENT (M30 step 0), not asserted here.
"""

from brain_action_cases import HELD_OUT, READ_ONLY, SWITCH, live_b_questions
from route_cases import ACTION, BAR, OTHER

from pseudo_brain import routing
from pseudo_brain.routing import is_action_request, offers_focus


def test_the_focus_rule_is_exactly_what_m29_measured() -> None:
    assert routing.SWITCH_PHRASES == ("switch to", "switch back", "switch over", "bring up", "to the front",
                                      "in front", "on top", "focus", "jump to", "take me to", "go back to",
                                      "alt tab", "alt-tab")
    assert routing.SEE_A_WINDOW.pattern == r"\b(show|see|open|go to)\b.*\bwindow\b"
    assert offers_focus("Switch to the fake order page.")
    assert not offers_focus("Can I see the test form?")  # H22: the miss M29 predicted and measured


def test_the_routing_questions_match_the_plan() -> None:
    assert len(ACTION) == 20 and len(OTHER) == 20
    assert len(set(ACTION + OTHER)) == 40
    earlier = {case["ask"] for case in live_b_questions() + HELD_OUT + SWITCH + READ_ONLY}
    assert not earlier & set(ACTION + OTHER)
    assert BAR == {"action_routed_min_of_20": 18, "other_routed_max_of_20": 2}


def test_a_plain_question_is_never_an_action_request() -> None:
    assert not is_action_request("Which box did I tick?")
    assert not is_action_request("  What happens if I press Submit?")


def test_a_polite_request_is_still_an_action_request() -> None:
    assert is_action_request("Can you press the Submit button?")
    assert is_action_request("Please tick the box.")


def test_action_words_match_whole_words_only() -> None:
    assert not is_action_request("Tell me about the settings.")  # "set" inside "settings"
    assert is_action_request("Set the volume to 5.")


def test_opening_a_window_is_a_switch_not_an_action() -> None:
    assert not is_action_request("Open the notes window.")
    assert is_action_request("Open the Help link.")
