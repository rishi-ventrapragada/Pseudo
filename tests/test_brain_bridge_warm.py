"""M32: warm sessions over the bridge (pseudo_brain/bridge_warm.py), and through chat.py.

The REAL bridge runs on in-memory pipes with bridge_fakes' fake face. Claude Code is FAKE
(tests/fixtures/fake_claude.py) and the billing check is replaced, so nothing here touches a real
login, the network or a window. Every test ends by checking that no fake Claude Code is left running.
"""

from pathlib import Path

import anyio
import pytest
from bridge_fakes import Face, run, world  # noqa: F401 - world is a pytest fixture
from claude_fakes import brain, fake_world, fakes_running

from pseudo_brain import bridge, bridge_warm
from pseudo_brain.action_brain import Routing

ACTION = "Tick the fake reminders box."
QUESTION = "What does my active window say?"


@pytest.fixture
def claude(world: dict, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict:  # noqa: F811
    """The bridge's world, plus an action brain that is the fake Claude Code, and a fast tick."""
    monkeypatch.setattr(bridge, "load_routing", lambda: Routing("focus_window", brain()))
    monkeypatch.setattr(bridge_warm, "TICK_SECONDS", 0.05)
    return fake_world(monkeypatch, tmp_path)


def steps(face: Face) -> list[str]:
    return [reply["kind"] for reply in face.replies("event")]


async def ask(face: Face, text: str, done: int) -> None:
    await face.say({"type": "ask", "text": text})
    await face.wait_for("turn_done", count=done)


@pytest.mark.anyio
async def test_warm_sessions_are_off_until_the_face_says_on(claude: dict) -> None:
    async def one_request(face: Face) -> None:
        await ask(face, ACTION, 1)
    _, face = await run(one_request)
    assert "launch" in steps(face) and "warm_opened" not in steps(face) and "warm" not in steps(face)
    off = {"type": "warm", "on": False, "open": False, "ram_mb": None, "asked": 0, "of": 6, "idle_minutes": 10, "note": ""}
    assert face.replies("warm") == [off]  # said once; many ticks passed, and an unchanged state is never repeated
    assert fakes_running() == []


@pytest.mark.anyio
async def test_switched_on_a_launch_opens_a_session_and_the_next_request_uses_it(claude: dict) -> None:
    async def two_requests(face: Face) -> None:
        await face.say({"type": "warm_sessions", "on": True})
        await face.wait_for("warm")
        await ask(face, ACTION, 1)
        await ask(face, ACTION, 2)
        with anyio.fail_after(5):  # the tick measures the open session's memory
            while not any(reply["ram_mb"] for reply in face.replies("warm")):
                await anyio.sleep(0.02)
    _, face = await run(two_requests)
    assert steps(face).count("launch") == 1 and steps(face).count("warm_opened") == 1 and steps(face).count("warm") == 1
    assert steps(face).count("billing") == 3  # the launch, the session's start, the warm request
    states = face.replies("warm")
    assert states[0] == {"type": "warm", "on": True, "open": False, "ram_mb": None, "asked": 0, "of": 6,
                         "idle_minutes": 10, "note": ""}
    assert any(state["open"] and state["asked"] == 1 and state["ram_mb"] > 0 for state in states)
    assert all(ACTION not in str(state) and "Fake answer" not in str(state) for state in states)  # numbers and names only
    assert [reply["ok"] for reply in face.replies("turn_done")] == [True, True]
    assert fakes_running() == []  # the face went away: the bridge stopped the session on its way out


@pytest.mark.anyio
async def test_switching_off_stops_the_open_session(claude: dict) -> None:
    async def on_then_off(face: Face) -> None:
        await face.say({"type": "warm_sessions", "on": True})
        await ask(face, ACTION, 1)
        assert fakes_running() != []  # a session is open behind the launch
        await face.say({"type": "warm_sessions", "on": False})
        with anyio.fail_after(5):
            while not any(reply["note"] == "stopped: warm sessions were turned off" for reply in face.replies("warm")):
                await anyio.sleep(0.02)
        assert fakes_running() == []  # freed, while the bridge is still running
        await ask(face, ACTION, 2)
    _, face = await run(on_then_off)
    last = face.replies("warm")[-1]
    assert (last["on"], last["open"], last["ram_mb"]) == (False, False, None)
    assert steps(face).count("launch") == 2 and steps(face).count("warm_opened") == 1 and fakes_running() == []


@pytest.mark.anyio
async def test_the_switch_works_while_a_question_runs_and_ignores_anything_but_true_or_false(claude: dict,
                                                                                            world: dict) -> None:  # noqa: F811
    world["gate"] = anyio.Event()

    async def switch_while_busy(face: Face) -> None:
        await face.say({"type": "ask", "text": QUESTION})
        await face.wait_for("event", event="sending")
        await face.say({"type": "warm_sessions", "on": "yes"})
        await face.say({"type": "warm_sessions"})
        await face.say({"type": "warm_sessions", "on": True})
        await face.wait_for("warm")
        world["gate"].set()
        await face.wait_for("turn_done")
    _, face = await run(switch_while_busy)
    assert [reply["on"] for reply in face.replies("warm")] == [True] and face.replies("refused") == []


@pytest.mark.anyio
async def test_a_question_that_is_not_an_action_request_never_touches_the_session(claude: dict) -> None:
    async def action_then_question(face: Face) -> None:
        await face.say({"type": "warm_sessions", "on": True})
        await ask(face, ACTION, 1)
        await ask(face, QUESTION, 2)
    _, face = await run(action_then_question)
    assert steps(face).count("routed") == 1 and steps(face).count("warm") == 0
    assert all(state["asked"] == 0 for state in face.replies("warm")) and fakes_running() == []


def test_the_log_gets_the_change_and_never_a_question(capsys: pytest.CaptureFixture) -> None:
    class FakeBridge:
        sent: list = []

        def send(self, kind: str, **fields) -> None:
            self.sent.append((kind, fields))

    report = bridge_warm.Reporter(FakeBridge())
    state = {"on": True, "open": True, "ram_mb": 350.0, "asked": 1, "of": 6, "idle_minutes": 10, "note": ""}
    report(state)
    report(dict(state))  # the same again: not sent twice
    report({**state, "ram_mb": 352.5})  # only the memory moved: sent, but not worth a log line
    report({**state, "open": False, "ram_mb": None, "asked": 0, "note": "stopped: idle for 10 minutes"})
    assert len(FakeBridge.sent) == 3 and all(kind == "warm" for kind, _fields in FakeBridge.sent)
    assert capsys.readouterr().err.splitlines() == [
        "warm: on, a session is open", "warm: on, none open (stopped: idle for 10 minutes)"]
