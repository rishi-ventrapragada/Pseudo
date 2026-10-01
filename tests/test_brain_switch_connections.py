"""Tests for M18: switching provider closes the old provider's connections (Chat.use in chat.py).

The SDK keeps a finished HTTPS connection open to reuse it (keep-alive). M18's check V5 found
the bridge still holding an idle connection to Groq, from its startup check, while in private
mode. Here a FAKE "Groq" runs inside this test on 127.0.0.1, so no network is needed and no key
is read: the REAL Model runs the real startup check (asking for the model list) over a real
socket, and we count this process's open connections to the fake Groq before and after.
"""

import dataclasses
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import psutil
import pytest

from brain_fakes import FAKE_CLOUD, FAKE_LOCAL, FakeModel, reply
from pseudo_brain import chat as chat_module
from pseudo_brain import session as session_module
from pseudo_brain.chat import Chat
from pseudo_brain.local_server import ServerFailure
from pseudo_brain.model import Model
from pseudo_brain.providers import Allowlist
from pseudo_brain.session import Session


class FakeGroq(BaseHTTPRequestHandler):
    """Answers GET /v1/models with FAKE_CLOUD's models, and keeps the connection open after."""

    protocol_version = "HTTP/1.1"  # keep-alive, like the real Groq

    def do_GET(self) -> None:  # noqa: N802 - the name http.server calls
        listed = [{"id": name, "object": "model", "created": 0, "owned_by": "fake"} for name in FAKE_CLOUD.models]
        body = json.dumps({"object": "list", "data": listed}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:  # keep the test output quiet
        pass


def open_connections_to(port: int) -> int:
    """This process's open (ESTABLISHED) connections to that port."""
    return sum(1 for c in psutil.Process().net_connections(kind="inet")
               if c.raddr and c.raddr.port == port and c.status == psutil.CONN_ESTABLISHED)


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict:
    """A Chat whose "groq" is the fake Groq on 127.0.0.1 and whose "local" is a FakeModel.

    world["refuse"][id] makes that provider fail to connect."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), FakeGroq)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    port = server.server_address[1]
    groq = dataclasses.replace(FAKE_CLOUD, base_url=f"http://127.0.0.1:{port}/v1")
    world: dict = {"port": port, "refuse": {}}
    monkeypatch.setattr(session_module, "SESSIONS_DIR", tmp_path / "sessions")

    async def connect(provider, servers, on_event):
        if provider.id in world["refuse"]:
            raise world["refuse"][provider.id]
        if provider.leaves_laptop:
            model = Model(provider, "fake-key")  # the real client, given a fake key (no .env)
            await model.check()  # the startup check: GET /v1/models, which leaves a keep-alive connection
            return model
        return FakeModel(reply("fake answer"), provider=provider)
    monkeypatch.setattr(chat_module, "connect_provider", connect)
    world["chat"] = Chat(Allowlist({"groq": groq, "local": FAKE_LOCAL}, "groq"), lambda k, d: None, [])
    yield world
    server.shutdown()
    server.server_close()


@pytest.mark.anyio
async def test_private_mode_has_no_connection_to_groq_after_switching(world: dict) -> None:
    await world["chat"].start()
    assert open_connections_to(world["port"]) == 1  # the startup check's keep-alive connection
    assert await world["chat"].switch("local")
    assert world["chat"].provider.id == "local"
    assert open_connections_to(world["port"]) == 0


@pytest.mark.anyio
async def test_opening_a_private_session_also_closes_groqs_connection(world: dict) -> None:
    Session(provider="local", started="20260101-000000-000",
            turns=[[{"role": "user", "content": "q"}, {"role": "assistant", "content": "a"}]]).save()
    await world["chat"].start()
    await world["chat"].open_session("20260101-000000-000")
    assert world["chat"].provider.id == "local" and open_connections_to(world["port"]) == 0


@pytest.mark.anyio
async def test_a_refused_switch_keeps_groq_as_it_was(world: dict) -> None:
    await world["chat"].start()
    world["refuse"]["local"] = ServerFailure("fake: Ollama didn't start")
    with pytest.raises(ServerFailure):
        await world["chat"].switch("local")
    assert world["chat"].provider.id == "groq" and open_connections_to(world["port"]) == 1
