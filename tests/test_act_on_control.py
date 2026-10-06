"""Tests for M28: act_on_control(). Every window, control and text here is FAKE; nothing real moves.

The `world` fixture is one fake window (the M27 test form) of fake controls (tests/uia_fakes.py).
world.id_for() hands out an id the way read_active_window would, and everything act.py asks
Windows is faked: the window read live, the window you were on, finding a control by runtime id.
The person at the popup is faked (popup_yes / popup_no); conftest fails any test that reaches
the real popup. A fake clock drives the 4-popups-in-2-minutes limit.
"""

import contextlib
import dataclasses
import os
from pathlib import Path

import pytest
from uia_fakes import P, FakeControl, FakePattern

from pseudo_hands.core import act, action_rules, approval, assistant_apps, blocked_apps, control_ids, ui_tree
from pseudo_hands.core.act import act_on_control
from pseudo_hands.core.action_rules import MASKED_TEXT, PopupBudget
from pseudo_hands.core.blocked_apps import BlockedAppsError
from pseudo_hands.core.control_ids import ControlIds, ControlKey
from pseudo_hands.core.windows import RawWindow

FORM = RawWindow("Pseudo M27 test form (fake)", "powershell.exe", True, False, False, handle=201, process_id=5001)
OTHER = RawWindow("Other window (fake)", "notepad.exe", True, False, False, handle=202, process_id=5002)


class World:
    def __init__(self) -> None:
        self.save, self.subject, self.remind = FakePattern(), FakePattern(), FakePattern(ToggleState=0)
        self.controls = {
            "save": FakeControl("Save fake draft", "Button", patterns={P.InvokePattern: self.save}, runtime_id=(42, 1)),
            "subject": FakeControl("Subject", "Edit", patterns={P.ValuePattern: self.subject}, runtime_id=(42, 2)),
            "remind": FakeControl("Send me reminders", "CheckBox", patterns={P.TogglePattern: self.remind},
                                  runtime_id=(42, 3)),
            "password": FakeControl("Portal password", "Edit", patterns={P.ValuePattern: FakePattern(value="fake-pass")},
                                    runtime_id=(42, 4), password=True),
            "archive": FakeControl("Archive (disabled)", "Button", patterns={P.InvokePattern: FakePattern()},
                                   runtime_id=(42, 5), enabled=False),
        }
        self.root = FakeControl(FORM.title, "Window", tuple(self.controls.values()))
        self.windows = {FORM.handle: FORM}  # what reading a window "now" returns
        self.front = FORM  # the window you were on: what read_active_window would read now
        self.ids, self.handed, self.now = ControlIds(), {}, 1000.0

    def id_for(self, name: str, window: RawWindow = FORM) -> str:
        control = self.controls[name]
        cid = self.ids.new_id()
        self.handed[cid] = ControlKey(window.handle, window.process_id, control.runtime_id,
                                      control.ControlTypeName.removesuffix("Control"), control.Name)
        self.ids.replace(self.handed)
        return cid

    def find_control(self, handle: int, runtime_id: tuple) -> FakeControl | None:
        return ui_tree.search(self.root, runtime_id) if handle in self.windows else None

    def calls(self) -> list:
        return [call for c in self.controls.values() for pattern in c.patterns.values() for call in pattern.calls]


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> World:
    (tmp_path / "blocked.txt").write_text("KeePass.exe\n", encoding="utf-8")
    (tmp_path / "assistants.txt").write_text("electron.exe\n", encoding="utf-8")
    monkeypatch.setattr(blocked_apps, "BLOCKED_APPS_FILE", tmp_path / "blocked.txt")
    monkeypatch.setattr(assistant_apps, "ASSISTANT_APPS_FILE", tmp_path / "assistants.txt")
    fake = World()
    monkeypatch.setattr(control_ids, "registry", fake.ids)
    monkeypatch.setattr(act, "read_window", lambda handle, _focused: fake.windows.get(handle))
    monkeypatch.setattr(act, "pick_window", lambda: fake.front)
    monkeypatch.setattr(act, "find_control", fake.find_control)
    monkeypatch.setattr(act.win32gui, "GetForegroundWindow", lambda: 0)
    monkeypatch.setattr(act.auto, "UIAutomationInitializerInThread", contextlib.nullcontext)
    monkeypatch.setattr(action_rules, "budget", PopupBudget(clock=lambda: fake.now))
    return fake


# ---------- approve, deny ----------

def test_approve_acts_once_and_reads_the_effect_back(world: World, popup_yes) -> None:
    result = act_on_control(world.id_for("subject"), "set_text", "Lab report draft")
    assert result["status"] == "done" and world.subject.calls == [("SetValue", "Lab report draft", 0)]
    assert len(popup_yes.previews) == 1


def test_a_no_changes_nothing(world: World, popup_no) -> None:
    assert act_on_control(world.id_for("remind"), "toggle")["status"] == act.NOT_APPROVED
    assert world.calls() == [] and world.remind.ToggleState == 0


