"""M9: walk ONE window's UI Automation tree and return raw lines. The only file that touches UIA.

What it demonstrates: Windows keeps an accessibility tree for every window, the
desktop's DOM. Each node ("control") has a type (Button, Edit, Document...), a
Name (like aria-label), and sometimes text you can read through a "pattern"
(ValuePattern is like input.value). Screen readers use this tree; so do we.

No privacy logic here on purpose: active_window.py decides whether this may run
at all (blocked apps never get here) and redacts whatever comes back.

Budget, so a huge browser tree can't stall a call or blow the token limit:
depth 30, 400 controls, 8,000 characters, 2 seconds. Hitting any sets truncated.
(M28) M9 stopped at depth 12, 200 controls and 4,000 characters. M27 found VS Code's
controls at depth 22-28, and a browser's own tabs and toolbar before the page, which
the walk must still reach. What the model gets is still cut to 1,200 characters.

(M12) A control that fails to answer is skipped, with everything inside it, and
counted; the rest of the tree is still read. M11 found one vanished control made
claude.exe's whole read fail, every time.

(M28) Each line also notes where its control's centre is on screen, and the walk
notes every Document's rectangle, so outline.py can put a browser's page first.
"""

import re
import time
from dataclasses import dataclass, field

import uiautomation as auto
from comtypes import COMError  # how UI Automation says "I can't answer" (e.g. the element is gone)

MAX_DEPTH = 30
MAX_CONTROLS = 400
MAX_RAW_CHARS = 8000
TIME_BUDGET_SECONDS = 2.0
NAME_CHARS = 200  # per control name
TEXT_CHARS = 600  # per Edit/Document text
TEXT_TYPES = {"Edit", "Document"}  # controls whose text (not just name) we read
NUMBER_TAIL = re.compile(r"[\d\s+\-().,/]*$")  # digits and separators at the end of a cut

Box = tuple[int, int, int, int]  # (M28) a rectangle on screen: left, top, right, bottom


@dataclass
class TreeLine:
    depth: int  # 0 = the window itself
    kind: str  # "Button", "Document", ... (UIA's ControlTypeName without "Control")
    text: str
    center: tuple[int, int] | None = None  # (M28) where the control's centre is on screen; None = no size


@dataclass
class TreeRead:
    lines: list[TreeLine]
    truncated: bool
    controls_read: int
    skipped: int = 0  # (M12) controls skipped because UI Automation failed to answer
    documents: list[Box] = field(default_factory=list)  # (M28) every Document's rectangle below the window


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


def box_of(control: auto.Control) -> Box | None:
    """(M28) The control's rectangle on screen, or None if it has no size."""
    rect = control.BoundingRectangle
    if rect.width() <= 0 or rect.height() <= 0:
        return None
    return rect.left, rect.top, rect.right, rect.bottom


def middle(box: Box | None) -> tuple[int, int] | None:
    return None if box is None else ((box[0] + box[2]) // 2, (box[1] + box[3]) // 2)


def read_tree(handle: int) -> TreeRead:
    """Depth-first walk (screen reading order) from the window with this handle."""
    with auto.UIAutomationInitializerInThread():  # COM must be set up in every thread that uses it
        root = auto.ControlFromHandle(handle)  # if even this fails, there is no tree: it raises
        if root is None:
            return TreeRead([], False, 0)
        return walk(root)


def walk(root: auto.Control) -> TreeRead:
    """(M12) The walk itself. Takes any control-like object, so tests can pass fake trees."""
    started, lines, count, chars, truncated, skipped = time.monotonic(), [], 0, 0, False, 0
    documents: list[Box] = []
    stack = [(root, 0)]
    while stack:
        if count >= MAX_CONTROLS or chars >= MAX_RAW_CHARS or time.monotonic() - started > TIME_BUDGET_SECONDS:
            truncated = True
            break
        control, depth = stack.pop()
        count += 1
        try:  # every question we ask this one control, together
            if depth > 0 and control.IsOffscreen:  # not visible: skip it and everything inside it
                continue
            kind = control.ControlTypeName.removesuffix("Control")
            text = control_line(control, kind)  # a password box whose IsPassword fails stops HERE, unread
            box = box_of(control) if text or kind == "Document" else None  # (M28) only when it's used
            children = control.GetChildren() if depth < MAX_DEPTH else []
            deeper = depth >= MAX_DEPTH and control.GetFirstChildControl() is not None
        except COMError:  # it vanished or won't answer: skip it and everything inside it, like off-screen
            skipped += 1
            continue  # nothing half-read is kept: its line is only added below, after every call worked
        if text:
            lines.append(TreeLine(depth, kind, text, middle(box)))
            chars += len(text)
        if kind == "Document" and depth > 0 and box is not None:
            documents.append(box)
        if deeper:
            truncated = True  # deeper controls exist but are beyond the depth limit
        stack.extend((child, depth + 1) for child in reversed(children))
    return TreeRead(lines, truncated, count, skipped, documents)
