"""M40: every tool_call event says whether that tool asks for approval (pseudo_brain/asks.py, Hands.asks).

The marks come from the REAL pseudo_hands server (in memory, no subprocess): what it publishes is what the
brain believes. Nothing here opens a window or a popup.
"""

import pytest

from pseudo_brain.asks import WithAsks
from pseudo_brain.hands import connect_hands
from pseudo_hands.mcp_server import server


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_the_brain_keeps_which_tools_only_read() -> None:
    async with connect_hands(server) as hands:
        assert {name: hands.asks(name) for name in ("list_open_windows", "read_active_window", "search_memories")} == {
            "list_open_windows": False, "read_active_window": False, "search_memories": False}
        assert hands.asks("focus_window") and hands.asks("act_on_control") and hands.asks("save_memory")


@pytest.mark.anyio
async def test_a_tool_the_brain_does_not_know_counts_as_asking() -> None:
    async with connect_hands(server) as hands:
        assert hands.asks("a_tool_added_later") is True
        assert hands.asks("") is True


@pytest.mark.anyio
async def test_asks_is_added_to_every_tool_call_and_nothing_else() -> None:
    seen: list[tuple[str, dict]] = []
    on_event = WithAsks(lambda kind, data: seen.append((kind, data)))
    async with connect_hands(server) as hands:
        on_event.hands = hands
        on_event("tool_call", {"name": "read_active_window", "arguments": "{}"})  # the Groq loop
        on_event("tool_call", {"name": "act_on_control", "arguments": "{}"})  # Claude Code, its prefix already removed
        on_event("tool_call", {"name": "save_memory", "arguments": "{}", "by": "pseudo"})  # Pseudo's own save
        on_event("tool_result", {"name": "read_active_window", "chars": 10, "is_error": False})
    assert [data.get("asks") for kind, data in seen] == [False, True, True, None]
    assert seen[2][1]["by"] == "pseudo" and "asks" not in seen[3][1]


def test_before_a_question_every_tool_counts_as_asking() -> None:
    seen: list[dict] = []
    on_event = WithAsks(lambda _kind, data: seen.append(data))
    on_event("tool_call", {"name": "read_active_window"})
    assert seen == [{"name": "read_active_window", "asks": True}]


def test_the_event_given_is_not_changed_in_place() -> None:
    data = {"name": "focus_window"}
    WithAsks(lambda *_: None)("tool_call", data)
    assert data == {"name": "focus_window"}
