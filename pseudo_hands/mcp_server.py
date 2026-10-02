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

from pseudo_hands.core.active_window import read_active_window
from pseudo_hands.core.focus import focus_window
from pseudo_hands.core.memory import save_memory
from pseudo_hands.core.memory_search import search_memories
from pseudo_hands.core.windows import list_open_windows

LIST_OPEN_WINDOWS_DESCRIPTION = (
    "List the windows open on the user's Windows desktop, front-most first. Each window has "
    "its title, the app (program) it belongs to, and whether it has keyboard focus. Windows of "
    "private apps come back as '[restricted app]'; never guess what they contain. Use this to "
    "see what the user is working on right now."
)
READ_ACTIVE_WINDOW_DESCRIPTION = (
    "Read the text of the user's front-most window (not this assistant): an outline of its "
    "controls, one per line as 'Type: text', indented by nesting. Personal info is already "
    "replaced with labels like [PERSON] or [IN_PHONE]; never guess what they hide. Private apps "
    "return nothing. Long windows are cut short ('truncated': true). Use this when the user asks "
    "about what is on their screen."
)
FOCUS_WINDOW_DESCRIPTION = (
    "Bring one of the user's windows to the front. Pass its id from list_open_windows (like "
    "'w3'); call list_open_windows first if you don't have a current id. The user must approve "
    "every call in a popup on their screen. If the status is 'not approved', nothing happened: "
    "tell the user and don't retry unless they ask. Private apps can't be focused."
)
SEARCH_MEMORIES_DESCRIPTION = (
    "Find up to 3 of the user's past tasks relevant to a question, from Pseudo's local memory. Each "
    "comes back redacted, with labels like [PERSON]; never guess what they hide. An empty list means "
    "nothing relevant. Pseudo's own brain calls this before each question; its model never sees it."
)
SAVE_MEMORY_DESCRIPTION = (
    "Save one finished task (the question, the answer, the tools used, the provider and model) to "
    "Pseudo's local memory. It is redacted first, and the user must approve every save in a popup. "
    "If the status is 'not approved', nothing was saved. Pseudo's own brain calls this after each "
    "answer; its model never sees it."
)

server = MCPServer("pseudo_hands", log_level="WARNING")  # (P5-tune) no INFO chatter on stderr; warnings and errors still show
server.add_tool(
    list_open_windows,  # the core function itself, not a copy or a wrapper around it
    name="list_open_windows",
    description=LIST_OPEN_WINDOWS_DESCRIPTION,
    annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False),  # hints for clients, not a guard
)
server.add_tool(
    read_active_window,  # M9: the core function itself, again
    name="read_active_window",
    description=READ_ACTIVE_WINDOW_DESCRIPTION,
    annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False),
)
server.add_tool(
    focus_window,  # M10: the first action. The approval popup runs inside it, in core (D13).
    name="focus_window",
    description=FOCUS_WINDOW_DESCRIPTION,
    annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False,
                                idempotent_hint=True, open_world_hint=False),
)
server.add_tool(
    search_memories,  # M24: brain-only (pseudo_brain hides it from the model). Redacts again, caps, fails closed.
    name="search_memories",
    description=SEARCH_MEMORIES_DESCRIPTION,
    annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False),
)
server.add_tool(
    save_memory,  # M24: brain-only too. Redaction and the approval popup run inside it, in core (D13, D23).
    name="save_memory",
    description=SAVE_MEMORY_DESCRIPTION,
    annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False,
                                idempotent_hint=False, open_world_hint=False),
)

if __name__ == "__main__":
    server.run()  # transport="stdio" is the default
