"""M4: Pseudo's first "eye". Lists the windows open on the desktop.

What it demonstrates: perception is just calling an operating-system API.
Windows keeps a list of top-level windows (like the DOM keeps top-level
elements). We walk that list, keep the ones a person would actually see, and
return plain data a model can read. No MCP and no agent code here (D11): the
M5 MCP server will call list_open_windows() unchanged.

Privacy is applied HERE, before anything is returned: windows of blocked apps
come back as "[restricted app]" (see blocked_apps.py and DECISIONS.md D6).
"""

import ctypes
import ctypes.wintypes
from dataclasses import dataclass
from typing import TypedDict

import psutil
import pywintypes
import win32gui
import win32process

from pseudo_hands.core.blocked_apps import load_blocked_apps, mask_if_blocked

DWMWA_CLOAKED = 14  # the id of the "is this window cloaked?" attribute in the Windows API


class Window(TypedDict):
    """One open window, as a model will see it. Plain types, so it becomes JSON as-is."""

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


def read_all_windows() -> list[RawWindow]:
    """Ask Windows for every top-level window, front-most first (the "z-order")."""
    handles: list[int] = []

    def remember(handle: int, _extra: None) -> bool:
        handles.append(handle)
        return True  # True = "keep going, give me the next window"

    win32gui.EnumWindows(remember, None)  # calls remember() once per window
    focused = win32gui.GetForegroundWindow()

    windows = []
    for handle in handles:
        try:
            _thread_id, process_id = win32process.GetWindowThreadProcessId(handle)
            windows.append(RawWindow(
                title=win32gui.GetWindowText(handle),
                app=app_name(process_id),
                visible=bool(win32gui.IsWindowVisible(handle)),
                cloaked=is_cloaked(handle),
                focused=handle == focused,
            ))
        except pywintypes.error:  # the window closed while we were looking at it
            continue
    return windows


def is_user_window(window: RawWindow) -> bool:
    """Would a person see this window? Visible, not cloaked, and it has a title."""
    return window.visible and not window.cloaked and window.title.strip() != ""


def list_open_windows() -> list[Window]:
    """The windows a person can see, front-most first, with blocked apps masked.

    Raises BlockedAppsError if the blocked-apps list can't be read: without the
    list we can't know what to hide, so nothing is returned (fail closed, D6).
    """
    blocked = load_blocked_apps()  # first, so a broken list stops us before we read any window
    result: list[Window] = []
    for raw in read_all_windows():
        if not is_user_window(raw):
            continue
        title, app = mask_if_blocked(raw.title, raw.app, blocked)
        result.append({"title": title, "app": app, "focused": raw.focused})
    return result
