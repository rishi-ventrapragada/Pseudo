"""M18: the bridge between Pseudo's face (the Electron window) and pseudo_brain.

What it demonstrates: a PROTOCOL over a child-process pipe. The face starts this file as its
child process (python -m pseudo_brain.bridge) and the two talk in JSON lines: one JSON object
per line, the face writing to our stdin and reading our stdout. It is the idea of MCP's stdio
link from pseudo_brain to pseudo_hands (M14). No port is opened, so no other program and no
web page can reach the brain (D18: the M5 and M17 lesson, "anything reachable gets reached").

Face -> brain:  ask {text} | provider {id} | new_session | list_sessions | open_session {name} | quit
Brain -> face:  ready {providers, provider, session, tools, hands_pid, action_brain, suggestions} | event {kind, data}
                | refused {reason} | switched {provider, session} | session {name, provider, title, messages}
                | sessions {items} | turn_done {ok}
More messages, each listed in its own file: voice (bridge_voice.py, M26), the warm session (bridge_warm.py,
M32), saved chats (bridge_sessions.py, M41), the look-at chip and the memory browser (bridge_sees.py, M42).
`event` carries every event the loop, the model and the private server report (loop.py).

Rules:
  - stdout carries ONLY protocol lines: sys.stdout is pointed at stderr, so a stray print()
    anywhere lands in the log, never in the protocol.
  - Every line has every key in use replaced by <hidden> before it is written (as the terminal does).
  - One job at a time. While a question, a switch or opening a session is running, another one
    is refused as busy. Listing and searching chats, and quit, always work; quit stops a running question.
    (M42) The chip and the memory browser are answered only while no job runs (bridge_sees.py).
  - A byte-order mark is stripped (PowerShell adds one; M16), and a question starting with "/"
    is never sent to the model (M16): the face has buttons, not commands.
  - hands_pid names the pseudo_hands process, so the face can let only it bring the approval
    popup to the front before each tool runs (face/foreground.js). None if it isn't certain.
  - This file decides nothing (D11): chat.py holds the rules, loop.py the loop.
"""

import json
import sys
from collections.abc import Awaitable, Callable

import anyio
from anyio.abc import TaskGroup

from pseudo_brain import bridge_sees, bridge_sessions, bridge_voice, bridge_warm
from pseudo_brain.action_brain import action_brain_info, load_routing
from pseudo_brain.bridge_sessions import SESSION_REFUSALS
from pseudo_brain.bridge_voice import VOICE_REFUSALS
from pseudo_brain.chat import REFUSALS, Chat
from pseudo_brain.hands import Hands, connect_hands
from pseudo_brain.providers import load_allowlist, provider_info
from pseudo_brain.suggestions import SUGGESTIONS

BOM = "﻿"
JOBS = ("ask", "provider", "new_session", "open_session", "transcribe") + bridge_sessions.JOBS  # one at a time
BUSY = "busy: Pseudo is still working on the last request; wait for it to finish"

Receive = Callable[[], Awaitable[bytes]]  # the next line from the face; b"" = the face closed the pipe
Write = Callable[[bytes], None]


def parse(raw: bytes) -> dict | None:
    """One line from the face -> a message, or None if it isn't a JSON object with a type."""
    try:
        message = json.loads(raw.decode("utf-8").replace(BOM, ""))
    except (UnicodeDecodeError, ValueError):
        return None
    return message if isinstance(message, dict) and isinstance(message.get("type"), str) else None


