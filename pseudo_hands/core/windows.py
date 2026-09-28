"""M4: Pseudo's first "eye". Lists the windows open on the desktop.

What it demonstrates: perception is just calling an operating-system API.
Windows keeps a list of top-level windows (like the DOM keeps top-level
elements). We walk that list, keep the ones a person would actually see, and
return plain data a model can read. No MCP and no agent code here (D11): the
M5 MCP server will call list_open_windows() unchanged.

Privacy is applied HERE, before anything is returned (DECISIONS.md D6):
  1. windows of blocked apps come back as "[restricted app]" (blocked_apps.py, M4)
  2. every other title goes through the local redactor (redactor.py, M8), and
     a title the redactor can't process comes back as "[title withheld]", never raw.
(M10) Each window also gets a short id for focus_window(). Blocked apps and
Pseudo's own windows (the approval popup, D14) get None: nothing to point at.
(M12) Invisible and click-through overlays (e.g. a GPU overlay) aren't windows a
person reads: they're dropped by is_user_window(), so they're never listed, never
get an id, and are never read or focused.
"""

import ctypes
import ctypes.wintypes
import os
from dataclasses import dataclass
from typing import TypedDict

import psutil
import pywintypes
import win32con
import win32gui
import win32process

from pseudo_hands.core import window_ids
from pseudo_hands.core.blocked_apps import RESTRICTED, load_blocked_apps, mask_if_blocked
from pseudo_hands.core.redactor import RedactionError, redact

DWMWA_CLOAKED = 14  # the id of the "is this window cloaked?" attribute in the Windows API
TITLE_WITHHELD = "[title withheld]"


class Window(TypedDict):
    """One open window, as a model will see it. Plain types, so it becomes JSON as-is."""

    id: str | None  # (M10) "w3", for focus_window(); None = this window can't be acted on
    title: str
    app: str
    focused: bool


@dataclass
class RawWindow:
    """Everything we read about one window, before filtering and masking."""

    title: str
    app: str | None  # None = Windows wouldn't tell us which program owns it
    visible: bool
    cloaked: bool
    focused: bool
    handle: int = 0  # (M9) Windows' id for the window, so a reader can open exactly this one
    process_id: int = 0  # (M10) which running program owns it; tells a reused handle apart
    overlay: bool = False  # (M12) invisible or click-through: see is_overlay_style()


def is_overlay_style(ex_style: int) -> bool:
    """(M12) Judge a window by its extended style bits: click-through (TRANSPARENT: clicks
    fall through to what's behind), or a tool window that can never become the active one.
    LAYERED alone is NOT enough: Electron apps (Claude, VS Code) are layered too."""
    never_active_tool = ex_style & win32con.WS_EX_TOOLWINDOW and ex_style & win32con.WS_EX_NOACTIVATE
    return bool(ex_style & win32con.WS_EX_TRANSPARENT or never_active_tool)


def is_cloaked(handle: int) -> bool:
    """True for windows Windows itself keeps hidden (e.g. suspended Store apps).

    They still say IsWindowVisible() == True, so without this check ghost
    windows like "Settings" show up. pywin32 has no wrapper for this one call,
    so ctypes calls the function in dwmapi.dll directly.
    """
    cloaked = ctypes.c_int(0)
    result = ctypes.windll.dwmapi.DwmGetWindowAttribute(
        ctypes.wintypes.HWND(handle), DWMWA_CLOAKED, ctypes.byref(cloaked), ctypes.sizeof(cloaked)
    )
    return result == 0 and cloaked.value != 0  # result 0 means "the call worked"


def app_name(process_id: int) -> str | None:
    """Process id -> program name, e.g. 4120 -> "Code.exe". None if we can't find out."""
    try:
        return psutil.Process(process_id).name()
    except psutil.Error:  # the process just ended, or it runs as admin and won't say
        return None


def read_window(handle: int, focused: int) -> RawWindow | None:
    """Everything about one window, or None if it no longer exists. (M10: focus.py uses this too.)"""
    if not win32gui.IsWindow(handle):
        return None
    try:
        _thread_id, process_id = win32process.GetWindowThreadProcessId(handle)
        return RawWindow(
            title=win32gui.GetWindowText(handle),
            app=app_name(process_id),
            visible=bool(win32gui.IsWindowVisible(handle)),
            cloaked=is_cloaked(handle),
            focused=handle == focused,
            handle=handle,
            process_id=process_id,
            overlay=is_overlay_style(win32gui.GetWindowLong(handle, win32con.GWL_EXSTYLE)),
        )
    except pywintypes.error:  # the window closed while we were looking at it
        return None


def read_all_windows() -> list[RawWindow]:
    """Ask Windows for every top-level window, front-most first (the "z-order")."""
    handles: list[int] = []

    def remember(handle: int, _extra: None) -> bool:
        handles.append(handle)
        return True  # True = "keep going, give me the next window"

    win32gui.EnumWindows(remember, None)  # calls remember() once per window
    focused = win32gui.GetForegroundWindow()
    windows = [read_window(handle, focused) for handle in handles]
    return [window for window in windows if window is not None]


def is_user_window(window: RawWindow) -> bool:
    """Would a person see this window? Visible, not cloaked, has a title, (M12) not an overlay."""
    return window.visible and not window.cloaked and window.title.strip() != "" and not window.overlay


def safe_title(title: str) -> str:
    """The redacted title, or a placeholder if redaction fails. Never the raw title."""
    try:
        return redact(title)
    except RedactionError:  # one bad title is withheld; the other windows are still listed
        return TITLE_WITHHELD


def list_open_windows() -> list[Window]:
    """The windows a person can see, front-most first, blocked apps masked, titles redacted.

    Raises BlockedAppsError if the blocked-apps list can't be read: without the
    list we can't know what to hide, so nothing is returned (fail closed, D6).
    """
    blocked = load_blocked_apps()  # first, so a broken list stops us before we read any window
    result: list[Window] = []
    for raw in read_all_windows():
        if not is_user_window(raw):
            continue
        title, app = mask_if_blocked(raw.title, raw.app, blocked)
        window_id = None
        if title != RESTRICTED:  # blocked apps' titles never even reach the redactor
            title = safe_title(title)
            if raw.process_id != os.getpid():  # D14: never an id for Pseudo's own windows
                window_id = window_ids.registry.id_for(raw.handle, raw.process_id)
        result.append({"id": window_id, "title": title, "app": app, "focused": raw.focused})
    return result
