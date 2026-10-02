"""M24: Pseudo's memory: one redacted markdown note per answered task, saved only if you say yes (D23).

What it demonstrates: a feature whose every rule lives next to the data, in core (D11), so any
brain gets the same protection:
  1. The vault is ONE fixed folder, %LOCALAPPDATA%\\Pseudo\\memory\\tasks (local, not synced like
     Documents can be). Nothing the model or the question says can change it. Obsidian can open
     %LOCALAPPDATA%\\Pseudo\\memory as a vault: that's where you view, edit and delete notes.
  2. The question and the answer are redacted BEFORE anything is shown or written. A typed
     question goes to the model as typed once (L8), but a memory is sent again later, in other
     conversations, so it's stored redacted. Redaction fails -> nothing is saved.
  3. Every save asks you first, in the approval popup (D13): default no, 20 s, then no.
  4. The file name is the date and time only, never words from the question.
  5. Links are refused (symlinks, junctions, hard links): a link could point outside the vault.
Pseudo itself only creates and reads notes. It has no tool to edit or delete one: you do that.
"""

import os
import re
import stat
import time
from pathlib import Path
from typing import TypedDict

from pseudo_hands.core import approval
from pseudo_hands.core.redactor import RedactionError, redact

MEMORY_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Pseudo" / "memory"  # open this in Obsidian
TASKS_DIR = MEMORY_DIR / "tasks"
TITLE_CHARS = 80
MAX_ANSWER_CHARS = 2000
MAX_QUESTION_CHARS = 2000
POPUP_PREVIEW_CHARS = 200
METADATA = re.compile(r"[^A-Za-z0-9 ._/()·-]")  # properties stay one plain line each, no ":" (no YAML tricks)

# What save_memory() reports back.
SAVED = "saved"
NOT_APPROVED = "not approved"  # denied, closed, or no answer in time: nothing was written
NOT_SAVED = "not saved"  # something failed; the reason says what. Nothing was written


class SaveResult(TypedDict):
    status: str  # one of the three above
    note: str  # the new note's file name, or "" if nothing was written
    reason: str


class VaultRefused(Exception):
    """The vault folder (or a note) is a link, or isn't where it must be: Pseudo won't touch it."""


def is_link(path: Path) -> bool:
    """A symlink or a junction (both are "reparse points" on Windows), even a broken one."""
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return False
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def tasks_folder(create: bool) -> Path:
    """The vault's tasks folder, checked: no link anywhere from the memory folder down. Raises VaultRefused."""
    root = TASKS_DIR
    if create:
        root.mkdir(parents=True, exist_ok=True)
    for part in (root.parent, root):
        if is_link(part):
            raise VaultRefused(f"{part.name} is a link; Pseudo only uses a real folder")
    if not root.is_dir():
        raise VaultRefused("there is no memory folder yet")
    return root


def plain(value: str, limit: int = 80) -> str:
    """A property value: one short line of safe characters (the model's name, a tool's name...)."""
    return METADATA.sub("", str(value))[:limit]


def note_text(question: str, answer: str, tools: list[str], provider: str, model: str, session: str) -> str:
    """The note: properties Obsidian understands, a title, then the (already redacted) question and answer."""
    title = question.strip().splitlines()[0][:TITLE_CHARS] if question.strip() else "(no question)"
    return (f"---\ndate: {time.strftime('%Y-%m-%dT%H:%M:%S%z')}\nprovider: {plain(provider)}\nmodel: {plain(model)}\n"
            f"tools: [{', '.join(plain(t) for t in tools)}]\nsession: {plain(session)}\n---\n"
            f"# {title}\n## Question\n{question.strip()}\n## Answer\n{answer.strip()}\n")


def popup_question(question: str, answer: str) -> str:
    """The popup's text: the REDACTED note, so you approve exactly what will be stored."""
    def short(text: str) -> str:
        return text if len(text) <= POPUP_PREVIEW_CHARS else text[:POPUP_PREVIEW_CHARS] + "…"
    return ("Save this task to Pseudo's memory?\n\n"
            f"Question:  {short(question)}\n\nAnswer:  {short(answer)}\n\n"
            "It is stored redacted, on this laptop only, and may be sent to the model with later questions.\n"
            f"Click OK to save. Cancel, Esc, the X, or no answer within {approval.TIMEOUT_SECONDS:.0f} seconds means NO.")


def new_note(folder: Path, text: str) -> str:
    """Write a NEW note named after the time; never overwrite one. Returns its file name."""
    now = time.time()
    stamp = time.strftime("%Y-%m-%d-%H%M%S", time.localtime(now))
    for extra in range(1000):
        name = f"{stamp}-{(int(now * 1000) + extra) % 1000:03d}.md"
        try:
            with open(folder / name, "x", encoding="utf-8", newline="\n") as file:  # "x": fails if it exists
                file.write(text)
            return name
        except FileExistsError:
            continue
    raise VaultRefused("no free note name")


def save_memory(question: str, answer: str, tools: list[str], provider: str, model: str, session: str) -> SaveResult:
    """Redact the task, ask you in the popup, and write it to the vault only if you say yes."""
    if not isinstance(question, str) or not isinstance(answer, str) or not question.strip() or not answer.strip():
        return {"status": NOT_SAVED, "note": "", "reason": "there is no question and answer to save"}
    try:
        question = redact(question[:MAX_QUESTION_CHARS])
        answer = redact(answer)  # the whole answer first, THEN cut (never half a secret)
    except RedactionError:
        return {"status": NOT_SAVED, "note": "", "reason": "redaction failed, so nothing was saved"}
    answer = answer if len(answer) <= MAX_ANSWER_CHARS else answer[:MAX_ANSWER_CHARS] + " … (cut)"
    if not approval.ask(popup_question(question, answer)):  # THE GATE: you decide
        return {"status": NOT_APPROVED, "note": "", "reason": "you didn't approve it, so nothing was saved"}
    try:
        name = new_note(tasks_folder(create=True), note_text(question, answer, list(tools or []), provider, model, session))
    except (OSError, VaultRefused) as error:
        return {"status": NOT_SAVED, "note": "", "reason": f"the vault refused the note ({error.__class__.__name__})"}
    return {"status": SAVED, "note": name, "reason": ""}
