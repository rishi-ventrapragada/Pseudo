"""M42: an app's name as people know it ("Brave Browser", not "brave.exe"), for the look-at chip.

What it demonstrates: Windows keeps a friendly name INSIDE every program file, in its version
information (its "FileDescription"). Task Manager shows that name. Reading it needs only the
program's path: never the window, its title or its text, so it says nothing about what you're doing.
If anything fails (a program running as admin won't give its path; some have no description), the
exe name without ".exe" is used instead.
The name is shown in Pseudo's own window only. No model is offered the tool that returns it (D29).
"""

import psutil
import pywintypes
import win32api

MAX_CHARS = 40


def description(path: str) -> str:
    """The program file's own FileDescription, or "" if it has none."""
    try:
        language, codepage = win32api.GetFileVersionInfo(path, "\\VarFileInfo\\Translation")[0]
        text = win32api.GetFileVersionInfo(path, f"\\StringFileInfo\\{language:04x}{codepage:04x}\\FileDescription")
    except (pywintypes.error, IndexError, TypeError, ValueError):  # no version info, or no language in it
        return ""
    return text if isinstance(text, str) else ""


def display_name(process_id: int, app: str | None) -> str:
    """The app's own name, one plain line of at most 40 characters; else its exe name without ".exe"."""
    try:
        path = psutil.Process(process_id).exe()
    except (psutil.Error, OSError, ValueError):  # it just ended, or runs as admin and won't say
        path = ""
    text = "".join(ch for ch in description(path) if ch.isprintable() or ch.isspace()) if path else ""
    name = " ".join(text.split())  # one line, single spaces
    if not name:
        name = app or ""
        name = name[:-4] if name.lower().endswith(".exe") else name
    return name[:MAX_CHARS]
