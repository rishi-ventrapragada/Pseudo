"""M10: focus_window(): Pseudo's first ACTION. Brings one window to the front, but
only if a person clicks OK in the approval popup.

What it demonstrates: an action tool is mostly checks. The one line that acts
(SetForegroundWindow) runs last, after everything below has passed, all in core
(D11, D13), so the rules hold for any brain:
  0. the blocked-apps list must load, or nothing happens (fail closed, D6)
  1. the id must be one list_open_windows() handed out, and its window must still
     exist, belong to the same program, and be a normal visible window
  2. Pseudo's own windows (the popup itself, D14) and blocked apps are never touched
  3. a window that's already in front needs no popup
  4. the popup: the person sees the REAL title (it stays on this screen) and must say yes
  5. check the window again: in 20 s it could have closed or been replaced
  6. act, then check it worked; if Windows refused, say so honestly
The model only ever gets the redacted title, never the popup's text.
"""

import os
from typing import TypedDict

import pywintypes
import win32con
import win32gui

from pseudo_hands.core import approval, window_ids
from pseudo_hands.core.blocked_apps import RESTRICTED, is_blocked, load_blocked_apps
from pseudo_hands.core.windows import RawWindow, is_user_window, read_window, safe_title

POPUP_TITLE_CHARS = 120

# What focus_window() reports back, as plain words a model can act on.
FOCUSED = "focused"
NOT_APPROVED = "not approved"  # denied, closed, or no answer in time: nothing was done
ALREADY_IN_FRONT = "already in front"
BLOCKED = "restricted"  # a blocked app: never shown in a popup, never touched
OWN_WINDOW = "own window"  # D14: a window of pseudo_hands itself, such as the popup
UNKNOWN_ID = "unknown id"  # not an id list_open_windows() handed out
WINDOW_GONE = "window gone"  # closed, hidden, or its handle now belongs to another program
FOCUS_REFUSED = "focus refused"  # approved, but Windows didn't let the focus change happen


class FocusResult(TypedDict):
    window_id: str
    title: str  # redacted, exactly as list_open_windows() shows it
    app: str
    status: str  # one of the statuses above


def result(window_id: str, status: str, title: str = "", app: str = "") -> FocusResult:
    return {"window_id": window_id, "title": title, "app": app, "status": status}


def still_there(handle: int, process_id: int) -> RawWindow | None:
    """The window read live now, or None if it closed, changed program, or was hidden."""
    raw = read_window(handle, win32gui.GetForegroundWindow())
    if raw is None or raw.process_id != process_id or not is_user_window(raw):
        return None
    return raw


def question(raw: RawWindow) -> str:
    """The popup's text, built only from what Windows reports. The model writes none of it."""
    title = raw.title if len(raw.title) <= POPUP_TITLE_CHARS else raw.title[:POPUP_TITLE_CHARS] + "…"
    return (
        "The assistant wants to bring this window to the front:\n\n"
        f"    App:    {raw.app}\n"
        f'    Title:  "{title}"\n\n'
        "Click OK to allow it.\n"
        f"Cancel, Esc, the X, or no answer within {approval.TIMEOUT_SECONDS:.0f} seconds means NO."
    )


def bring_to_front(handle: int) -> bool:
    """The action itself. True only if the window really is in front afterwards."""
    try:
        win32gui.SetForegroundWindow(handle)  # allowed because the person's OK click was our last input
    except pywintypes.error:  # Windows refused (its foreground lock): nothing was changed
        return False
    if win32gui.IsIconic(handle):  # minimized: restore it, but only now that focusing worked
        win32gui.ShowWindow(handle, win32con.SW_RESTORE)
    return win32gui.GetForegroundWindow() == handle


def focus_window(window_id: str) -> FocusResult:
    """Bring one listed window to the front if a person approves.

    Raises BlockedAppsError if the blocked-apps list can't be read (as list_open_windows does).
    """
    blocked = load_blocked_apps()  # 0. no list, no action
    key = window_ids.registry.find(window_id)  # 1. only ids we handed out
    if key is None:
        return result(window_id, UNKNOWN_ID)
    raw = still_there(*key)
    if raw is None:
        return result(window_id, WINDOW_GONE)
    if raw.process_id == os.getpid():  # 2. D14: never act on our own windows
        return result(window_id, OWN_WINDOW)
    if is_blocked(raw.app, blocked):  # 2. blocked apps: no popup, no action
        return result(window_id, BLOCKED, RESTRICTED, RESTRICTED)
    title, app = safe_title(raw.title), raw.app
    if raw.focused:  # 3. nothing to do
        return result(window_id, ALREADY_IN_FRONT, title, app)
    if not approval.ask(question(raw)):  # 4. THE GATE: a person decides
        return result(window_id, NOT_APPROVED, title, app)
    if still_there(*key) is None:  # 5. it closed or changed while the popup was open
        return result(window_id, WINDOW_GONE, title, app)
    focused = bring_to_front(raw.handle)  # 6. act, and check it worked
    return result(window_id, FOCUSED if focused else FOCUS_REFUSED, title, app)
