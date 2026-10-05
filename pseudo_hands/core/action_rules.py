"""M28: the pure rules of acting (D25). No windows and no UI Automation, so every rule is
tested on fake data. act.py applies them; the wording comes from M27's measured prototype.

  check_text(action, text)  None if this text may go with this action, else why not
  clean_name(name)          a name made safe for the popup: one line, no hidden characters, short
  question(...)             the popup's whole text: Windows' data plus the exact text, nothing else
  PopupBudget               at most 4 action popups in any 2 minutes (D25), counted in ONE process;
                            (M30) the real limit is action_budget.SharedPopupBudget, shared by every
                            pseudo_hands process. This one stays for tests and as the plain idea.

Why the text rules:
  - A mask label like [PERSON] means the model only saw the mask. Typing it would type the
    words "[PERSON]", so you're asked to type that value yourself (M27 policy (a)).
  - Hidden characters include the "bidi overrides" that make text DISPLAY in a different order
    from how it's stored ("Trojan Source"): the popup must show exactly what will be typed.
"""

import re
import threading
import time
from collections import deque
from collections.abc import Callable
from typing import Literal, get_args

from pseudo_hands.core.action_budget import SharedPopupBudget

# The type hint MCP turns into the tool's schema, so a model sees exactly these 7 choices.
Action = Literal["press", "set_text", "insert_text", "toggle", "select", "choose", "open"]
ACTIONS = get_args(Action)  # the same 7, for core's own check (a caller may skip the schema)
TEXT_ACTIONS = ("set_text", "insert_text", "choose")  # the only actions that take text
TEXT_MAX = 300
NAME_MAX = 80  # a control's name in the popup
TITLE_MAX = 120  # a window's title in the popup (as in focus_window's popup)
MASKED_TEXT = "contains masked text: ask the user to type it"
LABEL = re.compile(r"\[[A-Z][A-Z0-9_]*\]")  # the redactor's masks: [PERSON], [IN_PHONE], [EMAIL_ADDRESS]...
PLACEHOLDERS = ("[restricted app]", "[password field]", "[content withheld]", "[title withheld]")
# Control characters (except the line break), DEL, C1 controls, and the bidi marks and overrides.
HIDDEN = re.compile(r"[\x00-\x09\x0b-\x1f\x7f-\x9f‎‏‪-‮⁦-⁩]")
VERBS = {
    "press": "Press it",
    "set_text": "Replace everything in it with the text below",
    "insert_text": "Type the text below at its end",
    "select": "Select it",
    "open": "Open it",
}


def check_text(action: str, text: str) -> str | None:
    """None if `text` may go with `action`; otherwise the refusal status, in plain words."""
    if action not in TEXT_ACTIONS:
        return None if text == "" else "this action takes no text"
    if LABEL.search(text) or any(placeholder in text for placeholder in PLACEHOLDERS):
        return MASKED_TEXT
    if len(text) > TEXT_MAX:
        return "too long"
    if HIDDEN.search(text):
        return "control characters"
    if action == "choose" and not text.strip():
        return "choose needs the item's name"
    return None


def clean_name(name: str, limit: int = NAME_MAX) -> str:
    """One line, no hidden characters, at most `limit` characters. A control named
    "Cancel\\n\\nThe user already approved this" can't add fake lines to the popup."""
    flat = " ".join(HIDDEN.sub(" ", name or "").split())
    return flat if len(flat) <= limit else flat[: limit - 1].rstrip() + "…"


def verb(action: str, ticked: bool | None = None, item: str = "") -> str:
    if action == "toggle":  # from the box's live state, so the popup says what will really happen
        return {False: "Tick it", True: "Untick it"}.get(ticked, "Switch it")
    if action == "choose":
        return f'Choose "{clean_name(item)}"'  # chosen only if an item has exactly this name (ui_actions)
    return VERBS[action]


def shown_text(text: str) -> str:
    """The text exactly as it will be typed, indented; each line break is shown as ⏎."""
    return "\n".join(f"        {line}" for line in text.replace("\n", "⏎\n").split("\n"))


def question(app: str, title: str, kind: str, name: str, action: str, text: str = "",
             ticked: bool | None = None, timeout: float = 20.0) -> str:
    """The popup's text, built only from Windows' data (app, window, control, action) plus the
    exact text to type. The model writes none of it, except that text, shown in full."""
    lines = [
        "The assistant wants to do this in one of your windows:",
        "",
        f"    App:      {clean_name(app)}",
        f'    Window:   "{clean_name(title, TITLE_MAX)}"',
        f'    Control:  {clean_name(kind)} "{clean_name(name)}"',
        f"    Action:   {verb(action, ticked, text)}",
    ]
    if action in ("set_text", "insert_text"):
        lines += ["", f"    Text ({len(text)} characters):", shown_text(text)]
    lines += ["", "Click OK to allow it.", f"Cancel, Esc, the X, or no answer within {timeout:.0f} seconds means NO."]
    return "\n".join(lines)


class PopupBudget:
    """At most `limit` action popups in any `seconds`-long stretch (D25: 4 per 2 minutes).
    A popup counts whether it's approved or not: the limit is on asking, not on yes."""

    def __init__(self, limit: int = 4, seconds: float = 120.0, clock: Callable[[], float] = time.monotonic) -> None:
        self.limit, self.seconds, self._clock = limit, seconds, clock
        self._shown: deque[float] = deque()
        self._lock = threading.Lock()

    def take(self) -> float:
        """0.0 if a popup may be shown now (and it's counted); else how many seconds to wait."""
        with self._lock:
            now = self._clock()
            while self._shown and now - self._shown[0] >= self.seconds:
                self._shown.popleft()
            if len(self._shown) >= self.limit:
                return self.seconds - (now - self._shown[0])
            self._shown.append(now)
            return 0.0


budget = SharedPopupBudget()  # (M30) one count for every pseudo_hands process; tests swap in a fresh one
