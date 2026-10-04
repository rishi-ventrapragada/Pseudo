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
"""

import uiautomation as auto

P = auto.PatternId
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
