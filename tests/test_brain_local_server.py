"""Tests for M16: private mode's own server (pseudo_brain/local_server.py).

No real Ollama and no real server.json: the "server" is a tiny Python program that
listens on 127.0.0.1 where it is told to (through FAKE_M16_HOST), and the settings file
is a fake one in a temp folder. The processes are real, so starting and stopping are real.
"""

import json
import socket
import sys
from pathlib import Path

import psutil
import pytest

from pseudo_brain import local_server, model
from pseudo_brain.local_server import LocalServer, ServerFailure
from pseudo_brain.model import ModelFailure, connect_provider
from pseudo_brain.providers import Provider, Server

FAKE_SERVER = """
import os, socket, subprocess, sys
child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])  # like a model runner
open(sys.argv[1], "w").write(str(child.pid))
host, port = os.environ["FAKE_M16_HOST"].rsplit(":", 1)
s = socket.socket(); s.bind((host, int(port))); s.listen()
while True:
    connection, _ = s.accept(); connection.close()
"""


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def private(tmp_path: Path, command: list[str], settings: dict | None = None) -> Provider:
    """A fake private provider whose server is `command`, with a fake settings file."""
    (tmp_path / "server.json").write_text(json.dumps({"cloud_off": True} if settings is None else settings),
                                          encoding="utf-8")
    server = Server(tuple(command), "FAKE_M16_HOST", tmp_path / "server.json", "cloud_off")
    return Provider("local", "Fake local", f"http://127.0.0.1:{free_port()}/v1", "", ("tiny-model",), False,
                    "fake note", 180.0, 2500, server)


@pytest.fixture(autouse=True)
def temp_log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(local_server, "LOG_FILE", tmp_path / "server.log")


def running(pid: int) -> bool:
    return psutil.pid_exists(pid) and psutil.Process(pid).status() != psutil.STATUS_ZOMBIE


@pytest.mark.anyio
async def test_it_starts_the_server_on_127_0_0_1_and_stops_it_with_everything_it_started(tmp_path: Path) -> None:
    provider = private(tmp_path, [sys.executable, "-c", FAKE_SERVER, str(tmp_path / "child.pid")])
    server = LocalServer(provider)
    status = await server.start()
    child = int((tmp_path / "child.pid").read_text())
    assert status["started_by_us"] and local_server.answers(provider.address)
    assert local_server.listening_on(int(provider.address.split(":")[1])) == {"127.0.0.1"}
    pid = server.process.pid
    assert server.stop() and not local_server.answers(provider.address)
    assert not running(pid) and not running(child)  # the "model runner" is gone too
    assert not server.stop()  # stopping twice is harmless


@pytest.mark.anyio
@pytest.mark.parametrize("settings", [{"cloud_off": False}, {"something_else": True}, {"cloud_off": "true"}])
async def test_nothing_starts_unless_cloud_is_switched_off(tmp_path: Path, settings: dict) -> None:
    marker = tmp_path / "was_started.txt"
    provider = private(tmp_path, [sys.executable, "-c", f"open({str(marker)!r}, 'w')"], settings)
    server = LocalServer(provider)
    with pytest.raises(ServerFailure, match="cloud isn't switched off"):
        await server.start()
    assert not server.started_by_us and not marker.exists()


@pytest.mark.anyio
async def test_a_missing_settings_file_counts_as_cloud_on(tmp_path: Path) -> None:
    provider = private(tmp_path, [sys.executable, "-c", "pass"])
    (tmp_path / "server.json").unlink()
    with pytest.raises(ServerFailure, match="cloud isn't switched off"):
        await LocalServer(provider).start()


@pytest.mark.anyio
async def test_a_server_that_exits_at_once_fails_visibly(tmp_path: Path) -> None:
    server = LocalServer(private(tmp_path, [sys.executable, "-c", "raise SystemExit(3)"]))
    with pytest.raises(ServerFailure, match=r"exited at once \(code 3\)"):
        await server.start()
    assert not server.started_by_us


@pytest.mark.anyio
async def test_a_server_that_never_answers_is_stopped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(local_server, "READY_SECONDS", 1.0)
    server = LocalServer(private(tmp_path, [sys.executable, "-c", "import time; time.sleep(60)"]))
    with pytest.raises(ServerFailure, match="didn't answer within 1 s"):
        await server.start()
    assert not server.started_by_us


@pytest.mark.anyio
async def test_a_missing_server_program_fails_visibly(tmp_path: Path) -> None:
    with pytest.raises(ServerFailure, match="nope.exe not found"):
        await LocalServer(private(tmp_path, [str(tmp_path / "nope.exe"), "serve"])).start()


@pytest.mark.anyio
async def test_a_server_already_running_is_used_but_never_stopped(tmp_path: Path) -> None:
    provider = private(tmp_path, [sys.executable, "-c", "raise SystemExit('must not run')"])
    with socket.socket() as someone_elses:
        someone_elses.bind(("127.0.0.1", int(provider.address.split(":")[1])))
        someone_elses.listen()
        server = LocalServer(provider)
        status = await server.start()
        assert not status["started_by_us"] and not server.stop()
        assert local_server.answers(provider.address)  # still there


@pytest.mark.anyio
async def test_a_server_listening_outside_127_0_0_1_is_stopped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(local_server, "listening_on", lambda port: {"127.0.0.1", "0.0.0.0"})
    server = LocalServer(private(tmp_path, [sys.executable, "-c", FAKE_SERVER, str(tmp_path / "child.pid")]))
    with pytest.raises(ServerFailure, match=r"isn't private \(our server was stopped\)"):
        await server.start()
    assert not server.started_by_us


# ---------- connect_provider (model.py): server first, then the check ----------

@pytest.mark.anyio
async def test_connecting_starts_the_server_says_so_and_checks_the_provider(tmp_path: Path,
                                                                           monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_check(self) -> None:
        assert local_server.answers(self.provider.address)  # the server is up BEFORE the check
    monkeypatch.setattr(model.Model, "check", fake_check)
    provider = private(tmp_path, [sys.executable, "-c", FAKE_SERVER, str(tmp_path / "child.pid")])
    servers, events = {}, []
    connected = await connect_provider(provider, servers, lambda kind, data: events.append(kind))
    assert connected.provider is provider and events == ["server_starting", "server_ready"]
    assert servers["local"].stop()


@pytest.mark.anyio
async def test_a_server_started_for_a_provider_that_fails_its_check_is_stopped(tmp_path: Path,
                                                                             monkeypatch: pytest.MonkeyPatch) -> None:
    async def failing_check(self) -> None:
        raise ModelFailure("Fake local at 127.0.0.1 doesn't have tiny-model")
    monkeypatch.setattr(model.Model, "check", failing_check)
    provider = private(tmp_path, [sys.executable, "-c", FAKE_SERVER, str(tmp_path / "child.pid")])
    servers: dict = {}
    with pytest.raises(ModelFailure, match="doesn't have tiny-model"):
        await connect_provider(provider, servers, lambda kind, data: None)
    assert not servers["local"].started_by_us and not local_server.answers(provider.address)
