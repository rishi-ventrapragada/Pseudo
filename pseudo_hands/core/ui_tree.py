"""M9: walk ONE window's UI Automation tree and return raw lines. The only file that touches UIA.

What it demonstrates: Windows keeps an accessibility tree for every window, the
desktop's DOM. Each node ("control") has a type (Button, Edit, Document...), a
Name (like aria-label), and sometimes text you can read through a "pattern"
(ValuePattern is like input.value). Screen readers use this tree; so do we.

No privacy logic here on purpose: active_window.py decides whether this may run
at all (blocked apps never get here) and redacts whatever comes back.

Budget, so a huge browser tree can't stall a call or blow the token limit:
depth 12, 200 controls, 4,000 characters, 2 seconds. Hitting any sets truncated.
"""

import re
import time
from dataclasses import dataclass

import uiautomation as auto

MAX_DEPTH = 12
MAX_CONTROLS = 200
MAX_RAW_CHARS = 4000
TIME_BUDGET_SECONDS = 2.0
NAME_CHARS = 200  # per control name
TEXT_CHARS = 600  # per Edit/Document text
TEXT_TYPES = {"Edit", "Document"}  # controls whose text (not just name) we read
NUMBER_TAIL = re.compile(r"[\d\s+\-().,/]*$")  # digits and separators at the end of a cut


@dataclass
class TreeLine:
    depth: int  # 0 = the window itself
    kind: str  # "Button", "Document", ... (UIA's ControlTypeName without "Control")
    text: str


@dataclass
class TreeRead:
    lines: list[TreeLine]
    truncated: bool
    controls_read: int


def clean(text: str, limit: int) -> str:
    """Collapse whitespace; if too long, cut at a space and never leave half a number behind."""
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return NUMBER_TAIL.sub("", cut).rstrip() + " …"


def read_text(control: auto.Control) -> str:
    """An Edit/Document's content: its value if it has one, else its document text."""
    value = control.GetPattern(auto.PatternId.ValuePattern)
    if value is not None and value.Value:
        return value.Value
    text = control.GetPattern(auto.PatternId.TextPattern)
    return text.DocumentRange.GetText(TEXT_CHARS * 2) if text is not None else ""


def control_line(control: auto.Control, kind: str) -> str:
    """What one control contributes: its name, plus its text for Edit/Document controls."""
    name = clean(control.Name, NAME_CHARS)
    if kind not in TEXT_TYPES:
        return name
    if control.IsPassword:  # never read what's typed in a password box
        return f"{name} = [password field]".strip(" =")
    content = clean(read_text(control), TEXT_CHARS)
    return f"{name} = {content}" if name and content and content != name else (content or name)


def read_tree(handle: int) -> TreeRead:
    """Depth-first walk (screen reading order) from the window with this handle."""
    with auto.UIAutomationInitializerInThread():  # COM must be set up in every thread that uses it
        root = auto.ControlFromHandle(handle)
        if root is None:
            return TreeRead([], False, 0)
        started, lines, count, chars, truncated = time.monotonic(), [], 0, 0, False
        stack = [(root, 0)]
        while stack:
            if count >= MAX_CONTROLS or chars >= MAX_RAW_CHARS or time.monotonic() - started > TIME_BUDGET_SECONDS:
                truncated = True
                break
            control, depth = stack.pop()
            count += 1
            if depth > 0 and control.IsOffscreen:  # not visible: skip it and everything inside it
                continue
            kind = control.ControlTypeName.removesuffix("Control")
            text = control_line(control, kind)
            if text:
                lines.append(TreeLine(depth, kind, text))
                chars += len(text)
            if depth < MAX_DEPTH:
                stack.extend((child, depth + 1) for child in reversed(control.GetChildren()))
            elif control.GetFirstChildControl() is not None:
                truncated = True  # deeper controls exist but are beyond the depth limit
        return TreeRead(lines, truncated, count)
