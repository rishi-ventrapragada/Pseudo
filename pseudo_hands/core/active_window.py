"""M9: read_active_window(): the front-most window's contents as a small, redacted outline.

What it demonstrates: reading is only safe because every privacy rule runs HERE,
in core, before anything is returned (D6, D11):
  1. The assistant's own window is skipped, so Hermes never reads its own chat.
  2. Blocked (or unknown) apps return nothing, and their tree is never even walked.
  3. The outline is redacted as a whole, THEN cut to size, so a cut can't expose
     half of a secret. Redaction failure -> "[content withheld]", never raw text.
  4. The result is capped at 1,200 characters (~300-400 tokens) to fit Groq's
     8K tokens/min free tier, cut at a line boundary.
  5. (M12) A read that fails or finds nothing inside the window is tried once more
     after a short wait: Chromium/Electron apps build their tree only when first
     asked, so the first read can fail (M11 saw it in Brave, VS Code, Obsidian).
"""

import time
from typing import TypedDict

from pseudo_hands.core.blocked_apps import RESTRICTED, is_blocked, load_blocked_apps
from pseudo_hands.core.redactor import RedactionError, redact
from pseudo_hands.core.ui_tree import TreeLine, TreeRead, read_tree
from pseudo_hands.core.windows import RawWindow, is_user_window, read_all_windows, safe_title

ASSISTANT_APPS = {"hermes.exe"}  # the brain's own window: reading it would read the chat itself
MAX_CONTENT_CHARS = 1200
RETRY_WAIT_SECONDS = 1.0  # (M12) time for a lazy app to build its tree before the second try
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
    """The front-most window a person can see that isn't the assistant itself."""
    for raw in read_all_windows():  # z-order: front-most first
        if is_user_window(raw) and (raw.app or "").lower() not in ASSISTANT_APPS:
            return raw
    return None


def outline(lines: list[TreeLine]) -> str:
    return "\n".join(f"{'  ' * line.depth}{line.kind}: {line.text}" for line in lines)


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


def read_with_retry(handle: int) -> tuple[TreeRead | None, str, bool]:
    """(M12) Read; if that failed or found nothing inside the window, wait and read once more.
    Returns (tree or None, error type or "", whether it retried)."""
    tree, error = attempt(handle)
    if tree is not None and any(line.depth > 0 for line in tree.lines):
        return tree, error, False
    time.sleep(RETRY_WAIT_SECONDS)
    tree, error = attempt(handle)
    return tree, error, True


def success_note(retried: bool, skipped: int) -> str:
    """(M12) "" for a clean read; otherwise what happened, with numbers only."""
    parts = ["read on the second try"] if retried else []
    if skipped:
        parts.append(f"{skipped} control{'' if skipped == 1 else 's'} skipped (read errors)")
    return "; ".join(parts)


def read_window(raw: RawWindow, blocked: set[str]) -> WindowContent:
    """Read one window, with every privacy rule applied."""
    if is_blocked(raw.app, blocked):  # checked BEFORE touching the tree: nothing is read at all
        return result(RESTRICTED, RESTRICTED, note="blocked app: nothing read")
    title, app = safe_title(raw.title), raw.app
    tree, error, retried = read_with_retry(raw.handle)  # only windows that passed the check get here
    if tree is None:
        return result(title, app, note=f"read failed ({error})")
    if not tree.lines:
        return result(title, app, truncated=tree.truncated, controls_read=tree.controls_read,
                      note="no readable controls")
    try:
        redacted = redact(outline(tree.lines))  # whole outline first, THEN cut (never half a secret)
    except RedactionError:
        return result(title, app, CONTENT_WITHHELD, tree.truncated, tree.controls_read,
                      note="redaction failed: content withheld")
    content, was_cut = cap(redacted, MAX_CONTENT_CHARS)
    return result(title, app, content, tree.truncated or was_cut, tree.controls_read,
                  success_note(retried, tree.skipped))


def read_active_window() -> WindowContent:
    """Read-only. Raises BlockedAppsError if the blocked-apps list is missing (as in M4)."""
    blocked = load_blocked_apps()
    raw = pick_window()
    if raw is None:
        return result("", "", note="no active window")
    return read_window(raw, blocked)