class Bridge:
    """What the face talks to: the Chat, the pseudo_hands connection, and whether a job is running."""

    def __init__(self, write: Write) -> None:
        self.write = write
        self.secrets: list[str] = []  # every key in use; Chat adds them
        self.chat: Chat | None = None
        self.hands: Hands | None = None
        self.busy = False
        self.tasks: TaskGroup | None = None  # where background work runs (M26: speaking an answer)
        self.speak_answers = True  # M26, D24: on by default; the face's switch turns it off
        self.warm = None  # M32: the warm sessions (bridge_warm.running sets it); off until the face says on

    def send(self, message_type: str, **fields) -> None:
        """One protocol line. ASCII-only JSON, so no pipe encoding can garble it; keys hidden."""
        line = json.dumps({"type": message_type, **fields}, ensure_ascii=True, default=str)
        for secret in self.secrets:
            line = line.replace(secret, "<hidden>")
        self.write(line.encode("ascii") + b"\n")

    def event(self, kind: str, data: dict) -> None:
        """The loop's on_event: every event goes to the face as it happens."""
        self.send("event", kind=kind, data=data)
        if kind == "answer":
            bridge_voice.on_answer(self, data)  # M26: spoken in the background, if speaking is on

    def session_info(self) -> dict:
        session = self.chat.session
        return {"name": session.started, "provider": session.provider, "title": session.title,
                "messages": session.transcript()}

    async def handle(self, raw: bytes, tasks: TaskGroup) -> bool:
        """One line from the face. Returns False when it's time to quit."""
        if not raw:  # the face closed the pipe: it's gone, so stop
            return False
        if not raw.strip():
            return True
        message = parse(raw)
        kind = message["type"] if message else None
        if kind == "quit":
            return False
        if kind in bridge_sessions.READS:
            bridge_sessions.read(self, message)
        elif kind in bridge_sees.IDLE_READS:  # (M42) awaited here, so a job sent right after waits for it
            await bridge_sees.read(self, message, BUSY)
        elif kind == "speak_answers":
            bridge_voice.set_speaking(self, message)
        elif kind == "warm_sessions":
            bridge_warm.set_warm(self, message)
        elif kind not in JOBS:
            self.send("refused", reason="not a message the brain understands")
        elif self.busy:
            self.send("refused", reason=BUSY)
        else:
            self.busy = True  # set NOW, so a second job right behind this one is refused
            tasks.start_soon(self.job, kind, message)
        return True

    async def job(self, kind: str, message: dict) -> None:
        """Run one job. It ends with turn_done, switched, session, renamed, deleted or refused; then busy is cleared."""
        try:
            if kind == "ask":
                await self.ask(message.get("text"))
            elif kind == "provider":
                if await self.chat.switch(str(message.get("id", ""))):
                    self.send("switched", provider=self.chat.provider.id, session=self.session_info())
                else:
                    self.send("refused", reason=f"already using {self.chat.provider.id}")
            elif kind == "transcribe":
                await bridge_voice.transcribe_job(self, message)
            elif kind == "open_session":
                await self.chat.open_session(message.get("name"))
                self.send("session", **self.session_info())
            elif kind in bridge_sessions.JOBS:
                await bridge_sessions.job(self, kind, message)
            else:
                self.chat.new_session()
                self.send("session", **self.session_info())
        except REFUSALS + VOICE_REFUSALS + SESSION_REFUSALS as refusal:  # nothing changed; the reason says why
            self.send("refused", reason=str(refusal))
        finally:
            self.busy = False

    async def ask(self, text) -> None:
        text = text.replace(BOM, "").strip() if isinstance(text, str) else ""
        if not text:
            self.send("refused", reason="there is no question to send")
        elif text.startswith("/"):
            self.send("refused", reason="that looks like a command, so nothing was sent; the face uses buttons")
        else:
            await bridge_sees.look(self)  # (M42) the chip shows what this question will read
            result = await self.chat.ask(text, self.hands)
            self.send("turn_done", ok=result.ok)


async def serve(receive: Receive, write: Write) -> int:
    """Run until the face says quit or closes the pipe. Returns the exit code."""
    bridge = Bridge(write)
    try:
        try:
            bridge.chat = Chat(load_allowlist(), bridge.event, bridge.secrets, load_routing())
            await bridge.chat.start()
        except REFUSALS as refusal:  # a bad allowlist, a missing key, an unreachable provider
            bridge.send("refused", reason=f"can't start: {refusal}")
            return 1
        async with connect_hands() as hands, anyio.create_task_group() as tasks, bridge_warm.running(bridge, tasks):
            bridge.hands, bridge.tasks = hands, tasks
            bridge.send("ready", providers=[provider_info(p) for p in bridge.chat.allowlist.providers.values()],
                        provider=bridge.chat.provider.id, session=bridge.session_info(), tools=hands.names,
                        hands_pid=hands.pid, action_brain=action_brain_info(bridge.chat.routing),
                        suggestions=list(SUGGESTIONS))  # (M40) the empty chat's one-click questions
            while await bridge.handle(await receive(), tasks):
                pass
            tasks.cancel_scope.cancel()  # quitting: a question still running is stopped, not waited for
    finally:
        if bridge.chat:
            bridge.chat.close()  # stop every server Pseudo started (private mode's Ollama)
    return 0


def main() -> int:
    protocol = sys.stdout.buffer  # the pipe to the face: from here on, protocol lines only
    sys.stdout = sys.stderr  # a print() anywhere now goes to the log, never into the protocol
    stdin = sys.stdin.buffer

    async def receive() -> bytes:
        return await anyio.to_thread.run_sync(stdin.readline, abandon_on_cancel=True)

    def write(data: bytes) -> None:
        protocol.write(data)
        protocol.flush()

    return anyio.run(serve, receive, write)


if __name__ == "__main__":
    sys.exit(main())
