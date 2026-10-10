"""M42: the memory browser: your saved notes, listed and opened READ-ONLY, redacted again (D23).

What it demonstrates: a second door into the vault that is no wider than the first. M24's search
reads notes only through memory.py's checks, and the browser reuses exactly those:
  1. ONE folder, %LOCALAPPDATA%\\Pseudo\\memory\\tasks, with no link anywhere from the Pseudo
     folder down (memory.tasks_folder). Nothing Pseudo's window sends can change it.
  2. Only notes directly inside, named as Pseudo names them (2026-10-02-091500-123.md), that are
     plain files: not a link, not a hard link, at most 20,000 bytes, UTF-8 (readable_note).
     open_memory gets a NAME, never a path, and the name must fully match that shape.
  3. Everything shown is redacted AGAIN: you may have typed a name into a note in Obsidian.
  4. Read-only: nothing here opens a file for writing. Editing and deleting stay in Obsidian (D23).
It is brain-only (D29): Pseudo's brain asks it for your window; no model is ever offered it.
"""

import os
import re
from typing import TypedDict

from pseudo_hands.core import memory
from pseudo_hands.core.memory_search import note_parts, readable_note
from pseudo_hands.core.redactor import RedactionError, redact

NOTE_NAME = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}-[0-9]{6}-[0-9]{3}\.md")  # memory.new_note's names, ASCII digits
MAX_LISTED = 200
WITHHELD = "[content withheld]"
NOT_OPENED = "that memory can't be opened: it is missing, or not a plain note Pseudo can read"


class MemoryItem(TypedDict):
    name: str
    date: str  # 2026-10-02, or "undated"
    title: str  # redacted again


class MemoryList(TypedDict):
    items: list[MemoryItem]  # newest first
    note: str  # why there are none, or ""


class MemoryNote(TypedDict):
    name: str
    date: str
    title: str
    question: str  # redacted again
    answer: str  # redacted again
    note: str  # why it can't be opened, or ""


_titles: dict[tuple[str, int], str] = {}  # (name, the note's text) -> its redacted title: redacted once per version


def safe(text: str) -> str:
    """Redacted again; if redaction fails, nothing of it is shown."""
    try:
        return redact(text)
    except RedactionError:
        return WITHHELD


def list_memories() -> MemoryList:
    """Your saved notes, newest first (at most 200): name, date and title. Never raises."""
    try:
        folder = memory.tasks_folder(create=False)
    except memory.VaultRefused as refusal:
        return {"items": [], "note": str(refusal)}
    try:
        with os.scandir(folder) as entries:
            names = sorted((entry.name for entry in entries if NOTE_NAME.fullmatch(entry.name)), reverse=True)
    except OSError:
        return {"items": [], "note": "the memory folder can't be read"}
    items: list[MemoryItem] = []
    for name in names:
        text = readable_note(folder / name)  # the checks run every time; only the redaction is remembered
        if text is None:
            continue
        date, title, _question, _answer = note_parts(text)
        key = (name, hash(text))
        _titles[key] = _titles.get(key) or safe(title)
        items.append({"name": name, "date": date, "title": _titles[key]})
        if len(items) == MAX_LISTED:
            break
    return {"items": items, "note": "" if items else "no saved memories yet"}


def open_memory(name: str) -> MemoryNote:
    """One saved note, by its NAME, redacted again. Never raises: a refusal is in `note`."""
    empty: MemoryNote = {"name": "", "date": "", "title": "", "question": "", "answer": "", "note": ""}
    if not isinstance(name, str) or not NOTE_NAME.fullmatch(name):
        return {**empty, "note": "that is not a memory name Pseudo makes"}
    try:
        folder = memory.tasks_folder(create=False)
    except memory.VaultRefused as refusal:
        return {**empty, "note": str(refusal)}
    text = readable_note(folder / name)
    if text is None:
        return {**empty, "note": NOT_OPENED}
    date, title, question, answer = note_parts(text)
    return {"name": name, "date": date, "title": safe(title), "question": safe(question), "answer": safe(answer),
            "note": ""}
