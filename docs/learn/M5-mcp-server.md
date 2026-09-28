# M5: Thin MCP server

## The concept in one paragraph

**MCP (Model Context Protocol)** is a standard plug between an AI "brain" (the **client**, like Hermes) and a set of tools (the **server**, like `pseudo_hands`). They exchange **JSON-RPC** messages: small JSON objects saying "call method X with these params" and "here's the result". Every connection follows the same three steps: an `initialize` **handshake** (they agree on a protocol version), `tools/list` (the client asks what tools exist and gets their schemas), and `tools/call` (the client runs one). M5 puts `list_open_windows()` behind that plug without changing a line of the core, so any MCP brain can now see your windows, with the privacy mask already applied.

## Web-dev analogy

- An MCP server is a tiny API whose **OpenAPI spec is generated from your types**, like FastAPI or tRPC. `tools/list` is fetching that spec, and `tools/call` is calling an endpoint.
- **stdio transport** is `child_process.spawn()` with pipes, instead of `app.listen(3000)`. The brain starts the server as a child process and writes to its stdin and reads from its stdout. No port is opened.
- `readOnlyHint` is like HTTP GET being "safe": a promise to the client, not enforcement. The real guard is still the mask in `core/`.
- The M5 server is like a Next.js API route that just does `return res.json(await getWindows())`, except it doesn't even have the function body.

## What was built (file by file)

| File | What it does |
|---|---|
| `pseudo_hands/mcp_server.py` | Registers the core function with the MCP SDK and runs over stdio. **Zero functions of its own.** |
| `tests/test_mcp_server.py` | 7 tests: the published schema, same result as core, masking and fail-closed through MCP, two "stays thin" guards, and a real stdio subprocess. |
| `tests/conftest.py` | Now holds the `desktop` fake-desktop fixture, shared by the M4 and M5 tests. |
| `requirements.txt` | Adds `mcp==2.2.0`, the official SDK. |

## Walkthrough of the key code

**1. The whole server is one registration:**
```python
server = MCPServer("pseudo_hands")
server.add_tool(
    list_open_windows,  # the core function itself, not a copy or a wrapper around it
    name="list_open_windows",
    description=LIST_OPEN_WINDOWS_DESCRIPTION,
    annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False),
)
```
We hand the SDK the core function object itself. There's no wrapper function in between, so there's nowhere for logic (or a bug that skips the mask) to hide. Two tests keep it that way: one parses `mcp_server.py` and fails if it ever contains a `def`, `class` or `lambda`, and one fails if any file in `core/` imports `mcp` (D11).

**2. Type hints become the schema.** The SDK reads the signature: no parameters gives an empty `inputSchema`. The return type `-> list[Window]` (a `TypedDict`) gives an `outputSchema`. A list isn't a JSON *object*, so the SDK wraps it as `{"result": [...]}`. The `description` is what the model reads to decide *when* to call the tool.

**3. `server.run()` defaults to stdio.** The one rule of stdio: **stdout is the protocol channel.** A stray `print()` in the server or the core injects non-JSON into the message stream. When tested, the SDK's own client logged `Invalid JSON ... input_value='hello'` and skipped the line. A stricter client may drop the connection, and a print in the middle of a message corrupts that message. `core/` never prints, and `show_windows.py` (which does) is never imported by the server. Logs go to stderr.

**4. Errors fail closed, quietly.** If `blocked_apps.txt` can't be read, the core raises `BlockedAppsError`. The SDK turns that into a result with `is_error: true` and a generic message. The traceback, including the file path, stays on the server's stderr, so nothing about your machine reaches the cloud. We don't translate the exception into something friendlier, because that would be logic in the wrapper.

**5. SDK v1 vs v2.** Most tutorials online show v1: `from mcp.server.fastmcp import FastMCP`. In v2 (what we use) that import path is gone and the class is `MCPServer` (`from mcp.server import MCPServer`). Python result fields are snake_case (`structured_content`, `is_error`, `input_schema`), while the JSON on the wire stays camelCase (`structuredContent`, `inputSchema`).

## What happens when you run it

