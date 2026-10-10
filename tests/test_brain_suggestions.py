"""M40: the empty chat's suggestions only read (pseudo_brain/suggestions.py).

A click on one asks it at once, so each must be a question Groq answers by reading: never an action
request (routed to Claude Code, D26) and never a request to see or switch to a window (the switch tool).
"""

from pseudo_brain.routing import is_action_request, offers_focus
from pseudo_brain.suggestions import SUGGESTIONS


def test_three_or_four_short_suggestions() -> None:
    assert 3 <= len(SUGGESTIONS) <= 4
    assert all(0 < len(text) <= 40 and text == text.strip() for text in SUGGESTIONS)
    assert len(set(SUGGESTIONS)) == len(SUGGESTIONS)


def test_no_suggestion_is_an_action_request() -> None:
    assert [text for text in SUGGESTIONS if is_action_request(text)] == []


def test_no_suggestion_offers_the_switch_tool() -> None:
    assert [text for text in SUGGESTIONS if offers_focus(text)] == []