@pytest.mark.parametrize("answer", [None, 1, "yes"])
def test_anything_but_a_real_yes_changes_nothing(world: World, monkeypatch: pytest.MonkeyPatch, answer) -> None:
    monkeypatch.setattr(approval, "approver", lambda _question: answer)
    assert act_on_control(world.id_for("save"), "press")["status"] == act.NOT_APPROVED and world.calls() == []


def test_the_popup_shows_windows_data_and_the_model_gets_only_a_status(world: World, popup_yes) -> None:
    world.controls["save"].rename("Send to Rahul Verma (fake)")
    cid = world.id_for("save")
    result = act_on_control("#" + cid.upper(), "press")  # models sometimes copy the # or change the case
    assert result == {"control_id": "#" + cid.upper(), "action": "press", "status": "pressed"}
    popup = popup_yes.previews[0]
    assert "App:      powershell.exe" in popup and 'Window:   "Pseudo M27 test form (fake)"' in popup
    assert 'Control:  Button "Send to Rahul Verma (fake)"' in popup and "Action:   Press it" in popup


def test_the_toggle_popup_says_tick_or_untick_from_the_live_box(world: World, popup_no) -> None:
    cid = world.id_for("remind")
    act_on_control(cid, "toggle")
    world.remind.ToggleState = 1
    act_on_control(cid, "toggle")
    assert "Action:   Tick it" in popup_no.previews[0] and "Action:   Untick it" in popup_no.previews[1]


# ---------- refused before any popup, and nothing touched ----------

def refusal_cases() -> dict:
    def own(w: World) -> tuple:  # D14: e.g. the approval popup's own OK button
        mine = dataclasses.replace(FORM, process_id=os.getpid())
        w.windows[FORM.handle] = w.front = mine
        return w.id_for("save", mine), "press", ""

    def app(name: str):
        def setup(w: World) -> tuple:
            window = dataclasses.replace(FORM, app=name)
            w.windows[FORM.handle] = w.front = window
            return w.id_for("save", window), "press", ""
        return setup

    def then(change, name: str = "save", action: str = "press", text: str = ""):
        def setup(w: World) -> tuple:
            cid = w.id_for(name)
            change(w)
            return cid, action, text
        return setup

    return {
        "unknown action": (lambda w: (w.id_for("save"), "delete", ""), act.UNKNOWN_ACTION),
        "masked text": (lambda w: (w.id_for("subject"), "set_text", "Call [PERSON] tomorrow"), MASKED_TEXT),
        "text with a press": (lambda w: (w.id_for("save"), "press", "x"), "this action takes no text"),
        "unknown id": (lambda w: ("c999", "press", ""), act.UNKNOWN_ID),
        "old id": (then(lambda w: w.ids.replace({})), act.OLD_ID),
        "window closed": (then(lambda w: w.windows.clear()), act.CONTROL_GONE),
        "handle reused": (then(lambda w: w.windows.update({FORM.handle: dataclasses.replace(FORM, process_id=9)})),
                          act.CONTROL_GONE),
        "control removed": (then(lambda w: w.root._children.remove(w.controls["save"])), act.CONTROL_GONE),
        "own window": (own, act.OWN_WINDOW),
        "blocked app": (app("KeePass.exe"), act.BLOCKED),
        "assistant app": (app("Electron.exe"), act.ASSISTANT_APP),
        "not the target": (then(lambda w: setattr(w, "front", OTHER)), act.NOT_TARGET),
        "renamed": (then(lambda w: w.controls["save"].rename("Marked (fake)")), act.CONTROL_CHANGED),
        "password": (lambda w: (w.id_for("password"), "set_text", "x"), act.PASSWORD),
        "disabled": (lambda w: (w.id_for("archive"), "press", ""), act.DISABLED),
        "not offered": (lambda w: (w.id_for("subject"), "toggle", ""), act.NOT_AVAILABLE),
    }


@pytest.mark.parametrize("case", sorted(refusal_cases()))
def test_refusals_happen_before_any_popup_and_touch_nothing(world: World, popup_yes, case: str) -> None:
    setup, expected = refusal_cases()[case]
    control_id, action, text = setup(world)
    assert act_on_control(control_id, action, text)["status"] == expected
    assert popup_yes.previews == [] and world.calls() == []


def test_a_missing_blocked_list_stops_everything(world: World, popup_yes, monkeypatch: pytest.MonkeyPatch,
                                                 tmp_path: Path) -> None:
    monkeypatch.setattr(blocked_apps, "BLOCKED_APPS_FILE", tmp_path / "missing.txt")
    with pytest.raises(BlockedAppsError):
        act_on_control(world.id_for("save"), "press")
    assert popup_yes.previews == [] and world.calls() == []


def test_an_unreadable_assistant_list_stops_everything(world: World, popup_yes, monkeypatch: pytest.MonkeyPatch,
                                                       tmp_path: Path) -> None:
    monkeypatch.setattr(assistant_apps, "ASSISTANT_APPS_FILE", tmp_path / "missing.txt")
    assert act_on_control(world.id_for("save"), "press")["status"] == act.LISTS_UNREADABLE
    assert popup_yes.previews == [] and world.calls() == []
