"""Tests for M5: the thin MCP server around list_open_windows().

Most tests talk to the server in memory: Client(server) runs the real MCP
protocol (handshake, tools/list, tools/call) without a subprocess, on the fake
desktop from conftest.py. One test starts the server for real over stdio, the
way Hermes will, and asserts only on counts and types so no real title can
appear in a failure message.

Async tests: @pytest.mark.anyio runs them on an event loop (anyio's pytest
plugin comes with the mcp package). An event loop is what `await` needs,
like the one Node always runs for you.
"""

import ast
import json
import sys
from pathlib import Path

import pytest
from mcp import Client, StdioServerParameters

from pseudo_hands.core import blocked_apps
from pseudo_hands.core.blocked_apps import RESTRICTED
from pseudo_hands.core.windows import RawWindow, list_open_windows
from pseudo_hands.mcp_server import LIST_OPEN_WINDOWS_DESCRIPTION, server

REPO_ROOT = Path(__file__).resolve().parent.parent
PSEUDO_HANDS = REPO_ROOT / "pseudo_hands"
SECRET_TITLE = "Vault: bank PIN 4321"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def fake(title: str, app: str | None, focused: bool = False) -> RawWindow:
    return RawWindow(title=title, app=app, visible=True, cloaked=False, focused=focused)


def everything_sent(result) -> str:
    """All text a model could see in a tool result: the text content plus the structured copy."""
    texts = [item.text for item in result.content if hasattr(item, "text")]
    return json.dumps(texts) + json.dumps(result.structured_content)


# ---------- what the server publishes ----------

@pytest.mark.anyio
async def test_the_server_publishes_exactly_one_read_only_tool() -> None:
    async with Client(server) as client:
        tools = (await client.list_tools()).tools
    assert [tool.name for tool in tools] == ["list_open_windows"]
    tool = tools[0]
    assert tool.description == LIST_OPEN_WINDOWS_DESCRIPTION
    assert tool.input_schema["properties"] == {}  # the tool takes no arguments
    assert tool.annotations.read_only_hint is True


# ---------- calling it: same result as the core, privacy intact ----------

@pytest.mark.anyio
async def test_a_call_returns_exactly_what_the_core_returns(desktop) -> None:
    desktop([fake("notes.md - Notepad", "notepad.exe", focused=True), fake("Home", "Code.exe")])
    async with Client(server) as client:
        result = await client.call_tool("list_open_windows", {})
    assert result.is_error is False
    assert result.structured_content == {"result": list_open_windows()}


@pytest.mark.anyio
async def test_masking_still_holds_through_mcp(desktop) -> None:
    desktop([fake(SECRET_TITLE, "KeePass.exe", focused=True), fake(SECRET_TITLE, None)])
    async with Client(server) as client:
        result = await client.call_tool("list_open_windows", {})
    assert result.structured_content["result"] == [
        {"title": RESTRICTED, "app": RESTRICTED, "focused": True},
        {"title": RESTRICTED, "app": RESTRICTED, "focused": False},
    ]
    sent = everything_sent(result)
    assert "4321" not in sent and "Vault" not in sent and "KeePass" not in sent


@pytest.mark.anyio
async def test_a_missing_list_fails_closed_through_mcp(desktop, monkeypatch: pytest.MonkeyPatch,
                                                       tmp_path: Path) -> None:
    desktop([fake(SECRET_TITLE, "notepad.exe")])
    monkeypatch.setattr(blocked_apps, "BLOCKED_APPS_FILE", tmp_path / "missing.txt")
    async with Client(server) as client:
        result = await client.call_tool("list_open_windows", {})
    assert result.is_error is True
    sent = everything_sent(result)
    assert "4321" not in sent and "missing.txt" not in sent  # no window data, no file path


# ---------- D11: the wrapper stays thin ----------

def imported_modules(path: Path) -> set[str]:
    names = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_core_never_imports_mcp() -> None:
    for path in (PSEUDO_HANDS / "core").glob("*.py"):
        modules = imported_modules(path)
        assert not any(m == "mcp" or m.startswith("mcp.") for m in modules), path.name


def test_the_server_file_defines_no_logic_of_its_own() -> None:
    tree = ast.parse((PSEUDO_HANDS / "mcp_server.py").read_text(encoding="utf-8"))
    logic = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)
    assert [type(node).__name__ for node in ast.walk(tree) if isinstance(node, logic)] == []


# ---------- the real thing: a subprocess over stdio, like Hermes ----------

@pytest.mark.skipif(sys.platform != "win32", reason="needs Windows")
@pytest.mark.anyio
async def test_real_server_over_stdio_smoke() -> None:
    # Only counts, key sets and types in the asserts: a failure can't print window titles.
    params = StdioServerParameters(command=sys.executable, args=["-m", "pseudo_hands.mcp_server"],
                                   cwd=str(REPO_ROOT))
    async with Client(params) as client:
        names = [tool.name for tool in (await client.list_tools()).tools]
        result = await client.call_tool("list_open_windows", {})
    assert names == ["list_open_windows"]
    assert result.is_error is False
    windows = result.structured_content["result"]
    assert all(set(w) == {"title", "app", "focused"} for w in windows)
    assert all(isinstance(w["focused"], bool) for w in windows)
    focused_count = sum(w["focused"] for w in windows)
    assert focused_count <= 1
