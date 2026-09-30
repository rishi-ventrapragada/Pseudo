"""M16: private mode's own server. pseudo_brain starts it (Ollama), and stops it again.

What it demonstrates: starting and supervising a helper process, the way hands.py
already starts pseudo_hands. Private mode needs a model server on this laptop, so when
you switch to it, pseudo_brain runs the server command from providers.toml and waits
until it answers; when pseudo_brain exits, it stops the server and everything it started.
Nothing here names Ollama: the command, the settings file and the variable all come
from providers.toml (D11).

Safety rules (D16), all checked BEFORE any question can reach the server:
  - Cloud must be switched off in the server's own settings file (for Ollama,
    server.json says "disable_ollama_cloud": true). If it isn't, nothing is started.
  - The server is told to listen on base_url's address (127.0.0.1:port) only. Once it
    answers, whatever listens on that port must be on 127.0.0.1 and nowhere else;
    if not, a server we started is stopped, and the switch fails.
  - If it can't start, the switch fails visibly with the reason. Nothing falls back.
  - A server that was already running (not started by pseudo_brain) is used, never stopped.
"""

import json
import os
import socket
import subprocess
import time
from pathlib import Path

import anyio
import psutil

from pseudo_brain.providers import LOCALHOST, Provider
from pseudo_brain.session import SESSIONS_DIR

READY_SECONDS = 30.0  # Ollama answers in about a second; a cold disk can be slower
LOG_FILE = SESSIONS_DIR.parent / "local_server.log"  # %LOCALAPPDATA%\Pseudo\local_server.log


class ServerFailure(Exception):
    """The private server can't be used. The message says why, in plain words."""


def cloud_is_off(provider: Provider) -> bool:
    """True only if the server's settings file exists and says <key>: true."""
    server = provider.server
    try:
        return json.loads(server.cloud_off_file.read_text(encoding="utf-8")).get(server.cloud_off_key) is True
    except (OSError, ValueError, AttributeError):  # missing, unreadable, or not a JSON object
        return False


def answers(address: str) -> bool:
    """Does something accept connections at host:port?"""
    host, port = address.rsplit(":", 1)
    try:
        with socket.create_connection((host, int(port)), timeout=0.5):
            return True
    except OSError:
        return False


def listening_on(port: int) -> set[str]:
    """Every local address that something on this laptop listens on for this port."""
    return {c.laddr.ip for c in psutil.net_connections(kind="inet")
            if c.status == psutil.CONN_LISTEN and c.laddr.port == port}


class LocalServer:
    """One private provider's server: started (and later stopped) by us, or found already running."""

    def __init__(self, provider: Provider) -> None:
        self.provider = provider
        self.process: subprocess.Popen | None = None
        self.log = None

    @property
    def started_by_us(self) -> bool:
        return self.process is not None

    async def start(self) -> dict:
        """Make sure the server is up and safe. Returns what happened; raises ServerFailure if it can't."""
        provider, server = self.provider, self.provider.server
        if not cloud_is_off(provider):
            raise ServerFailure(f'cloud isn\'t switched off: {server.cloud_off_file} must say '
                                f'"{server.cloud_off_key}": true, so nothing was started')
        began = time.monotonic()
        if not answers(provider.address):
            self.launch()
            while not answers(provider.address):
                if self.process.poll() is not None:
                    code = self.process.returncode
                    self.stop()
                    raise ServerFailure(f"the server exited at once (code {code}); see {LOG_FILE}")
                if time.monotonic() - began > READY_SECONDS:
                    self.stop()
                    raise ServerFailure(f"the server didn't answer within {READY_SECONDS:.0f} s; see {LOG_FILE}")
                await anyio.sleep(0.25)
        others = listening_on(int(provider.address.rsplit(":", 1)[1])) - {LOCALHOST}
        if others:
            stopped = self.stop()
            raise ServerFailure(f"something listens on port {provider.address.rsplit(':', 1)[1]} outside "
                                f"{LOCALHOST} too, so it isn't private" + (" (our server was stopped)" if stopped else ""))
        return {"started_by_us": self.started_by_us, "seconds": time.monotonic() - began,
                "address": provider.address}

    def launch(self) -> None:
        """Run the server command, told to listen on base_url's address only. No console window."""
        server = self.provider.server
        if not Path(server.command[0]).exists():
            raise ServerFailure(f"{Path(server.command[0]).name} not found at {Path(server.command[0]).parent}")
        env = {**os.environ, server.address_env: self.provider.address}
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        self.log = open(LOG_FILE, "ab")  # the server's own log, on this laptop only
        self.process = subprocess.Popen(list(server.command), env=env, stdin=subprocess.DEVNULL, stdout=self.log,
                                        stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)

    def stop(self) -> bool:
        """Stop the server if WE started it, with every process it started. True if something was stopped."""
        if self.process is None:
            return False
        try:
            parent = psutil.Process(self.process.pid)
            family = parent.children(recursive=True) + [parent]  # model runners first, then the server
        except psutil.NoSuchProcess:
            family = []
        for proc in family:
            try:
                proc.kill()
            except psutil.NoSuchProcess:  # already gone
                pass
        self.process.wait(timeout=10)
        self.process = None
        if self.log:
            self.log.close()
            self.log = None
        return True
