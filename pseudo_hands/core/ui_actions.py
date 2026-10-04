"""M28: the ACTING side of UI Automation (ui_tree.py is the reading side). Plain Python, no MCP.

What it demonstrates: a control says what it can do through its "patterns", interfaces it
offers on top of its name and type (D25). It's like the DOM: a <button> has .click(), an
<input> has .value, a checkbox has .checked. Pseudo acts only through these, never with the
mouse or keyboard (M27: they added nothing and can hit the wrong window).
  InvokePattern          press (a button, a link)
  ValuePattern           set_text / insert_text (only if it isn't read-only)
  TogglePattern          toggle (a checkbox)
  SelectionItemPattern   select (a radio button, a list or tree item); open selects it too
  ExpandCollapsePattern  choose (open a dropdown, pick an item by its own name)
  LegacyIAccessible      the older accessibility interface: its "default action" presses
                         controls that offer nothing else (M27: Obsidian's buttons are Groups)
No privacy logic here: act.py decides whether an action may happen at all.

perform() acts and then READS THE EFFECT BACK, so Pseudo reports what really happened,
not what it hoped: the box is ticked, the field holds exactly the text, the item is selected.
A press has no generic effect to read, so it's reported as "pressed".
"""

import time

import uiautomation as auto
from comtypes import COMError

P = auto.PatternId
WAIT = 0  # uiautomation waits 0.5 s after every pattern call by default; Pseudo doesn't need to (M27 v1: 510 ms)
CHOOSE_WAIT_SECONDS = 0.3  # a dropdown fills its list a moment after it opens (M27 prototype)
DONE = "done"
DIFFERS = "done, but the read-back differs: check the window"
PRESSED = "pressed"
NO_ITEM = "no item with that name"
UNAVAILABLE = "action not available"
# Controls that only hold other controls never get an id, even if they offer a pattern (M27 v2).
CONTAINERS = {"Window", "Pane", "Document", "ToolBar", "List", "Tree", "Table", "MenuBar", "Menu", "TitleBar",
              "ScrollBar", "Thumb", "Separator", "Header", "StatusBar", "Tab", "AppBar"}
NAME_SEARCH_DEPTH = 3  # an unnamed control is named by the first text this deep inside it


def actions_of(control: auto.Control, kind: str) -> frozenset[str]:
    """What this control can do, from the patterns it offers. Empty = it gets no id.
    Only asks whether a pattern exists (and IsReadOnly): never reads a value."""
    if kind in CONTAINERS:
        return frozenset()
    found: set[str] = set()
    legacy = control.GetPattern(P.LegacyIAccessiblePattern)
    if control.GetPattern(P.InvokePattern) is not None or (legacy is not None and legacy.DefaultAction):
        found |= {"press", "open"}
    value = control.GetPattern(P.ValuePattern)
    if value is not None and not value.IsReadOnly:
        found |= {"set_text", "insert_text"}
    if control.GetPattern(P.TogglePattern) is not None:
        found.add("toggle")
    if control.GetPattern(P.SelectionItemPattern) is not None:
        found |= {"select", "open"}
    if control.GetPattern(P.ExpandCollapsePattern) is not None:
        found.add("choose")
    return frozenset(found)


def name_of(control: auto.Control) -> str:
    """The control's Name, or, if it has none, the first named Text inside it (M27 v2: Obsidian's
    buttons are unnamed Groups with a Text inside). "" if there is none."""
    if control.Name:
        return control.Name
    stack = [(child, 1) for child in reversed(control.GetChildren())]
    while stack:
        child, depth = stack.pop()
        if child.ControlTypeName == "TextControl" and child.Name:
            return child.Name
        if depth < NAME_SEARCH_DEPTH:
            stack.extend((inner, depth + 1) for inner in reversed(child.GetChildren()))
    return ""


# ---------- acting (act.py calls this only after every check and an approved popup) ----------

def perform(control: auto.Control, action: str, text: str = "") -> str:
    """Do one action through its pattern, then read the effect back. Returns a status above."""
    if action == "press" or (action == "open" and presses(control)):
        return press(control)
    if action in ("select", "open"):
        return select(control)
    if action == "toggle":
        return toggle(control)
    if action in ("set_text", "insert_text"):
        return type_text(control, action, text)
    if action == "choose":
        return choose(control, text)
    return UNAVAILABLE


def presses(control: auto.Control) -> bool:
    legacy = control.GetPattern(P.LegacyIAccessiblePattern)
    return control.GetPattern(P.InvokePattern) is not None or (legacy is not None and bool(legacy.DefaultAction))


def press(control: auto.Control) -> str:
    invoke = control.GetPattern(P.InvokePattern)
    if invoke is not None:
        invoke.Invoke(waitTime=WAIT)
        return PRESSED
    legacy = control.GetPattern(P.LegacyIAccessiblePattern)
    if legacy is not None and legacy.DefaultAction:
        legacy.DoDefaultAction(waitTime=WAIT)  # (M27 v2) e.g. Obsidian's buttons, VS Code's view tabs
        return PRESSED
    return UNAVAILABLE


def select(control: auto.Control) -> str:
    item = control.GetPattern(P.SelectionItemPattern)
    if item is None:
        return UNAVAILABLE
    item.Select(waitTime=WAIT)
    return DONE if item.IsSelected else DIFFERS


def toggle(control: auto.Control) -> str:
    box = control.GetPattern(P.TogglePattern)
    if box is None:
        return UNAVAILABLE
    before = box.ToggleState
    box.Toggle(waitTime=WAIT)
    return DONE if box.ToggleState != before else DIFFERS


def type_text(control: auto.Control, action: str, text: str) -> str:
    """set_text replaces the whole value; insert_text adds the text at its end."""
    value = control.GetPattern(P.ValuePattern)
    if value is None or value.IsReadOnly:
        return UNAVAILABLE
    wanted = text if action == "set_text" else (value.Value or "") + text
    value.SetValue(wanted, waitTime=WAIT)
    return DONE if value.Value == wanted else DIFFERS


def choose(combo: auto.Control, wanted: str) -> str:
    """Open the dropdown, select the item whose OWN name is exactly `wanted`, close it again.
    Never a partial match: the popup promised exactly that name."""
    expand = combo.GetPattern(P.ExpandCollapsePattern)
    if expand is None:
        return UNAVAILABLE
    expand.Expand(waitTime=WAIT)
    time.sleep(CHOOSE_WAIT_SECONDS)
    item = find_item(combo, wanted)
    picked = item.GetPattern(P.SelectionItemPattern) if item is not None else None
    if picked is not None:
        picked.Select(waitTime=WAIT)
    try:
        expand.Collapse(waitTime=WAIT)
    except COMError:
        pass  # selecting an item often closes the dropdown by itself
    if picked is None:
        return NO_ITEM
    value = combo.GetPattern(P.ValuePattern)
    shown = value.Value if value is not None else None
    return DONE if shown == wanted or (shown is None and picked.IsSelected) else DIFFERS


def find_item(combo: auto.Control, wanted: str) -> auto.Control | None:
    """The ListItem inside the dropdown (up to 3 levels down) named exactly `wanted`."""
    stack = [(child, 1) for child in reversed(combo.GetChildren())]
    while stack:
        item, depth = stack.pop()
        if item.ControlTypeName == "ListItemControl" and (item.Name or "") == wanted:
            return item
        if depth < 3:
            stack.extend((inner, depth + 1) for inner in reversed(item.GetChildren()))
    return None
