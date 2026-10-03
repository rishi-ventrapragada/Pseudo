"""M10: the approval gate (DECISIONS.md D13). Every action asks here first, and the
answer is NO unless a person clicks OK in time.

What it demonstrates: consent enforced by the tool itself, not by the brain. A brain
may auto-approve (Hermes one-shot mode) or have nobody watching; this gate still
holds, because it lives in core next to the action (D11).

How the popup works:
  - It's Windows' standard message box (MessageBoxW), shown by THIS process from the
    tool's own thread. Why this process: Windows only lets a program bring a window
    to the front if it received the user's last input. Your OK click lands here, so
    your click is exactly what makes the focus change allowed.
  - MB_SYSTEMMODAL keeps the box in the always-on-top layer, in front of normal windows,
    even when Windows won't let this background process take the keyboard. MB_TOPMOST
    asks for the same layer, but Windows drops it whenever the box isn't allowed to come
    to the front (P7 lab: 0 of 3 on top without the face's grant; with MB_SYSTEMMODAL,
    3 of 3). The box takes the keyboard only when the face passed its right on
    (face/foreground.js), and even then Enter means no.
  - Default NO: Cancel is the default button (so Enter means no) and OK has no
    keyboard shortcut. Cancel, Esc, the X, the timeout, any error, or another popup
    already being open all mean no.
  - The timeout: a timer thread closes the box after TIMEOUT_SECONDS, sending the
    same message as the X. 20 s is shorter than the brain's tool timeout (Hermes: 30 s),
    so the popup is always gone before the brain stops waiting for the answer.
"""

import ctypes
import threading
import time
from collections.abc import Callable

import pywintypes
import win32api
import win32con
import win32gui

POPUP_TITLE = "Pseudo: approve this action?"
TIMEOUT_SECONDS = 20.0
DIALOG_CLASS = "#32770"  # the class name Windows gives every standard dialog box
FLAGS = (win32con.MB_OKCANCEL | win32con.MB_ICONWARNING | win32con.MB_DEFBUTTON2 | win32con.MB_TOPMOST
         | win32con.MB_SYSTEMMODAL)


def approved(answer: int, elapsed: float, timeout: float) -> bool:
    """The whole rule: OK, clicked in time. Anything else (Cancel, Esc, X, 0 = error) is no."""
    return answer == win32con.IDOK and elapsed < timeout


def close_popup(thread_id: int) -> None:
    """Run by the timer: close the dialog that thread is showing, as if the X was clicked."""
    def close(handle: int, _extra: None) -> bool:
        if win32gui.GetClassName(handle) == DIALOG_CLASS:
            win32gui.PostMessage(handle, win32con.WM_CLOSE, 0, 0)  # X -> Cancel -> no
        return True

    try:
        win32gui.EnumThreadWindows(thread_id, close, None)  # only that thread's windows
    except pywintypes.error:  # it was answered a moment ago and is already gone
        pass


def show_popup(question: str, timeout: float = TIMEOUT_SECONDS) -> bool:
    """Show the popup and wait at most `timeout` seconds. True only for OK in time."""
    timer = threading.Timer(timeout, close_popup, args=(win32api.GetCurrentThreadId(),))
    started = time.monotonic()
    timer.start()
    try:
        # ctypes lets go of Python's GIL while the box is open, so the timer thread can run.
        answer = ctypes.windll.user32.MessageBoxW(None, question, POPUP_TITLE, FLAGS)
    finally:
        timer.cancel()
    return approved(answer, time.monotonic() - started, timeout)


# ---------- the gate: what every action tool calls ----------

approver: Callable[[str], bool] = show_popup  # tests swap in a fake, like agent_tools.approver in M3
_one_at_a_time = threading.Lock()


def ask(question: str) -> bool:
    """True only if a person approved. Never raises: every failure means no."""
    if not _one_at_a_time.acquire(blocking=False):
        return False  # a popup is already open: never stack a second one on top
    try:
        return approver(question) is True
    except Exception:  # noqa: BLE001 - a broken popup must never count as yes
        return False
    finally:
        _one_at_a_time.release()
