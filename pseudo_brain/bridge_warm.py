"""M32: warm sessions over the bridge. The face's switch comes in; the session's state goes out (D26).

What it demonstrates: the same split as voice (bridge_voice.py). bridge.py stays the router, the rules
live in warm_sessions.py, and this file only carries messages and keeps time.

Face -> brain:  warm_sessions {on}    the switch: keep a Claude Code session open (true) or not (false).
                                      NOT a job: it works while a question is running. The face sends
                                      its remembered choice to every brain it starts.
Brain -> face:  warm {on, open, ram_mb, asked, of, idle_minutes, note}
                                      whether a session is open, the memory it holds (MB), how many of its
                                      requests it has answered, and the last thing that happened to one.

Rules:
  - Warm sessions are off until the face says on (warm_sessions.py).
  - Every TICK_SECONDS the rules get a tick: an idle session is stopped, the open one is measured.
  - A state is sent only when it differs from the last one sent. With no session open nothing changes,
    so nothing is sent; while one is open its memory moves, so the face sees it every few seconds.
  - Leaving running() stops the session, however the bridge ends: quit, the face gone, an error.
  - The log (stderr) gets a line when the switch, the session or the note changes. Never a question.
"""

import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import anyio
from anyio.abc import TaskGroup

from pseudo_brain.warm_sessions import WarmSessions

TICK_SECONDS = 5.0


def log(line: str) -> None:
    print(f"warm: {line}", file=sys.stderr, flush=True)


class Reporter:
    """The rules' on_status: one `warm` line to the face per CHANGE of state."""

    def __init__(self, bridge) -> None:
        self.bridge, self.sent = bridge, None

    def __call__(self, state: dict) -> None:
        if state == self.sent:
            return
        before, self.sent = self.sent or {}, state
        self.bridge.send("warm", **state)
        if [state[key] for key in ("on", "open", "note")] != [before.get(key) for key in ("on", "open", "note")]:
            log(f"{'on' if state['on'] else 'off'}, {'a session is open' if state['open'] else 'none open'}"
                + (f" ({state['note']})" if state["note"] else ""))


@asynccontextmanager
async def running(bridge, tasks: TaskGroup) -> AsyncIterator[None]:
    """Give the bridge's chat its warm sessions for as long as the bridge serves; stop them on the way out."""
    warm = WarmSessions(Reporter(bridge))
    bridge.warm = bridge.chat.warm = warm
    tasks.start_soon(keep_time, warm)
    try:
        yield
    finally:
        with anyio.CancelScope(shield=True):  # the bridge is being cancelled: the session must still be stopped
            await warm.close()


async def keep_time(warm: WarmSessions) -> None:
    while True:
        await anyio.sleep(TICK_SECONDS)
        await warm.tick()


def set_warm(bridge, message: dict) -> None:
    """`warm_sessions {on}`: anything but a real true/false is ignored.

    It runs in the background: turning off waits for a running request to end, and the bridge must
    go on reading the face's messages (quit, above all) meanwhile."""
    if isinstance(message.get("on"), bool) and bridge.warm is not None and bridge.tasks is not None:
        bridge.tasks.start_soon(bridge.warm.set_on, message["on"])
