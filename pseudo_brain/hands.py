"""M14: pseudo_brain's connection to pseudo_hands, as an MCP CLIENT.

What it demonstrates: the other side of M5. pseudo_hands is an MCP server; here
the brain starts it over stdio (the way Hermes did in M6) and asks which tools it
has. Nothing in pseudo_brain names a tool: whatever pseudo_hands publishes is what
the model gets, converted to the OpenAI tool format from M2/M3.

Privacy: pseudo_hands has already blocked, redacted and capped everything in its
core (D6, D11) before it reaches this file. This file only relays. A tool result
goes back to the loop, which keeps it in memory; it is never printed or saved.
The approval popup for actions is shown by the pseudo_hands process itself (D13).
"""

import json
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from mcp import Client, StdioServerParameters

REPO_ROOT = Path(__file__).resolve().parent.parent
MAX_RESULT_CHARS = 6000  # one tool result, as sent to the model (pseudo_hands already caps its own)
NO_ARGUMENTS = {"type": "object", "properties": {}}


def pseudo_hands_process() -> StdioServerParameters:
    """How to start pseudo_hands: the same command Hermes used in M6."""
    return StdioServerParameters(command=sys.executable, args=["-m", "pseudo_hands.mcp_server"],
                                 cwd=str(REPO_ROOT))


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

    def __init__(self, client: Client, tools: list) -> None:
        self._client = client
        self.names = [tool.name for tool in tools]
        self.schemas = [to_openai_tool(tool) for tool in tools]

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


@asynccontextmanager
async def connect_hands(target: Any = None) -> AsyncIterator[Hands]:
    """Start pseudo_hands over stdio (or use an in-memory server in tests) and discover its tools."""
    async with Client(target if target is not None else pseudo_hands_process()) as client:
        tools = (await client.list_tools()).tools
        yield Hands(client, tools)
