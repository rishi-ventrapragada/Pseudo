"""Tests for M18: the JSON-lines bridge the face talks to (pseudo_brain/bridge.py).

The REAL bridge runs on in-memory pipes. A fake face (below) writes lines to it and reads
every byte it writes back. Everything else is FAKE: brain_fakes' providers and scripted
models, the in-memory fake pseudo_hands, and sessions in a temporary folder.
"""

import io
import json
import sys
from pathlib import Path

import anyio
import pytest

from brain_fakes import FAKE_CLOUD, FAKE_HANDS, FAKE_LOCAL, MARKER, FakeModel, reply
from pseudo_brain import bridge
from pseudo_brain import chat as chat_module
from pseudo_brain import session as session_module
from pseudo_brain.hands import connect_hands
from pseudo_brain.local_server import ServerFailure
from pseudo_brain.providers import Allowlist

READ_THEN_ANSWER = [reply(tools=[("read_active_window", "{}")]), reply("Your window says BLUE.")]


class GatedModel(FakeModel):
    """A FakeModel that waits until the test opens the gate: a question that is still running."""

    def __init__(self, *replies, gate: anyio.Event, **kwargs) -> None:
        super().__init__(*replies, **kwargs)
        self.gate = gate

    async def complete(self, request: dict):
        await self.gate.wait()
        return await super().complete(request)


class Face:
    """Plays the Electron window: one pipe into the bridge's stdin, one out of its stdout."""

    def __init__(self) -> None:
        self.to_bridge, self.bridge_reads = anyio.create_memory_object_stream(100)
        self.written = bytearray()

    async def receive(self) -> bytes:  # what the bridge reads from stdin
        try:
            return await self.bridge_reads.receive()
        except anyio.EndOfStream:
            return b""

    def write(self, data: bytes) -> None:  # what the bridge writes to stdout
        self.written += data

    def replies(self, kind: str | None = None) -> list[dict]:
        every = [json.loads(line) for line in bytes(self.written).splitlines()]
        return [r for r in every if kind in (None, r["type"])]

    async def say(self, message: dict | bytes) -> None:
        await self.to_bridge.send(message if isinstance(message, bytes) else json.dumps(message).encode() + b"\n")

    async def wait_for(self, kind: str, count: int = 1, event: str | None = None) -> dict:
        """Wait until the bridge has sent `count` replies of this type (or events of this kind)."""
        def matching() -> list[dict]:
            return [r for r in self.replies(kind) if event in (None, r.get("kind"))]
        with anyio.fail_after(5):
            while len(matching()) < count:
                await anyio.sleep(0.01)
        return matching()[count - 1]


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict:
    """world["replies"] scripts each new model; world["gate"] (if set) holds its replies back."""
    world: dict = {"replies": READ_THEN_ANSWER, "gate": None, "refuse": {}, "servers": []}
    monkeypatch.setattr(session_module, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(bridge, "load_allowlist", lambda: Allowlist({"groq": FAKE_CLOUD, "local": FAKE_LOCAL}, "groq"))
    monkeypatch.setattr(bridge, "connect_hands", lambda: connect_hands(FAKE_HANDS))

    async def fake_connect(provider, servers, on_event):
        if provider.id in world["refuse"]:
            raise world["refuse"][provider.id]
        if not provider.leaves_laptop:
            on_event("server_starting", {"provider": provider.id, "address": provider.address})
            world["servers"].append(servers.setdefault(provider.id, FakeServer(provider)))
        if world["gate"]:
            return GatedModel(*world["replies"], gate=world["gate"], provider=provider)
        return FakeModel(*world["replies"], provider=provider)
    monkeypatch.setattr(chat_module, "connect_provider", fake_connect)
    return world


class FakeServer:
    def __init__(self, provider) -> None:
        self.provider, self.running = provider, True

    def stop(self) -> bool:
        was_running, self.running = self.running, False
        return was_running


async def run(face_script) -> tuple[int, Face]:
    """Run the real bridge while face_script(face) plays the window. Returns (exit code, face)."""
    face, result = Face(), {}

    async def brain() -> None:
        result["code"] = await bridge.serve(face.receive, face.write)
    with anyio.fail_after(10):
        async with anyio.create_task_group() as tasks:
            tasks.start_soon(brain)
            await face.wait_for("ready")
            await face_script(face)
            await face.to_bridge.aclose()  # the window is gone: the bridge must stop on its own
    return result["code"], face


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


# ---------- providers and sessions ----------

@pytest.mark.anyio
async def test_switching_provider_starts_a_new_session(world: dict) -> None:
    async def switch(face: Face) -> None:
        await face.say({"type": "ask", "text": "hello"})
        await face.wait_for("turn_done")
        await face.say({"type": "provider", "id": "local"})
        await face.wait_for("switched")
    _, face = await run(switch)
    switched = face.replies("switched")[0]
    assert switched["provider"] == "local" and switched["session"]["messages"] == []
    assert switched["session"]["name"] != face.replies("ready")[0]["session"]["name"]
    assert face.replies("event")[-1] == {"type": "event", "kind": "server_starting",
                                         "data": {"provider": "local", "address": "127.0.0.1:11434"}}


@pytest.mark.anyio
@pytest.mark.parametrize("message, reason", [
    ({"type": "provider", "id": "cloudy"}, '"cloudy" is not in the allowlist'),
    ({"type": "provider", "id": "groq"}, "already using groq"),
    ({"type": "provider", "id": "local"}, "cloud isn't switched off: fake"),
    ({"type": "open_session", "name": "..\\..\\secret"}, "that is not a session name"),
    ({"type": "delete_everything"}, "not a message the brain understands"),
    (b"this is not json\n", "not a message the brain understands"),
])
async def test_refusals_say_why_and_change_nothing(world: dict, message, reason: str) -> None:
    world["refuse"]["local"] = ServerFailure("cloud isn't switched off: fake")

    async def refused(face: Face) -> None:
        await face.say(message)
        await face.wait_for("refused")
    _, face = await run(refused)
    assert reason in face.replies("refused")[0]["reason"] and face.replies("switched") == []


@pytest.mark.anyio
async def test_sessions_are_listed_and_one_opens_on_its_own_provider(world: dict) -> None:
    session_module.Session(provider="local", started="20260101-000000-000",
                           turns=[[{"role": "user", "content": "private question"},
                                   {"role": "assistant", "content": "private answer"}]]).save()

    async def reopen(face: Face) -> None:
        await face.say(b"\xef\xbb\xbf" + json.dumps({"type": "list_sessions"}).encode() + b"\n")  # with a BOM
        await face.wait_for("sessions")
        await face.say({"type": "open_session", "name": "20260101-000000-000"})
        await face.wait_for("session")
        await face.say({"type": "ask", "text": "and now?"})
        await face.wait_for("turn_done")
    _, face = await run(reopen)
    assert face.replies("sessions")[0]["items"] == [{"name": "20260101-000000-000", "provider": "local",
                                                     "questions": 1, "title": "private question"}]
    opened = face.replies("session")[0]
    assert opened["provider"] == "local" and [m["content"] for m in opened["messages"]] == ["private question",
                                                                                          "private answer"]
    assert face.replies("event")[-1]["data"]["provider"] == "local"  # the next answer came from local


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
