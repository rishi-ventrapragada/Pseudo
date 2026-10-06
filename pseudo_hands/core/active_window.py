"""M9: read_active_window(): the front-most window's contents as a small, redacted outline.

What it demonstrates: reading is only safe because every privacy rule runs HERE,
in core, before anything is returned (D6, D11):
  1. Assistant apps are skipped (M18: the owner's list in assistant_apps.txt), so a
     question asked from Pseudo's face reads the window you were on before switching,
     never the chat itself. Windows keeps windows in the order they were last active,
     so skipping the face leads to that window. If the list can't be read, nothing is.
  2. Blocked (or unknown) apps return nothing, and their tree is never even walked.
  3. The outline is redacted as a whole, THEN cut to size, so a cut can't expose
     half of a secret. Redaction failure -> "[content withheld]", never raw text.
  4. The result is capped at 1,200 characters (~300-400 tokens) to fit Groq's
     8K tokens/min free tier, cut at a line boundary.
  5. (M28, replacing M12's single retry) The window is read again until two reads in
     a row find the same number of lines: Chromium/Electron apps build their tree only
     when first asked, so a first read can be thin (M27: VS Code 4 controls, then 59).
  6. (M28) Pseudo's own windows, such as the approval popup, are never read (D14).
  7. (M28) A browser's page area goes first, so the 1,200-character cut drops the
     browser's own controls before the page (outline.py).
  8. (M28) Controls that can act get ids ("Button #c12: Save") for act_on_control. Only
     the ids still in the content after the cut work (control_ids.py).
"""

import os
import time
from typing import TypedDict

from pseudo_hands.core import control_ids
from pseudo_hands.core.assistant_apps import AssistantAppsError, is_assistant, load_assistant_apps
from pseudo_hands.core.blocked_apps import RESTRICTED, is_blocked, load_blocked_apps
from pseudo_hands.core.control_ids import ControlKey, shown_ids
from pseudo_hands.core.outline import outline, page_first
from pseudo_hands.core.redactor import RedactionError, redact
from pseudo_hands.core.ui_tree import TreeLine, TreeRead, read_tree
from pseudo_hands.core.windows import RawWindow, is_user_window, read_all_windows, safe_title

ASSISTANT_LIST_UNREADABLE = "assistant-apps list can't be read: nothing read"
MAX_CONTENT_CHARS = 1200
SETTLE_WAIT_SECONDS = 1.0  # (M28) between reads; the M27 stand-in used 1.0 s on fresh Brave pages
MAX_READS = 4  # (M28) a window that keeps changing (a clock, a feed) is read at most this often
STILL_CHANGING = f"still changing after {MAX_READS} reads"
CONTENT_WITHHELD = "[content withheld]"
TRUNCATED_MARK = "… (truncated)"


class WindowContent(TypedDict):
    """One window's contents, as a model will see it."""

    title: str
    app: str
    content: str  # redacted outline: one control per line, indented 2 spaces per level
    truncated: bool
    controls_read: int
    note: str  # "" or a short reason, never an error message (those could contain text)


def pick_window() -> RawWindow | None:
    """The front-most window a person can see that isn't an assistant app or one of Pseudo's own
    windows, such as the approval popup (M28, D14). Raises AssistantAppsError."""
    assistants = load_assistant_apps()  # (P8-fix) the list now lives in assistant_apps.py
    for raw in read_all_windows():  # z-order: front-most first
        if is_user_window(raw) and not is_assistant(raw.app, assistants) and raw.process_id != os.getpid():
            return raw
    return None


def cap(text: str, limit: int) -> tuple[str, bool]:
    """Keep whole lines up to `limit` characters. Returns (text, was_cut)."""
    if len(text) <= limit:
        return text, False
    kept = text[:limit].rsplit("\n", 1)[0] if "\n" in text[:limit] else ""
    return f"{kept}\n{TRUNCATED_MARK}".lstrip("\n"), True


def result(title: str, app: str, content: str = "", truncated: bool = False,
           controls_read: int = 0, note: str = "") -> WindowContent:
    return {"title": title, "app": app, "content": content, "truncated": truncated,
            "controls_read": controls_read, "note": note}


