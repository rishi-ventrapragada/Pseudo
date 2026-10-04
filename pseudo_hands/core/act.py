"""M28: act_on_control(): Pseudo clicks and types, through UI Automation only (D25).

What it demonstrates: like focus_window (M10), an action tool is mostly checks. The few lines
that act run last, after everything below has passed, all in core (D11, D13, D14), so the
rules hold for any brain:
  0. the blocked-apps and assistant-apps lists must load, or nothing happens (fail closed)
  1. a known action, and text that may go with it (no mask labels like [PERSON], <= 300
     characters, no hidden characters)
  2. an id the LATEST read handed out (control_ids.py)
  3. its window still exists, isn't Pseudo's own (D14), a blocked app or an assistant app,
     and is the window you were on (the one read_active_window would read now)
  4. the control itself, found again by its runtime id: same type and name, not a password
     field, enabled, and still offering that action
  5. at most 4 action popups in any 2 minutes (action_rules.PopupBudget)
  6. THE GATE: the popup, built from Windows' data plus the exact text; a person must say yes
  7. check again: in 20 s the window or control could have changed (or the box been ticked)
  8. act through the pattern, then read the effect back (ui_actions.perform)
The model only ever gets back the id, the action and a status in plain words.
"""

import math
import os
from typing import TypedDict

import uiautomation as auto
import win32gui
from comtypes import COMError

from pseudo_hands.core import action_rules, approval, control_ids
from pseudo_hands.core.action_rules import ACTIONS, check_text, question
from pseudo_hands.core.active_window import AssistantAppsError, load_assistant_apps, pick_window
from pseudo_hands.core.blocked_apps import is_blocked, load_blocked_apps
from pseudo_hands.core.control_ids import ControlKey
from pseudo_hands.core.ui_actions import P, actions_of, name_of, perform
from pseudo_hands.core.ui_tree import find_control
from pseudo_hands.core.windows import RawWindow, read_window

# What act_on_control() reports back, as plain words a model can act on.
UNKNOWN_ACTION = "unknown action"
UNKNOWN_ID = "unknown id"
OLD_ID = "old id: read the window again"
CONTROL_GONE = "control gone"
OWN_WINDOW = "own window"  # D14: a window of pseudo_hands itself, such as the popup
BLOCKED = "blocked app"
ASSISTANT_APP = "assistant app"
NOT_TARGET = "not in the target window"
CONTROL_CHANGED = "control changed"
PASSWORD = "password field"
DISABLED = "disabled"
NOT_AVAILABLE = "action not available"
NOT_APPROVED = "not approved"  # denied, closed, or no answer in time: nothing was done
CHANGED_DURING_POPUP = "changed while the popup was open: nothing done"
FAILED = "failed: the app didn't accept it"
LISTS_UNREADABLE = "assistant-apps list can't be read: nothing done"


class ActResult(TypedDict):
    control_id: str
    action: str
    status: str  # one of the statuses above, a text rule's, or ui_actions' read-back


def result(control_id: str, action: str, status: str) -> ActResult:
    return {"control_id": control_id, "action": action, "status": status}


def window_of(key: ControlKey) -> RawWindow | None:
    """The control's window read live now, or None if it closed or its handle changed program."""
    raw = read_window(key.handle, win32gui.GetForegroundWindow())
    return raw if raw is not None and raw.process_id == key.process_id else None


def window_refusal(key: ControlKey, raw: RawWindow | None, blocked: set[str], assistants: set[str]) -> str | None:
    """Step 3. None if this window may be acted on."""
    if raw is None:
        return CONTROL_GONE
    if raw.process_id == os.getpid():  # D14: never our own windows, the popup above all
        return OWN_WINDOW
    if is_blocked(raw.app, blocked):
        return BLOCKED
    if (raw.app or "").lower() in assistants:
        return ASSISTANT_APP
    target = pick_window()
    return None if target is not None and target.handle == key.handle else NOT_TARGET


def live_control(key: ControlKey, action: str) -> tuple[auto.Control | None, str | None]:
    """Step 4: (the control, None) if it's still the same control and may do this; else (None, why).
    Runs inside the caller's COM block, and the control must not be used outside it."""
    try:
        control = find_control(key.handle, key.runtime_id)
        if control is None:
            return None, CONTROL_GONE
        kind = control.ControlTypeName.removesuffix("Control")
        if (kind, name_of(control)) != (key.kind, key.name):
            return None, CONTROL_CHANGED
        if control.IsPassword:
            return None, PASSWORD
        if not control.IsEnabled:
            return None, DISABLED
        if action not in actions_of(control, kind):
            return None, NOT_AVAILABLE
        return control, None
    except COMError:  # it vanished while we looked
        return None, CONTROL_GONE


def ticked(control: auto.Control) -> bool | None:
    """A checkbox's live state for the popup's verb: True ticked, False not, None neither."""
    box = control.GetPattern(P.TogglePattern)
    return {0: False, 1: True}.get(box.ToggleState) if box is not None else None


def act_on_control(control_id: str, action: str, text: str = "") -> ActResult:
    """Do ONE action on one control from the latest read, if a person approves.

    Raises BlockedAppsError if the blocked-apps list can't be read (as focus_window does).
    """
    blocked = load_blocked_apps()  # 0. no list, no action
    try:
        assistants = load_assistant_apps()
    except AssistantAppsError:
        return result(control_id, action, LISTS_UNREADABLE)
    if action not in ACTIONS:  # 1.
        return result(control_id, action, UNKNOWN_ACTION)
    refusal = check_text(action, text)
    if refusal:
        return result(control_id, action, refusal)
    key = control_ids.registry.find(control_id)  # 2.
    if key is None:
        return result(control_id, action, OLD_ID if control_ids.registry.was_handed_out(control_id) else UNKNOWN_ID)
    raw = window_of(key)  # 3.
    refusal = window_refusal(key, raw, blocked, assistants)
    if refusal:
        return result(control_id, action, refusal)
    with auto.UIAutomationInitializerInThread():  # 4. COM for this thread, only while we use controls
        control, refusal = live_control(key, action)
        state = ticked(control) if control is not None and action == "toggle" else None
    if refusal:
        return result(control_id, action, refusal)
    wait = action_rules.budget.take()  # 5.
    if wait:
        return result(control_id, action, f"too many actions: wait {math.ceil(wait)} seconds")
    popup = question(raw.app or "", raw.title, key.kind, key.name, action, text, state, approval.TIMEOUT_SECONDS)
    if not approval.ask(popup):  # 6. THE GATE: a person decides
        return result(control_id, action, NOT_APPROVED)
    with auto.UIAutomationInitializerInThread():
        return result(control_id, action, recheck_and_act(key, action, text, state))


def recheck_and_act(key: ControlKey, action: str, text: str, state: bool | None) -> str:
    """Steps 7-8, inside one COM block: check everything again, act, read back."""
    if window_of(key) is None:
        return CHANGED_DURING_POPUP
    control, refusal = live_control(key, action)
    if refusal or (action == "toggle" and ticked(control) != state):
        return CHANGED_DURING_POPUP
    try:
        return perform(control, action, text)
    except COMError:
        return FAILED
