"""M14: pseudo_brain's connection to pseudo_hands, as an MCP CLIENT.

What it demonstrates: the other side of M5. pseudo_hands is an MCP server; here
the brain starts it over stdio (the way Hermes did in M6) and asks which tools it
has. Nothing in pseudo_brain names a tool: whatever pseudo_hands publishes is what
the model gets, converted to the OpenAI tool format from M2/M3.

Privacy: pseudo_hands has already blocked, redacted and capped everything in its
core (D6, D11) before it reaches this file. This file only relays. A tool result
goes back to the loop, which keeps it in memory; it is never printed or saved.
The approval popup for actions is shown by the pseudo_hands process itself (D13).
M18: Hands also knows that process's pid, so the face can let ONLY it bring the popup
to the front (face/foreground.js).
M24: the one exception to "nothing here names a tool". The two memory tools are BRAIN-ONLY: they
are left out of what the model sees and can call, so neither the model nor text on the screen
can make Pseudo search or write its memory. The brain calls them itself (chat.py), via memory().
"""

import json
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import psutil
from mcp import Client, StdioServerParameters

REPO_ROOT = Path(__file__).resolve().parent.parent
MAX_RESULT_CHARS = 6000  # one tool result, as sent to the model (pseudo_hands already caps its own)
NO_ARGUMENTS = {"type": "object", "properties": {}}
HANDS_MODULE = "pseudo_hands.mcp_server"
MEMORY_TOOLS = ("search_memories", "save_memory")  # (M24) brain-only: never offered to the model


def pseudo_hands_process() -> StdioServerParameters:
    """How to start pseudo_hands: the same command Hermes used in M6."""
    return StdioServerParameters(command=sys.executable, args=["-m", HANDS_MODULE],
                                 cwd=str(REPO_ROOT))


def command_line(process: psutil.Process) -> str:
    try:
        return " ".join(process.cmdline())
    except psutil.Error:  # it just exited, or isn't ours to read: it isn't pseudo_hands
        return ""


def find_hands_pid(me: psutil.Process | None = None) -> int | None:
    """The pid of the pseudo_hands process that shows the approval popup; None if unsure (M18).

    The venv's python.exe is a small launcher that starts the real Python as its child, so
    TWO of our child processes run pseudo_hands' command line. The real one, which shows the
    popup, is the one with no such child. Anything else (none, or two real ones) gives None,
    and then the face grants nothing.
    """
    try:
        found = [p for p in (me or psutil.Process()).children(recursive=True) if HANDS_MODULE in command_line(p)]
        pids = {p.pid for p in found}
        real = [p.pid for p in found if not any(child.pid in pids for child in p.children())]
    except psutil.Error:
        return None
    return real[0] if len(real) == 1 else None


def to_openai_tool(tool: Any) -> dict:
    """An MCP tool description -> the {"type": "function", ...} shape the model expects (M2)."""
    return {"type": "function", "function": {
        "name": tool.name, "description": tool.description or "",
        "parameters": tool.input_schema or NO_ARGUMENTS}}


def result_text(result: Any) -> str:
    """What the model sees for one tool result: compact JSON of the structured copy, else the text."""
    data = result.structured_content
    if data is not None:
        if isinstance(data, dict) and set(data) == {"result"}:  # the SDK wraps lists as {"result": [...]}
            data = data["result"]
        text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    else:
        text = "\n".join(item.text for item in result.content if hasattr(item, "text"))
    if result.is_error:
        text = f"ERROR: {text}"
    return text if len(text) <= MAX_RESULT_CHARS else text[:MAX_RESULT_CHARS] + " … (cut)"


class Hands:
    """An open connection to pseudo_hands: the tools it published, and a way to call them."""

    def __init__(self, client: Client, tools: list, pid: int | None = None) -> None:
        self._client = client
        self.pid = pid  # the pseudo_hands process (None for an in-memory server in tests)
        self.names = [tool.name for tool in tools if tool.name not in MEMORY_TOOLS]  # what the model may call
        self.schemas = [to_openai_tool(tool) for tool in tools if tool.name not in MEMORY_TOOLS]
        self.has_memory = all(name in {tool.name for tool in tools} for name in MEMORY_TOOLS)
        # (M40) the tools pseudo_hands marks as only reading; every other tool (memory ones too) may ask in a popup
        self.read_only = {tool.name for tool in tools if tool.annotations and tool.annotations.read_only_hint is True}

    def asks(self, name: str) -> bool:
        """(M40) Can this tool open an approval popup? Yes unless it is marked read-only; an unknown name, yes."""
        return name not in self.read_only

    async def call(self, name: str, arguments: str) -> tuple[str, bool]:
        """Run one tool the model asked for. Returns (text for the model, is_error)."""
        if name not in self.names:
            return f"ERROR: no such tool: {name}", True
        try:
            args = json.loads(arguments or "{}")
        except json.JSONDecodeError:
            return "ERROR: the tool arguments were not valid JSON", True
        if not isinstance(args, dict):
            return "ERROR: the tool arguments must be a JSON object", True
        try:
            result = await self._client.call_tool(name, args)
        except Exception as error:  # noqa: BLE001 - the server crashed or hung up; report the type only
            return f"ERROR: the tool call failed ({type(error).__name__})", True
        return result_text(result), bool(result.is_error)

    async def memory(self, name: str, arguments: dict) -> dict | None:
        """(M24) The brain's own call to a memory tool. Its structured result, or None if anything failed."""
        if name not in MEMORY_TOOLS or not self.has_memory:
            return None
        try:
            result = await self._client.call_tool(name, arguments)
        except Exception:  # noqa: BLE001 - the server crashed or hung up: treat as "no memory"
            return None
        data = result.structured_content
        return data if isinstance(data, dict) and not result.is_error else None


class OfferedHands:
    """(M30) The same connection with one tool left out: the model neither sees it nor can call it.

    M29's rule decides per question whether the window-switching tool is offered (routing.py).
    Leaving its schema out of the request is what works: asking the model not to call it didn't."""

    def __init__(self, hands: Hands, withheld: str = "") -> None:
        self._hands, self.pid, self.has_memory = hands, hands.pid, hands.has_memory
        self.names = [name for name in hands.names if name != withheld]
        self.schemas = [schema for schema in hands.schemas if schema["function"]["name"] != withheld]

    async def call(self, name: str, arguments: str) -> tuple[str, bool]:
        if name not in self.names:
            return f"ERROR: no such tool: {name}", True
        return await self._hands.call(name, arguments)


@asynccontextmanager
async def connect_hands(target: Any = None) -> AsyncIterator[Hands]:
    """Start pseudo_hands over stdio (or use an in-memory server in tests) and discover its tools."""
    async with Client(target if target is not None else pseudo_hands_process()) as client:
        tools = (await client.list_tools()).tools
        yield Hands(client, tools, find_hands_pid() if target is None else None)
