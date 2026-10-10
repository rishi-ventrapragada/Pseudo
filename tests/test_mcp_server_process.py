"""Tests for M5 (moved here from test_mcp_server.py in M39, unchanged, to keep each file under 200 lines).

Two kinds of checks on pseudo_hands' MCP wrapper:
- D11: the wrapper stays thin (core never imports mcp; the server file defines no logic).
- The real thing: the server started as a subprocess over stdio, the way Hermes and Claude Code start it.
"""

import ast
import sys
from pathlib import Path

import pytest
from mcp import Client, StdioServerParameters
from test_mcp_server import ALL_TOOLS

REPO_ROOT = Path(__file__).resolve().parent.parent
PSEUDO_HANDS = REPO_ROOT / "pseudo_hands"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


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
    assert names == ALL_TOOLS
    assert result.is_error is False
    windows = result.structured_content["result"]
    assert all(set(w) == {"id", "title", "app", "focused"} for w in windows)
    assert all(isinstance(w["focused"], bool) for w in windows)
    focused_count = sum(w["focused"] for w in windows)
    assert focused_count <= 1


@pytest.mark.skipif(sys.platform != "win32", reason="needs Windows")
@pytest.mark.anyio
async def test_tools_option_publishes_only_the_named_tools() -> None:  # (M30) what Claude Code's copy gets
    chosen = ["list_open_windows", "read_active_window", "act_on_control"]
    params = StdioServerParameters(command=sys.executable,
                                   args=["-m", "pseudo_hands.mcp_server", "--tools", ",".join(chosen)],
                                   cwd=str(REPO_ROOT))
    async with Client(params) as client:
        names = [tool.name for tool in (await client.list_tools()).tools]
    assert names == chosen


def test_tools_option_refuses_an_unknown_name() -> None:  # (M30)
    import subprocess
    done = subprocess.run([sys.executable, "-m", "pseudo_hands.mcp_server", "--tools", "list_open_windows,delete_files"],
                          cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=120, stdin=subprocess.DEVNULL)
    assert done.returncode != 0 and "unknown tool" in done.stderr and done.stdout == ""


def test_the_wrapper_knows_every_tool_it_publishes() -> None:  # (M30) --tools removes by this list
    from pseudo_hands.mcp_server import ALL_TOOLS as published
    assert list(published) == ALL_TOOLS
