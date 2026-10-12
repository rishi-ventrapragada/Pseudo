# pseudo_hands

Pseudo's eyes and hands on Windows. It lists your windows, reads the one you were on, and clicks or types in it, and it holds the privacy rules every time:

- **Blocked apps** (`core/blocked_apps.txt`, yours to edit) are never read.
- **Assistant apps** (`core/assistant_apps.txt`), Pseudo's own window included, are never read, focused or acted on.
- **Everything read is redacted** on the laptop before it is returned (`core/redactor.py`: Presidio and spaCy, Indian phone and ID patterns, and a names list from Wikidata). If redaction fails, nothing is returned.
- **Every action asks first** in a native popup whose default answer is no (`core/approval.py`). At most 4 action popups in 2 minutes.
- **Memory** notes are saved only after you approve, redacted, in `%LOCALAPPDATA%\Pseudo\memory\tasks`, and are read back redacted again.

Every one of those decisions lives in `core/`, plain Python that never imports MCP or a model SDK. `mcp_server.py` is a thin wrapper that publishes the core functions as MCP tools, so the rules hold for any brain that calls them. Which tools a model may be offered is decided in `pseudo_brain/providers.toml` (decision D29).

```
python -m pseudo_hands.mcp_server         the MCP server over stdio (pseudo_brain starts it for you)
python -m pseudo_hands.show_windows       a terminal demo: your open windows, as Pseudo sees them
python -m pseudo_hands.show_active_window a terminal demo: the window Pseudo would read, redacted
```
