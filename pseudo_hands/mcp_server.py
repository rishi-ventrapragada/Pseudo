"""M5: the MCP wrapper. Publishes Pseudo's core tools to any MCP brain.

What it demonstrates: a wrapper with no logic (DECISIONS.md D11). This file
defines no functions at all. It hands the core function itself to the MCP
SDK, which reads its type hints to build the tool's input and output schemas
and handles the protocol (handshake, tools/list, tools/call). Every privacy
rule still runs inside the core, so the brain on the other side can't skip it.

Transport: stdio. The brain (Hermes in M6, the Inspector, our tests) starts
this file as a child process and talks to it over stdin/stdout. No port is
opened, so nothing else on the machine can ask it for your windows.
The one rule of stdio: stdout IS the protocol channel. Nothing here or in
core/ may print(); a stray print corrupts the messages. Logs go to stderr.

Run it (normally the brain does this for you):
    python -m pseudo_hands.mcp_server
"""

from mcp.server import MCPServer
from mcp.types import ToolAnnotations

from pseudo_hands.core.windows import list_open_windows

LIST_OPEN_WINDOWS_DESCRIPTION = (
    "List the windows open on the user's Windows desktop, front-most first. Each window has "
    "its title, the app (program) it belongs to, and whether it has keyboard focus. Windows of "
    "private apps come back as '[restricted app]'; never guess what they contain. Use this to "
    "see what the user is working on right now."
)

server = MCPServer("pseudo_hands")
server.add_tool(
    list_open_windows,  # the core function itself, not a copy or a wrapper around it
    name="list_open_windows",
    description=LIST_OPEN_WINDOWS_DESCRIPTION,
    annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False),  # hints for clients, not a guard
)

if __name__ == "__main__":
    server.run()  # transport="stdio" is the default
