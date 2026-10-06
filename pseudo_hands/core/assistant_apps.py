"""M18, P8-fix: the assistant-apps list, the programs you talk to Pseudo (or another AI) through.

What it demonstrates: ONE rule, read in one place, used by every tool that needs it (D11).
Their windows are never Pseudo's target:
  - read_active_window skips them, so it reads the window you were on before switching (M18);
  - act_on_control refuses them (M28);
  - (P8-fix) list_open_windows gives them no id, and focus_window refuses them. Before this
    fix the face's own window got an id, so a model could ask to bring it to the front.
The list is assistant_apps.txt, in the same format as blocked_apps.txt. If it can't be read,
every one of those tools does nothing (fail closed): we can't tell the face from your window.

It lives in its own file because windows.py needs it too, and active_window.py (where it
started in M18) already imports windows.py: two files importing each other is a circular import.
"""

from pathlib import Path

from pseudo_hands.core.blocked_apps import parse_blocked_apps

ASSISTANT_APPS_FILE = Path(__file__).resolve().parent / "assistant_apps.txt"  # the face, Hermes, the Claude app


class AssistantAppsError(Exception):
    """assistant_apps.txt could not be read, so we can't tell the face from your window."""


def load_assistant_apps() -> set[str]:
    """Read assistant_apps.txt (lowercased names). Raises instead of guessing."""
    try:
        return parse_blocked_apps(ASSISTANT_APPS_FILE.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        raise AssistantAppsError(f"can't read {ASSISTANT_APPS_FILE.name}") from None


def is_assistant(app: str | None, assistants: set[str]) -> bool:
    """Is this program on the list? Judged by process name, like blocked apps (M4)."""
    return (app or "").lower() in assistants
