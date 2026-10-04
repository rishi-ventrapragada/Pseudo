"""Tests for M28: act_on_control()'s limit (4 action popups in 2 minutes), its re-check after the
popup, and what it reports. Every window and control here is FAKE (the `world` fixture from
test_act_on_control.py); the person at the popup is faked, and nothing real moves.
"""

import json

import pytest
from test_act_on_control import World, world  # noqa: F401 - world is a pytest fixture

from pseudo_hands.core import act, approval
from pseudo_hands.core.act import act_on_control

# ---------- at most 4 action popups in 2 minutes ----------

def test_a_fifth_popup_within_two_minutes_is_refused_before_it_shows(world: World, popup_no) -> None:
    cid = world.id_for("save")
    for _ in range(4):
        assert act_on_control(cid, "press")["status"] == act.NOT_APPROVED
        world.now += 10
    assert act_on_control(cid, "press")["status"] == "too many actions: wait 80 seconds"
    assert len(popup_no.previews) == 4
    world.now += 80
    assert act_on_control(cid, "press")["status"] == act.NOT_APPROVED and len(popup_no.previews) == 5


def test_refusals_dont_use_up_the_limit(world: World, popup_no) -> None:
    for _ in range(6):
        act_on_control("c999", "press")
    assert act_on_control(world.id_for("save"), "press")["status"] == act.NOT_APPROVED


# ---------- checked again after the popup ----------

@pytest.mark.parametrize("change", ["renamed", "closed", "ticked meanwhile", "disabled"])
def test_a_change_while_the_popup_is_open_means_nothing_is_done(world: World, monkeypatch: pytest.MonkeyPatch,
                                                                change: str) -> None:
    cid = world.id_for("remind")
    changes = {"renamed": lambda: world.controls["remind"].rename("Something else (fake)"),
               "closed": world.windows.clear,
               "ticked meanwhile": lambda: setattr(world.remind, "ToggleState", 1),
               "disabled": lambda: setattr(world.controls["remind"], "enabled", False)}

    def person(_question: str) -> bool:
        changes[change]()
        return True
    monkeypatch.setattr(approval, "approver", person)
    assert act_on_control(cid, "toggle")["status"] == act.CHANGED_DURING_POPUP and world.remind.calls == []


def test_an_app_that_rejects_the_action_is_reported_as_failed(world: World, popup_yes) -> None:
    world.save.refuse = True
    assert act_on_control(world.id_for("save"), "press")["status"] == act.FAILED


def test_nothing_from_the_screen_reaches_the_result(world: World, popup_yes) -> None:
    world.subject._value = "Rahul Verma, +91 98765 43210 (fake)"
    result = act_on_control(world.id_for("subject"), "insert_text", " ok")
    assert result["status"] == "done" and set(result) == {"control_id", "action", "status"}
    assert "Rahul" not in json.dumps(result) and "98765" not in json.dumps(result)
