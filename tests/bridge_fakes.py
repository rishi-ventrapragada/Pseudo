"""Shared fakes for the bridge's tests (M18): test_brain_bridge*.py and test_brain_hands_pid.py.
Not a test file itself.

The REAL bridge runs on in-memory pipes. A fake face (below) writes lines to it and reads
every byte it writes back. Everything else is FAKE: brain_fakes' providers and scripted
models, the in-memory fake pseudo_hands, and sessions in a temporary folder.
Test files import `world` (a pytest fixture) and `run` from here.
"""

import json
from pathlib import Path

import anyio
import pytest

from brain_fakes import FAKE_CLOUD, FAKE_HANDS, FAKE_LOCAL, FakeModel, reply
from pseudo_brain import bridge
from pseudo_brain import chat as chat_module
from pseudo_brain import session as session_module
from pseudo_brain.hands import connect_hands
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
