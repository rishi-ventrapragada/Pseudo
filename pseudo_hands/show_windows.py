"""M4: a thin terminal demo for list_open_windows(). Run it from the repo root:

    python -m pseudo_hands.show_windows

What it demonstrates: a wrapper with no logic of its own (D11). It only calls
core functions and prints what they return. The M5 MCP server has the same
shape: call list_open_windows(), hand the result to whoever asked.

Privacy: this prints your real window titles to YOUR terminal. Don't paste the
output into a chat with a cloud model; that's the leak Pseudo exists to prevent.
"""

import json

from pseudo_hands.core.blocked_apps import RESTRICTED, load_blocked_apps
from pseudo_hands.core.windows import is_user_window, list_open_windows, read_all_windows


def main() -> None:
    print("--- BLOCKED-APPS LIST (pseudo_hands/core/blocked_apps.txt) ---")
    print(", ".join(sorted(load_blocked_apps())) or "(empty)")

    print("\n--- ASKING WINDOWS FOR EVERY TOP-LEVEL WINDOW ---")
    raw = read_all_windows()
    print(f"{len(raw)} windows in total (most are invisible helper windows)")
    print(f"{sum(is_user_window(w) for w in raw)} are visible, not cloaked, and have a title")

    print("\n--- WHAT list_open_windows() RETURNS (what a model would see) ---")
    windows = list_open_windows()
    for window in windows:
        marker = "*" if window["focused"] else " "
        print(f" {marker} {window['app']:<24} {window['title']}")
    masked = sum(w["title"] == RESTRICTED for w in windows)
    print(f"{len(windows)} windows, {masked} masked as {RESTRICTED!r}  (* = focused)")

    print("\n--- THE FIRST TWO AS JSON (the shape the M5 MCP server will send) ---")
    print(json.dumps(windows[:2], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
