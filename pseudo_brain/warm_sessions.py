"""M32: WHEN Pseudo uses, restarts and stops its warm Claude Code session (D26).

What it demonstrates: a POLICY kept apart from the mechanism. claude_session.py can keep a Claude Code
open and stop it; this file decides when. Every number here was measured in M31, not chosen.

The rules, for one action request (chat.py sends every one of them here when the face is in use):
  1. The billing check runs before EVERY request and before EVERY session start (D26). Not clean:
     nothing is sent, and an open session is stopped.
  2. The open session answers the request only if warm sessions are on, one is open and alive, it
     serves THIS conversation, and the request brings no memories. Otherwise the request gets a LAUNCH
     of its own, exactly as in M30, and its steps say why.
  3. After an answered launch, if warm sessions are on and none is open, one is opened for the NEXT
     requests. So at most one Claude Code is ever starting, and it never slows the request you wait for.
  4. After a request answered by the session: if it was the 6th, or its input was at least 3 times
     the session's first request's, the session is stopped and a new one started (M31: the 6th
     reached 2.83 times, so one extra tool call would cross 3).
  5. A request that fails inside the session stops the session, and is NOT asked again: an action you
     approved may already have happened.
And between requests (tick, every few seconds, from bridge_warm.py):
  6. A session idle for 10 minutes is stopped, which frees its 310 to 440 MB (D20).
  7. The face's switch: off stops the session at once, or as soon as a running request ends.
Warm sessions are OFF until the face says on, so the terminal keeps a launch per request.
Like the loop, this never prints: steps go to on_event, and the session's state to on_status.
"""

import time
from collections.abc import Callable

import anyio

from pseudo_brain.action_brain import ActionBrain
from pseudo_brain.claude_code import billing_check, launch, not_sent
from pseudo_brain.claude_session import WarmSession, open_session
from pseudo_brain.loop import EventSink, TurnResult

MAX_REQUESTS = 6  # M31: a session restarted every 6 requests passed all five criteria
INPUT_TIMES = 3.0  # M31's W-T: no request's input over 3 times its session's first
IDLE_SECONDS = 600.0  # 10 idle minutes, then the laptop gets the memory back

Status = Callable[[dict], None]  # on_status(state): numbers and names only, for the face


def restart_reason(asked: int, first_input: int, last_input: int) -> str:
    """Why the session must be restarted after this request; '' if it can go on."""
    if first_input and last_input >= INPUT_TIMES * first_input:
        return (f"this request's input was {last_input / first_input:.2f} times the session's first "
                f"(limit {INPUT_TIMES:g})")
    if asked >= MAX_REQUESTS:
        return f"it has answered {MAX_REQUESTS} requests"
    return ""