Real `tools/list` output from the MCP Inspector (the official debugging client). It's safe to show because it contains no window data (trimmed):
```
{"tools": [{
  "name": "list_open_windows",
  "description": "List the windows open on the user's Windows desktop, front-most first. ...",
  "inputSchema":  {"type": "object", "properties": {}},          <- takes no arguments
  "outputSchema": {"type": "object",
     "properties": {"result": {"type": "array", "items": {"$ref": "#/$defs/Window"}}},
     "$defs": {"Window": {"properties": {"title": {"type": "string"}, "app": {"type": "string"},
               "focused": {"type": "boolean"}}, "required": ["title", "app", "focused"]}}},
  "annotations": {"readOnlyHint": true, "openWorldHint": false}}]}
```
The `tools/call` output contains real titles, so it was piped straight into a filter that prints only counts:
```
isError: False
windows: 6          focused: 1          masked: 0
every window has exactly title/app/focused: True
same_as_core: True   <- the MCP result is identical to calling the core function directly
```
**An encoding gotcha from the first run:** that filter first said `same_as_core: False` for one VS Code window. The title contained one non-ASCII character, MCP sends UTF-8, but a Windows pipe decodes stdin as `cp1252` by default, so the filter misread one character. The fix was `sys.stdin.buffer.read().decode("utf-8")`. The server was fine all along. When text crosses a process boundary on Windows, always state the encoding.

**Controlled check through the real stdio server:** open Notepad, add `notepad.exe` to the list, call the tool via MCP. The masked count went 0 → 1. Then the list was restored byte-for-byte and only that Notepad window was closed.

## M3 schema vs M5 tool, side by side

| | M3 (`agent_tool_schemas.py`) | M5 (MCP `tools/list`) |
|---|---|---|
| Envelope | `{"type": "function", "function": {...}}` | the tool object directly |
| Inputs | `parameters`, written by hand | `inputSchema`, generated from type hints |
| Output | not described; the model reads text | `outputSchema` from `-> list[Window]` |
| Safety hints | none | `readOnlyHint`, `openWorldHint` |
| Schema/code drift | caught by the M3 contract test | can't happen: the schema *is* the signature |

When Hermes connects (M6), it converts each MCP tool back into the OpenAI `{"type": "function", ...}` shape, named `mcp_<server>_list_open_windows`. The model ends up seeing exactly the M3 format. That's D11: one core function, any brain.

## Try this

1. Add `print("hello")` at the top of `mcp_server.py` and connect a client. The SDK client logs an `Invalid JSON` validation error for the `hello` line, because stdout is the protocol. Whether the connection survives depends on the client. Remove it.
2. Rename `pseudo_hands/core/blocked_apps.txt` for a moment and call the tool. You get `isError: true` with a generic message, and the real reason appears on stderr. Rename it back.
3. Change `LIST_OPEN_WINDOWS_DESCRIPTION` and rerun `tools/list`. That text is all a model knows about when to call the tool. The tests still pass, because they compare against the same constant: a description is a design choice, not something a test can judge.

## Check yourself

1. What are the three steps every MCP connection goes through?
2. Why can't a bug in `mcp_server.py` skip the blocked-apps mask?
3. Why stdio and not HTTP for a tool that reads your screen?
4. Why must nothing in the server or the core `print()`?
5. Where did `outputSchema` come from, given that we never wrote it?

<details>
<summary>Answers</summary>

1. `initialize` (the handshake), `tools/list` (discover tools and schemas), `tools/call` (run one).
2. The server has no function of its own; it registers the core function object directly, and the mask runs inside the core. A test fails if anyone adds a `def` to the server.
3. stdio opens no port, so only the process that started the server can talk to it. A localhost HTTP server could be queried by any local program, or even a web page, and would need auth.
4. stdout carries the JSON-RPC messages. Anything else printed there is garbage to the client: at best it's logged and skipped, at worst it corrupts a message or drops the connection.
5. From the return type hint `-> list[Window]`. The SDK turned the `TypedDict` into JSON Schema and wrapped the list in `{"result": ...}`.

</details>

## How this connects to Pseudo's final architecture

- **M6:** Hermes' config will start this server with the same command the Inspector used (the venv's `python -m pseudo_hands.mcp_server`, with the repo as the working directory).
- **Phase 3 tools** (`focus_window`, the UI Automation reader) get one `add_tool(...)` line each here. Their logic and their approval gate live in `core/`.
- **A future web-UI face (L5)** might need an HTTP transport. That's a change to `server.run(...)`, not to the tools.
