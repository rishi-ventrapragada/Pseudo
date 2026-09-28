"""M10: short ids for windows ("w1", "w2", ...), so a model can point at a window.

What it demonstrates: a model can't name a window by its title, because titles
are redacted before it sees them (two windows may both read "Chat with [PERSON]").
So list_open_windows() hands out opaque ids, like primary keys in a database, and
focus_window() takes only an id. This registry remembers what each id means:
(window handle, process id). The handle is Windows' number for the window; the
process id lets us notice when Windows reuses a handle for a different program.

Rules:
  - the same window keeps the same id across listings (w3 stays Notepad)
  - an id is never handed out twice; the counter only goes up
  - only list_open_windows() creates ids, so the model can only point at windows
    it was shown (blocked apps and Pseudo's own windows never get one)
"""

import threading


class WindowIds:
    def __init__(self) -> None:
        self._by_window: dict[tuple[int, int], str] = {}  # (handle, process id) -> "w3"
        self._by_id: dict[str, tuple[int, int]] = {}  # "w3" -> (handle, process id)
        self._lock = threading.Lock()  # the MCP server may run two tool calls at once

    def id_for(self, handle: int, process_id: int) -> str:
        """The window's id, creating a new one the first time we see this window."""
        key = (handle, process_id)
        with self._lock:
            if key not in self._by_window:
                new_id = f"w{len(self._by_id) + 1}"  # nothing is ever removed, so this never repeats
                self._by_window[key] = new_id
                self._by_id[new_id] = key
            return self._by_window[key]

    def find(self, window_id: str) -> tuple[int, int] | None:
        """(handle, process id) for an id we handed out, or None for anything else."""
        with self._lock:
            return self._by_id.get(window_id.strip().lower())


registry = WindowIds()  # one per process; tests swap in a fresh one