class WarmSessions:
    """The one warm session Pseudo may hold, and the rules above."""

    def __init__(self, on_status: Status, clock: Callable[[], float] = time.monotonic) -> None:
        self.on_status, self.clock = on_status, clock
        self.on = False  # off until the face says on
        self.session: WarmSession | None = None
        self.asked = 0  # requests the open session has answered
        self.first_input = 0  # the input of its first request: what the 3-times rule compares with
        self.conversation = ""  # the Pseudo session it serves
        self.used = 0.0  # when it was opened or last answered: the idle clock
        self.ram: float | None = None  # its memory in MB, as last measured by tick()
        self.note = ""  # the last thing that happened to a session, in plain words
        self.lock = anyio.Lock()  # one thing at a time: a request, a stop, the switch

    def status(self) -> dict:
        is_open = self.session is not None and self.session.alive
        return {"on": self.on, "open": is_open, "ram_mb": self.ram if is_open else None, "asked": self.asked,
                "of": MAX_REQUESTS, "idle_minutes": round(IDLE_SECONDS / 60), "note": self.note}

    def report(self) -> None:
        self.on_status(self.status())

    async def ask(self, brain: ActionBrain, text: str, on_event: EventSink, memories: list[str] = (),
                  intro: str = "", conversation: str = "") -> TurnResult:
        """One action request: through the open session, or a launch. ok=False always means: no answer."""
        async with self.lock:
            try:
                clean, why = await billing_check(brain, on_event)  # rule 1
                if not clean:
                    await self.stop("the billing check wasn't clean")
                    return not_sent(brain, why, on_event)
                why_launch = self.why_launch(list(memories), conversation)
                if not why_launch:
                    return await self.ask_session(brain, text, on_event)
                if self.session is not None and (not self.session.alive or conversation != self.conversation):
                    await self.stop(why_launch)  # it can't answer this conversation; a new one opens below
                on_event("launch", {"why": why_launch})
                result = await launch(brain, text, on_event, memories, intro)
                if result.ok and self.on and self.session is None:  # rule 3
                    await self.open(brain, on_event, conversation)
                return result
            finally:
                self.report()

    def why_launch(self, memories: list[str], conversation: str) -> str:
        """'' if the open session can answer this request (rule 2); else why it gets a launch."""
        if not self.on:
            return "warm sessions are off"
        if self.session is None:
            return "no warm session is open"
        if not self.session.alive:
            return "the warm session had ended"
        if conversation != self.conversation:
            return "the open session belongs to another conversation"
        return "this request brings memories, which never enter a warm session" if memories else ""

    async def ask_session(self, brain: ActionBrain, text: str, on_event: EventSink) -> TurnResult:
        number, result = self.asked + 1, None
        on_event("warm", {"request": number, "of": MAX_REQUESTS})
        try:
            result = await self.session.ask(text, on_event)
        finally:  # failed, timed out, or Pseudo is quitting: Claude Code may still be working on it (rule 5)
            if result is None or not result.ok:
                await self.stop("a request failed inside it", now=True)
        if not result.ok:
            return result
        self.asked, self.used = number, self.clock()
        self.first_input = self.first_input or result.tokens_in
        reason = restart_reason(self.asked, self.first_input, result.tokens_in)
        if reason:  # rule 4
            on_event("warm_restart", {"why": reason})
            conversation = self.conversation
            await self.stop(f"restarted: {reason}")
            await self.open(brain, on_event, conversation)
        return result

    async def open(self, brain: ActionBrain, on_event: EventSink, conversation: str) -> None:
        """Start a session for the next requests, after its own billing check (rule 1)."""
        clean, _why = await billing_check(brain, on_event)
        problem = "" if clean else "the billing check wasn't clean"
        if clean:
            try:
                self.session = await open_session(brain)
            except OSError as error:
                problem = f"{brain.name} couldn't be started ({type(error).__name__})"
        if problem:
            self.note = f"not opened: {problem}"
        else:
            self.asked, self.first_input, self.ram = 0, 0, None
            self.conversation, self.used, self.note = conversation, self.clock(), ""
        on_event("warm_opened", {"opened": not problem, "why": problem, "of": MAX_REQUESTS})

    async def stop(self, why: str, now: bool = False) -> None:
        """Stop the open session, if there is one, and note why. Safe to call twice."""
        session, self.session = self.session, None
        if session is None:
            return
        self.asked, self.first_input, self.ram = 0, 0, None
        left = await session.stop(now)
        self.note = f"stopped: {why}" + (f" ({left} of its processes would not end)" if left else "")

    async def end(self, why: str) -> None:
        """Stop the session from outside a request (chat.py: the provider was switched)."""
        async with self.lock:
            await self.stop(why)
        self.report()

    async def set_on(self, on: bool) -> None:
        """The face's switch (rule 7). It counts at once; a running request is allowed to finish first."""
        self.on = on
        self.report()
        if not on:
            async with self.lock:
                if not self.on:  # still off now that the request has ended
                    await self.stop("warm sessions were turned off")
            self.report()

    async def tick(self) -> None:
        """Between requests: stop an idle session (rule 6), notice one that ended, measure, tell the face."""
        if self.session is not None and not self.lock.locked():  # locked: a request is running, so it isn't idle
            async with self.lock:
                if self.session is not None and not self.session.alive:
                    await self.stop("it had ended by itself")
                elif self.session is not None and self.clock() - self.used >= IDLE_SECONDS:
                    await self.stop(f"idle for {IDLE_SECONDS / 60:.0f} minutes")
        session = self.session
        if session is not None and session.alive:  # walking the process tree takes a moment: off the event loop
            self.ram = await anyio.to_thread.run_sync(session.ram_mb)
        self.report()

    async def close(self) -> None:
        """Pseudo is quitting: nothing may be left running."""
        self.on = False
        await self.stop("Pseudo was closed")
