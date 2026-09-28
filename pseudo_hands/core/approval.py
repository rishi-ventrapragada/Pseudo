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
  - It goes in the always-on-top layer, in front of normal windows, even though Windows
    won't let a background process take keyboard focus. We don't try: a popup that
    grabs your keyboard mid-sentence invites accidental answers. MB_TOPMOST alone
    didn't always stick in the real test (2 of 8 popups), so pin_on_top() also pins
    the box there itself once it appears, without activating it.
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
FLAGS = win32con.MB_OKCANCEL | win32con.MB_ICONWARNING | win32con.MB_DEFBUTTON2 | win32con.MB_TOPMOST


def approved(answer: int, elapsed: float, timeout: float) -> bool:
    """The whole rule: OK, clicked in time. Anything else (Cancel, Esc, X, 0 = error) is no."""
    return answer == win32con.IDOK and elapsed < timeout


def find_popup(thread_id: int) -> int:
    """The dialog box that thread is showing, or 0. Only that thread's windows are looked at."""
    found: list[int] = []

    def check(handle: int, _extra: None) -> bool:
        if win32gui.GetClassName(handle) == DIALOG_CLASS:
            found.append(handle)
        return True

    try:
        win32gui.EnumThreadWindows(thread_id, check, None)
    except pywintypes.error:  # the thread has no windows (yet, or any more)
        pass
    return found[0] if found else 0


def pin_on_top(thread_id: int) -> None:
    """Run in a helper thread: once the box is visible, pin it in the always-on-top layer."""
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        popup = find_popup(thread_id)
        if popup and win32gui.IsWindowVisible(popup):
            flags = win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE  # don't take focus
            try:
                win32gui.SetWindowPos(popup, win32con.HWND_TOPMOST, 0, 0, 0, 0, flags)
            except pywintypes.error:  # refused: the box is still shown, and no answer still means no
                pass
            return
        time.sleep(0.02)


def close_popup(thread_id: int) -> None:
    """Run by the timer: close the box that thread is showing, as if the X was clicked."""
    popup = find_popup(thread_id)
    if popup:
        win32gui.PostMessage(popup, win32con.WM_CLOSE, 0, 0)  # X -> Cancel -> no


def show_popup(question: str, timeout: float = TIMEOUT_SECONDS) -> bool:
    """Show the popup and wait at most `timeout` seconds. True only for OK in time."""
    thread_id = win32api.GetCurrentThreadId()
    threading.Thread(target=pin_on_top, args=(thread_id,), daemon=True).start()
    timer = threading.Timer(timeout, close_popup, args=(thread_id,))
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
