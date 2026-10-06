"""M31: consistency checks for the warm-session questions (tests/warm_session_cases.py).

What it demonstrates: testing the TEST MATERIAL. These checks measure nothing. They make sure the 18
questions match the plan and their own expected popups, so a typo can't quietly turn a right popup into
a "miss", and that the set really is held out: no question, and no control-and-action pair, was already
used to decide anything in M27 to M30.
"""

from pathlib import Path

import brain_action_cases as m29
from action_cases import BENIGN_QUESTIONS, CONTROL_QUESTIONS
from brain_action_cases import ACTION_TYPES
from route_cases import ACTION, OTHER
from warm_session_cases import CRITERIA, FIXTURES, HELD_OUT, SESSION_SIZE, sessions, type_order

REPO = Path(__file__).resolve().parent.parent
TEXT_ACTIONS = {"set_text", "insert_text", "choose"}


def fixture(window: str) -> str:
    return (REPO / FIXTURES[window]).read_text(encoding="utf-8")


def test_sizes_match_the_plan() -> None:
    assert len(HELD_OUT) == 18 and SESSION_SIZE == 6 and len(sessions()) == 3
    assert all(sum(case["action"] == kind for case in HELD_OUT) == 3 for kind in ACTION_TYPES)
    assert [sum(case["window"] == window for case in HELD_OUT) for window in ("F6", "F1", "F2")] == [16, 1, 1]


def test_every_session_holds_each_action_type_once_in_the_rotated_order() -> None:
    for number, session in enumerate(sessions(), start=1):
        assert [case["action"] for case in session] == type_order(number), number
    assert len({session[-1]["action"] for session in sessions()}) == 3  # the 6th place never repeats a type


def test_ids_say_where_a_request_sits() -> None:
    for number, session in enumerate(sessions(), start=1):
        assert [case["id"] for case in session] == [f"S{number}-{place}" for place in range(1, SESSION_SIZE + 1)]


def test_the_third_session_stays_on_one_page() -> None:
    assert {case["window"] for case in sessions()[2]} == {"F6"}


def test_text_is_given_exactly_when_the_action_needs_it_and_appears_in_the_question() -> None:
    for case in HELD_OUT:
        assert bool(case["text"]) == (case["action"] in TEXT_ACTIONS), case["id"]
        assert case["text"] in case["ask"], case["id"]


def test_every_expected_control_and_choice_is_in_its_fake_window() -> None:
    for case in HELD_OUT:
        page = fixture(case["window"])
        assert case["name"] in page, case["id"]
        if case["action"] == "choose":
            assert f"{case['text']}<" in page, case["id"]  # an item of the list


def test_questions_are_new() -> None:
    spent = {case["ask"].lower() for case in m29.live_b_questions() + m29.HELD_OUT + m29.SWITCH + m29.READ_ONLY}
    spent |= {case["ask"].lower() for case in CONTROL_QUESTIONS} | {ask.lower() for ask in BENIGN_QUESTIONS}
    spent |= {ask.lower() for ask in ACTION + OTHER} | {ask.lower() for ask in m29.M15_QUESTIONS.values()}
    asks = [case["ask"].lower() for case in HELD_OUT]
    assert len(asks) == len(set(asks)) and not spent & set(asks)


def test_no_control_and_action_pair_was_in_m29s_held_out_set() -> None:
    used = {(case["window"], case["name"], case["action"]) for case in m29.HELD_OUT}
    assert not used & {(case["window"], case["name"], case["action"]) for case in HELD_OUT}


def test_criteria_are_the_ones_fixed_in_prd() -> None:
    prd = (REPO / "PRD.md").read_text(encoding="utf-8")
    section = prd[prd.index("### M31:"):prd.index("### M32:")]  # M31's section ends where M32's starts
    assert CRITERIA == {"W_S_median_seconds_to_popup_max": 15.0, "W_U_usable_min_of_18": 17,
                        "W_R_own_read_before_acting_min_of_18": 18, "W_T_input_times_the_sessions_first_max": 3.0,
                        "W_B_billing_and_session_clean_min_of_18": 18}
    for phrase in ("raw median to the popup at most 15 s", "usable popups at least 17 of 18",
                   "every request does its own fresh read before acting",
                   "over 3 times the first request's of its session", "billing clean before every request"):
        assert phrase in section, phrase
