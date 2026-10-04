"""M29: consistency checks for the action questions (tests/brain_action_cases.py).

These don't measure anything, and they never apply the rule (R1 is a measurement). They make sure the
questions match the plan and their own expected popups, so a typo can't quietly turn a right popup
into a "miss" in M29's results.
"""

from pathlib import Path

from action_cases import BENIGN_QUESTIONS, CONTROL_QUESTIONS
from brain_action_cases import (ACTION_TYPES, FIXTURES, HELD_OUT, LIVE_B, READ_ONLY, SWITCH,
                                live_b_questions)

REPO = Path(__file__).resolve().parent.parent
TEXT_ACTIONS = {"set_text", "insert_text", "choose"}


def fixture(window: str) -> str:
    return (REPO / FIXTURES[window]).read_text(encoding="utf-8")


def test_sizes_match_the_plan() -> None:
    assert [case["action"] for case in LIVE_B] == list(ACTION_TYPES)
    assert len(live_b_questions()) == 12
    assert len(HELD_OUT) == 18 and len(SWITCH) == 4 and len(READ_ONLY) == 2
    assert all(sum(case["action"] == kind for case in HELD_OUT) == 3 for kind in ACTION_TYPES)


def test_ids_are_unique() -> None:
    ids = [case["id"] for case in live_b_questions() + HELD_OUT + SWITCH + READ_ONLY]
    assert len(ids) == len(set(ids))


def test_text_is_given_exactly_when_the_action_needs_it_and_appears_in_the_question() -> None:
    for case in live_b_questions() + HELD_OUT:
        assert bool(case["text"]) == (case["action"] in TEXT_ACTIONS), case["id"]
        assert case["text"] in case["ask"], case["id"]


def test_every_expected_control_and_choice_is_in_its_fake_window() -> None:
    for case in live_b_questions() + HELD_OUT:
        page = fixture(case["window"])
        assert case["name"] in page, case["id"]
        if case["action"] == "choose":
            assert f"{case['text']}<" in page or f'"{case["text"]}"' in page, case["id"]  # an item of the list


def test_held_out_questions_are_new() -> None:
    spent = {case["ask"].lower() for case in live_b_questions()}
    spent |= {case["ask"].lower() for case in CONTROL_QUESTIONS} | {ask.lower() for ask in BENIGN_QUESTIONS}
    assert not any(case["ask"].lower() in spent for case in HELD_OUT + SWITCH + READ_ONLY)


def test_switch_questions_ask_for_a_window_that_is_not_already_right_behind_pseudo() -> None:
    for case in SWITCH:
        assert case["focus"] == case["behind"] != case["window"], case["id"]
        assert {case["window"], case["behind"]} <= set(FIXTURES), case["id"]
