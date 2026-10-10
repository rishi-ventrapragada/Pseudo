"""M40: a tool that can show the approval popup is never published as read-only.

Why it matters now: the face shows "Waiting for your approval in the popup" only for tools that ask
(pseudo_brain/asks.py), and it learns which ones ask from these marks. A popup tool marked read-only
would wait with no line on screen. Each published tool IS a core function (mcp_server.py adds the
function itself), so the check reads that function's own module for a call to approval.ask.
"""

import inspect

import pytest
from mcp import Client

from pseudo_hands import mcp_server
from pseudo_hands.mcp_server import ALL_TOOLS, server

ASKS = "approval.ask("


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def calls_the_popup(tool_name: str) -> bool:
    function = getattr(mcp_server, tool_name)  # the core function published under that name
    return ASKS in inspect.getsource(inspect.getmodule(function))


def test_found_the_tools_that_show_the_popup() -> None:
    assert [name for name in ALL_TOOLS if calls_the_popup(name)] == ["focus_window", "act_on_control", "save_memory"]


@pytest.mark.anyio
async def test_every_tool_that_shows_the_popup_is_marked_as_not_read_only() -> None:
    async with Client(server) as client:
        marks = {tool.name: tool.annotations.read_only_hint for tool in (await client.list_tools()).tools}
    assert set(marks) == set(ALL_TOOLS)
    for name in ALL_TOOLS:
        if calls_the_popup(name):
            assert marks[name] is False, name
