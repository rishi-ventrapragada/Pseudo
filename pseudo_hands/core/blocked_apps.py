"""M4: the privacy check for window listing. Blocked apps send nothing (D6).

What it demonstrates: the privacy rule lives next to the tool, inside Pseudo's
core, not in the MCP wrapper or in the brain (D11). Whoever calls
list_open_windows() gets windows that were already masked here.

The rules, all "fail closed" (when unsure, mask; DECISIONS.md D6):
  1. An app is judged by its process name (e.g. "KeePass.exe"), never by its
     window title. A title is whatever the app chooses to show; the process
     name says which program it really is.
  2. If we can't tell which program owns a window, it is treated as blocked.
  3. If the list itself can't be read, list_open_windows() returns nothing.
"""

from pathlib import Path

BLOCKED_APPS_FILE = Path(__file__).resolve().parent / "blocked_apps.txt"
RESTRICTED = "[restricted app]"


class BlockedAppsError(Exception):
    """The blocked-apps list could not be loaded, so no window may be returned."""


def parse_blocked_apps(text: str) -> set[str]:
    """One process name per line, '#' starts a comment. Lowercased for matching."""
    names = set()
    for line in text.splitlines():
        name = line.split("#", 1)[0].strip()  # drop the comment, then the spaces
        if name:
            names.add(name.lower())
    return names


def load_blocked_apps() -> set[str]:
    """Read blocked_apps.txt. Raises BlockedAppsError instead of guessing."""
    try:
        text = BLOCKED_APPS_FILE.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise BlockedAppsError(f"can't read the blocked-apps list {BLOCKED_APPS_FILE}: {error}") from None
    return parse_blocked_apps(text)


def is_blocked(app: str | None, blocked: set[str]) -> bool:
    """An unknown app (None) counts as blocked: when unsure, mask."""
    return app is None or app.lower() in blocked


def mask_if_blocked(title: str, app: str | None, blocked: set[str]) -> tuple[str, str]:
    """The (title, app) a model may see: unchanged, or both replaced by RESTRICTED."""
    if is_blocked(app, blocked):
        return RESTRICTED, RESTRICTED
    return title, app
