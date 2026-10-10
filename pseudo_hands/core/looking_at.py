"""M42: looking_at(): which app read_active_window WOULD read right now, for the chip in Pseudo's window.

What it demonstrates: telling you what Pseudo will look at, without looking. The chip in the
question box says "Looking at Brave Browser". To know that, this picks the window exactly as
read_active_window does (pick_window: the front-most window that isn't an assistant app or one of
Pseudo's own), and then reads NOTHING from it: not its title, not its text. It also leaves the
control ids from the last read alone (control_ids.py), so act_on_control isn't affected.
  - A blocked app is reported as private, with no name (blocked_apps.txt).
  - If either list can't be read, or there is no window, there is no app, so nothing is shown.
It is brain-only (D29): Pseudo's brain asks it for the window; no model is ever offered it.
"""

from typing import TypedDict

from pseudo_hands.core.active_window import pick_window
from pseudo_hands.core.app_names import display_name
from pseudo_hands.core.assistant_apps import AssistantAppsError
from pseudo_hands.core.blocked_apps import BlockedAppsError, is_blocked, load_blocked_apps

LISTS_UNREADABLE = "a list of apps can't be read: nothing to show"


class LookingAt(TypedDict):
    app: str  # the app's own name ("Brave Browser"), or "" when there is none to show
    private: bool  # a blocked app: Pseudo won't read it, and its name isn't shown either
    note: str  # why there is no app, or ""


def looking_at() -> LookingAt:
    """The app of the window read_active_window would pick now. Never raises."""
    try:
        blocked = load_blocked_apps()
        raw = pick_window()
    except (BlockedAppsError, AssistantAppsError):
        return {"app": "", "private": False, "note": LISTS_UNREADABLE}
    if raw is None:
        return {"app": "", "private": False, "note": "no window"}
    if is_blocked(raw.app, blocked):  # an unknown owner counts as blocked too
        return {"app": "", "private": True, "note": ""}
    return {"app": display_name(raw.process_id, raw.app), "private": False, "note": ""}
