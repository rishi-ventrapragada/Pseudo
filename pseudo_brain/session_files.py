"""M41: renaming, deleting and searching your saved chats (%LOCALAPPDATA%\\Pseudo\\sessions).

What it demonstrates: a DELETE that can only reach the file it was meant for. The face sends a chat's
NAME, never a path, and this file decides whether that name may be touched at all. It is the M3
sandbox idea again (and M24's for the memory vault), written here because the brain never imports
pseudo_hands' core: it reaches core only through MCP tools (D11). A chat may be changed only if:
  1. its name looks exactly like one Pseudo makes: a date and time in ASCII digits, so it can't be
     "..\\..\\x", "C:\\Windows", "*" or a name with a slash in it;
  2. the Pseudo and sessions folders are real folders, not links or junctions: a junction would
     quietly make "inside the sessions folder" mean somewhere else on the disk;
  3. its file sits directly inside, as a plain file: not a link, and not a hard link (a second name
     for a file that also lives somewhere else, so rewriting it would change that file too);
  4. it is a chat Pseudo saved: it reads as one, and its "started" is its own name.
Anything else is refused with the reason, and nothing is touched.

Search reads each chat's title and YOUR messages, never the answers: the sidebar's search is about
what you asked.
"""

import json
import os
import stat
import unicodedata
from pathlib import Path

from pseudo_brain import session as sessions  # sessions.SESSIONS_DIR is read on every call, so tests can move it

MAX_SEARCH_CHARS = 200


class SessionRefused(Exception):
    """Pseudo won't rename or delete that chat; the reason says why. Nothing was touched."""


def is_link(path: Path) -> bool:
    """A symlink or a junction (both are "reparse points" on Windows), even a broken one."""
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return False
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def checked_file(name: object) -> tuple[Path, dict, dict]:
    """The saved chat called `name`, if Pseudo may change it: its file, what it holds, and its sidebar item.

    Raises SessionRefused (rules 1 to 4 above)."""
    if not isinstance(name, str) or not sessions.SESSION_NAME.fullmatch(name):
        raise SessionRefused("that is not a chat name Pseudo makes")
    folder = sessions.SESSIONS_DIR
    for part in (folder.parent, folder):
        if is_link(part):
            raise SessionRefused(f"the {part.name} folder is a link; Pseudo only changes chats in a real folder")
    path = folder / f"{name}.json"
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        raise SessionRefused(f"there is no saved chat called {name}") from None
    if is_link(path) or not stat.S_ISREG(info.st_mode) or info.st_nlink > 1:
        raise SessionRefused("that chat's file isn't a plain file Pseudo saved: it is a link, a hard link or a folder")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data["started"] != name:
            raise ValueError("another chat's name")
        item, _asked = sessions.session_item(name, data)
    except (OSError, ValueError, KeyError, TypeError):
        raise SessionRefused("that file isn't a chat Pseudo saved") from None
    return path, data, item


def clean_title(title: object) -> str:
    """A chat's new name: one line of 1 to 60 plain characters. Raises SessionRefused."""
    text = title.strip() if isinstance(title, str) else ""
    if not text:
        raise SessionRefused("a chat's name can't be empty")
    if any(unicodedata.category(ch).startswith("C") for ch in text):  # line breaks, tabs, invisible marks
        raise SessionRefused("a chat's name must be one line of plain characters")
    if len(text) > sessions.TITLE_CHARS:
        raise SessionRefused(f"a chat's name can be at most {sessions.TITLE_CHARS} characters")
    return text


def rename_session(name: object, title: object) -> str:
    """Give a saved chat a new name; nothing else in its file changes. Returns the name. Raises SessionRefused."""
    clean = clean_title(title)
    path, data, _item = checked_file(name)
    data["title"] = clean
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return clean


def delete_session(name: object) -> str:
    """Delete one saved chat's file. Returns its title, for the face's notice. Raises SessionRefused."""
    path, _data, item = checked_file(name)
    path.unlink()
    return item["title"]


def search_sessions(text: object) -> list[dict]:
    """The saved chats whose title or one of YOUR messages contains `text`, in any case, newest first."""
    wanted = text.strip().casefold()[:MAX_SEARCH_CHARS] if isinstance(text, str) else ""
    if not wanted:
        return sessions.list_sessions()
    return [item for item, asked in sessions.saved_chats()
            if any(wanted in str(part).casefold() for part in [item["title"], *asked])]
