"""Tests for M18: the JSON-lines bridge the face talks to (pseudo_brain/bridge.py): asking,
quitting, hiding keys, and stdout. Providers and sessions are in test_brain_bridge_sessions.py.

The REAL bridge runs on in-memory pipes with bridge_fakes' fake face; everything else is FAKE.
"""

import io
import sys

import anyio
import pytest

from brain_fakes import MARKER, reply
from bridge_fakes import Face, run, world  # noqa: F401 - world is a pytest fixture
from pseudo_brain import bridge
from pseudo_brain.local_server import ServerFailure

# ---------- asking ----------

@pytest.mark.anyio
async def test_ready_lists_the_providers_and_the_tools(world: dict) -> None:
    async def nothing(face: Face) -> None:
        pass
    code, face = await run(nothing)
    ready = face.replies("ready")[0]
    assert code == 0 and ready["provider"] == "groq" and ready["session"]["messages"] == []
    assert [(p["id"], p["leaves_laptop"]) for p in ready["providers"]] == [("groq", True), ("local", False)]
    assert ready["tools"] == ["read_active_window", "focus_window", "broken_tool"] and ready["hands_pid"] is None


@pytest.mark.anyio
async def test_a_question_streams_its_events_then_turn_done(world: dict) -> None:
    async def ask(face: Face) -> None:
        await face.say({"type": "ask", "text": "What does my active window say?"})
        await face.wait_for("turn_done")
    _, face = await run(ask)
    kinds = [r["kind"] for r in face.replies("event")]
    assert kinds == ["sending", "tokens", "tool_call", "tool_result", "sending", "tokens", "answer"]
    answer = face.replies("event")[-1]["data"]
    assert answer["text"] == "Your window says BLUE." and (answer["provider"], answer["model"]) == ("groq", "big-model")
    assert face.replies("turn_done") == [{"type": "turn_done", "ok": True}]
    assert MARKER not in face.written.decode()  # a tool result's text never reaches the face (only its size)


@pytest.mark.anyio
async def test_a_second_question_while_one_runs_is_refused_as_busy(world: dict) -> None:
    world["gate"] = anyio.Event()

    async def two_at_once(face: Face) -> None:
        await face.say({"type": "ask", "text": "first"})
        await face.wait_for("event", event="sending")
        await face.say({"type": "ask", "text": "second"})
        await face.say({"type": "provider", "id": "local"})
        await face.say({"type": "list_sessions"})  # read-only: always answered
        await face.wait_for("sessions")
        world["gate"].set()
        await face.wait_for("turn_done")
    _, face = await run(two_at_once)
    assert [r["reason"] for r in face.replies("refused")] == [bridge.BUSY, bridge.BUSY]
    assert len(face.replies("turn_done")) == 1 and face.replies("switched") == []


@pytest.mark.anyio
@pytest.mark.parametrize("text", ["", "   ", "/provider local", "﻿/new"])
async def test_empty_questions_and_commands_are_never_sent(world: dict, text: str) -> None:
    async def ask(face: Face) -> None:
        await face.say({"type": "ask", "text": text})
        await face.wait_for("refused")
    _, face = await run(ask)
    assert face.replies("event") == [] and face.replies("turn_done") == []


# ---------- quitting, keys, and stdout ----------

@pytest.mark.anyio
async def test_quit_stops_a_running_question_and_the_servers(world: dict) -> None:
    world["gate"] = anyio.Event()  # never opened: the question is still running when quit arrives

    async def quit_midway(face: Face) -> None:
        await face.say({"type": "provider", "id": "local"})
        await face.wait_for("switched")
        await face.say({"type": "ask", "text": "a slow question"})
        await face.wait_for("event", event="sending")
        await face.say({"type": "quit"})
    code, face = await run(quit_midway)
    assert code == 0 and face.replies("turn_done") == [] and not world["servers"][0].running


@pytest.mark.anyio
async def test_a_key_is_hidden_in_every_line(world: dict) -> None:
    world["replies"] = [reply("the key is fake-key")]

    async def ask(face: Face) -> None:
        await face.say({"type": "ask", "text": "hi"})
        await face.wait_for("turn_done")
    _, face = await run(ask)
    assert b"fake-key" not in face.written and "the key is <hidden>" in face.replies("event")[-1]["data"]["text"]


@pytest.mark.anyio
async def test_a_provider_that_cannot_start_is_reported_and_the_bridge_exits(world: dict) -> None:
    world["refuse"]["groq"] = ServerFailure("fake: unreachable")
    face = Face()
    code = await bridge.serve(face.receive, face.write)
    assert code == 1 and face.replies() == [{"type": "refused", "reason": "can't start: fake: unreachable"}]


def test_stdout_carries_only_protocol_lines(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    protocol = io.BytesIO()
    fake_stdout = io.TextIOWrapper(protocol)  # kept here, so the pipe isn't closed when main() drops it
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(b'{"type":"quit"}\n')))
    monkeypatch.setattr(sys, "stdout", fake_stdout)

    async def noisy_serve(receive, write) -> int:
        print("a stray print somewhere in the brain")
        assert await receive() == b'{"type":"quit"}\n'
        write(b'{"type":"ready"}\n')
        return 0
    monkeypatch.setattr(bridge, "serve", noisy_serve)
    assert bridge.main() == 0
    assert protocol.getvalue() == b'{"type":"ready"}\n'
    assert "a stray print" in capsys.readouterr().err
