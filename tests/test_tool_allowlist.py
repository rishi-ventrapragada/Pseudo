"""M42 (D29): one allowlist of the tools a model may be offered (pseudo_brain/model_tools.py).

Checked against the REAL pseudo_hands server (in memory, no subprocess) and the committed providers.toml:
  - the server's ALL_TOOLS is exactly what it registers, and every tool is on exactly one list;
  - a tool on no list is offered to nobody: not to Groq's loop, not to the action brain, not to brain_call;
  - no brain-only tool reaches any model, Groq's requests or Claude Code's command line and config.
"""

from pathlib import Path

import pytest
from brain_fakes import FakeModel, reply
from mcp import Client
from mcp.server.mcpserver import MCPServer

from pseudo_brain import claude_code
from pseudo_brain.action_brain import load_routing
from pseudo_brain.hands import connect_hands
from pseudo_brain.loop import run_turn
from pseudo_brain.model_tools import BRAIN_TOOLS, load_model_tools
from pseudo_brain.providers import ProviderRefused
from pseudo_brain.session import Session
from pseudo_hands.core.memory_search import MemoryResult
from pseudo_hands.mcp_server import ALL_TOOLS, server

RAN: list[str] = []  # every fake tool that actually ran


def fake_read() -> dict:
    RAN.append("read_active_window")
    return {"content": "fake"}


def fake_new() -> dict:
    RAN.append("new_tool")
    return {"done": True}


def fake_search(question: str) -> MemoryResult:  # typed, so it has a structured result
    RAN.append("search_memories")
    return {"intro": "", "memories": [], "note": ""}


EXTRA = MCPServer("fake_hands_with_a_new_tool")  # a pseudo_hands that published a tool nobody listed
EXTRA.add_tool(fake_read, name="read_active_window", description="Read the fake window.")
EXTRA.add_tool(fake_new, name="new_tool", description="A tool added later and listed nowhere.")
EXTRA.add_tool(fake_search, name="search_memories", description="A brain-only tool.")


@pytest.fixture(autouse=True)
def nothing_ran() -> None:
    RAN.clear()


@pytest.mark.anyio
async def test_all_tools_is_exactly_what_the_server_registers_with_no_name_twice() -> None:
    async with Client(server) as client:
        registered = [tool.name for tool in (await client.list_tools()).tools]
    assert sorted(registered) == sorted(ALL_TOOLS) and len(set(ALL_TOOLS)) == len(ALL_TOOLS)


def test_every_published_tool_is_on_exactly_one_list() -> None:
    model_tools = load_model_tools()
    assert set(model_tools) <= set(ALL_TOOLS) and set(BRAIN_TOOLS) <= set(ALL_TOOLS)  # no list names a missing tool
    assert all((name in model_tools) != (name in BRAIN_TOOLS) for name in ALL_TOOLS)


def test_the_committed_list_is_what_models_were_offered_before_d29() -> None:
    assert load_model_tools() == ("list_open_windows", "read_active_window", "focus_window", "act_on_control")


@pytest.mark.anyio
async def test_a_tool_on_no_list_is_offered_to_no_model_and_runs_for_nobody() -> None:
    fake = FakeModel(reply(tools=[("new_tool", "{}"), ("search_memories", '{"question": "x"}')]), reply("Done."))
    async with connect_hands(EXTRA, ("read_active_window",)) as hands:
        assert hands.names == ["read_active_window"]
        assert [schema["function"]["name"] for schema in hands.schemas] == ["read_active_window"]
        await run_turn(Session(), "Do the new thing", fake, hands, lambda kind, data: None)
        assert await hands.brain_call("new_tool", {}) is None  # brain_call only knows BRAIN_TOOLS
    offered = {tool["function"]["name"] for request in fake.requests for tool in request["tools"]}
    assert offered == {"read_active_window"}
    tool_texts = [m["content"] for m in fake.requests[1]["messages"] if m["role"] == "tool"]
    assert all("no such tool" in text for text in tool_texts) and RAN == []


@pytest.mark.anyio
async def test_a_brain_only_tool_is_never_offered_even_if_a_list_names_it() -> None:
    async with connect_hands(EXTRA, ("read_active_window", "search_memories")) as hands:
        assert "search_memories" not in hands.names  # Hands checks a second time
        assert await hands.brain_call("search_memories", {"question": "x"}) is not None
    assert RAN == ["search_memories"]  # the brain's own call, the only way in


@pytest.mark.anyio
async def test_the_real_server_offers_a_model_only_the_list() -> None:
    async with connect_hands(server) as hands:
        assert hands.names == list(load_model_tools()) and not set(BRAIN_TOOLS) & set(hands.names)


def test_no_brain_tool_reaches_the_action_brain(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    brain = load_routing().action_brain
    assert set(brain.tools) <= set(load_model_tools()) and not set(BRAIN_TOOLS) & set(brain.tools)
    monkeypatch.setattr(claude_code, "WORK_DIR", tmp_path)
    config = claude_code.write_config(brain)
    line = claude_code.command_line(["claude"], brain, config, "fake prompt")
    allowed = line[line.index("--allowedTools") + 1:line.index("--system-prompt")]
    assert allowed == [claude_code.PREFIX + tool for tool in brain.tools]
    published = config.read_text(encoding="utf-8")
    assert f'"--tools", "{",".join(brain.tools)}"' in published
    assert not any(tool in published or tool in " ".join(line) for tool in BRAIN_TOOLS)


@pytest.mark.parametrize("text, reason", [
    ('switch_tool = "x"\n', "must be a list of tool names"),
    ('model_tools = "read_active_window"\n', "must be a list of tool names"),
    ('model_tools = ["read_active_window", ""]\n', "must be a list of tool names"),
    ('model_tools = ["read_active_window", "read_active_window"]\n', "names a tool twice"),
    ('model_tools = ["read_active_window", "save_memory"]\n', "save_memory is brain-only"),
    ('model_tools = ["looking_at"]\n', "looking_at is brain-only"),
])
def test_a_bad_list_is_refused_and_pseudo_does_not_start(tmp_path: Path, text: str, reason: str) -> None:
    path = tmp_path / "providers.toml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ProviderRefused, match=reason):
        load_model_tools(path)
    with pytest.raises(ProviderRefused, match=reason):
        load_routing(path)  # the bridge loads routing before anything starts