def attempt(handle: int) -> tuple[TreeRead | None, str]:
    """One read: (tree, "") or (None, the error's TYPE). Never its message: that could contain text."""
    try:
        return read_tree(handle), ""
    except Exception as error:  # noqa: BLE001 - UIA/COM can fail many ways; report only the type
        return None, type(error).__name__


def inside_count(tree: TreeRead | None) -> int:
    """How many lines a read found inside the window (the window's own line doesn't count)."""
    return 0 if tree is None else sum(line.depth > 0 for line in tree.lines)


def read_until_settled(handle: int) -> tuple[TreeRead | None, str, str]:
    """(M28) Read until two reads in a row find the same number of lines inside the window, and
    some; at most MAX_READS times. A failed read counts as 0 lines.
    Returns (the last good read or None, the last error's type or "", "" or STILL_CHANGING)."""
    good, error, counts = None, "", []
    for number in range(MAX_READS):
        if number:
            time.sleep(SETTLE_WAIT_SECONDS)
        tree, error = attempt(handle)
        good = tree if tree is not None else good
        counts.append(inside_count(tree))
        if number and counts[-1] == counts[-2] > 0:
            return good, error, ""
    return good, error, STILL_CHANGING if counts[-1] > 0 else ""


def success_note(settle_note: str, skipped: int) -> str:
    """"" for a clean read; otherwise what happened, with numbers only (M12, M28)."""
    parts = [settle_note] if settle_note else []
    if skipped:
        parts.append(f"{skipped} control{'' if skipped == 1 else 's'} skipped (read errors)")
    return "; ".join(parts)


def read_window(raw: RawWindow, blocked: set[str]) -> WindowContent:
    """Read one window, with every privacy rule applied."""
    if is_blocked(raw.app, blocked):  # checked BEFORE touching the tree: nothing is read at all
        return result(RESTRICTED, RESTRICTED, note="blocked app: nothing read")
    title, app = safe_title(raw.title), raw.app
    tree, error, settle_note = read_until_settled(raw.handle)  # only windows that passed the check get here
    if tree is None:
        return result(title, app, note=f"read failed ({error})")
    if not tree.lines:
        return result(title, app, truncated=tree.truncated, controls_read=tree.controls_read,
                      note="no readable controls")
    lines = page_first(tree.lines, tree.documents)  # (M28) the page area first
    ids = {n: control_ids.registry.new_id() for n, line in enumerate(lines) if line.actions}
    try:  # whole outline first, THEN cut (never half a secret)
        redacted = redact(outline(lines, ids))
    except RedactionError:
        return result(title, app, CONTENT_WITHHELD, tree.truncated, tree.controls_read,
                      note="redaction failed: content withheld")
    content, was_cut = cap(redacted, MAX_CONTENT_CHARS)
    keep_shown_ids(raw, lines, ids, content)
    return result(title, app, content, tree.truncated or was_cut, tree.controls_read,
                  success_note(settle_note, tree.skipped))


def keep_shown_ids(raw: RawWindow, lines: list[TreeLine], ids: dict[int, str], content: str) -> None:
    """(M28) Only the ids the model will actually see work: ids cut off by the cap never do."""
    shown = shown_ids(content)
    control_ids.registry.replace({
        cid: ControlKey(raw.handle, raw.process_id, lines[n].runtime_id, lines[n].kind, lines[n].name)
        for n, cid in ids.items() if cid in shown})


def read_active_window() -> WindowContent:
    """Read-only. Raises BlockedAppsError if the blocked-apps list is missing (as in M4).
    (M28) Every call first retires the last read's control ids; only a successful read hands out new ones."""
    control_ids.registry.replace({})
    blocked = load_blocked_apps()
    try:
        raw = pick_window()
    except AssistantAppsError:  # (M18) fail closed: the front window might be the face itself
        return result("", "", note=ASSISTANT_LIST_UNREADABLE)
    if raw is None:
        return result("", "", note="no active window")
    return read_window(raw, blocked)
