"""M28: the outline the model sees, built from the walk's lines (ui_tree.py).

What it demonstrates: the ORDER of a read matters, because read_active_window cuts every
outline at 1,200 characters (Groq's free tier). In a browser the walk meets the browser's
own tabs, address bar and toolbar BEFORE the page (M27, Brave), so the cut could keep the
browser and drop the page you asked about. So the page area goes first:
  - the window's own line stays first;
  - then every line whose control's centre lies inside the biggest Document (in a browser
    the web page; in VS Code or Obsidian, nearly the whole window);
  - then everything else, in walk order (tabs, toolbars, title bar): what the cut drops first.
No list of browsers is needed: any window with a Document gets the same rule. It's like
putting <main> before <nav> when you can only send the first part of a page.
"""

from pseudo_hands.core.ui_tree import Box, TreeLine


def area(box: Box) -> int:
    left, top, right, bottom = box
    return (right - left) * (bottom - top)


def inside(line: TreeLine, box: Box) -> bool:
    if line.center is None:  # a control with no size isn't anywhere on screen
        return False
    x, y = line.center
    left, top, right, bottom = box
    return left <= x <= right and top <= y <= bottom


def page_first(lines: list[TreeLine], documents: list[Box]) -> list[TreeLine]:
    """The window's own line, then the lines inside the biggest Document, then the rest.
    With no Document, the lines come back in walk order, unchanged."""
    if not documents:
        return lines
    page = max(documents, key=area)
    head = lines[:1] if lines and lines[0].depth == 0 else []
    rest = lines[len(head):]
    return head + [line for line in rest if inside(line, page)] + [line for line in rest if not inside(line, page)]


def outline(lines: list[TreeLine]) -> str:
    """One control per line as 'Kind: text', indented 2 spaces per level of nesting (M9)."""
    return "\n".join(f"{'  ' * line.depth}{line.kind}: {line.text}" for line in lines)
