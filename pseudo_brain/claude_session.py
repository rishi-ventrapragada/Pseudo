"""M32: one WARM Claude Code session (D26): a process that stays open and answers several action requests.

What it demonstrates: a long-lived child process spoken to over a pipe, the way the face speaks to
pseudo_brain (M18) and pseudo_brain to pseudo_hands (M14). A launch (claude_code.py) starts Claude
Code, asks one question and stops it: about 20 s to the popup, most of it start-up. Here the process
is started once and each request is written to its stdin as ONE JSON line (--input-format
stream-json), so the start-up is paid once: 10.4 s to the popup in M31.

What stays exactly as in a launch (the same functions, from claude_code.py):
  - the command line: only Pseudo's tools, Pseudo's system prompt, the model, nothing saved to disk;
  - the check of each request's init line (Claude Code prints one per request): exactly those tools,
    no API key, the model asked for;
  - at most MAX_ITERATIONS tool calls and timeout_seconds per request.
What is new, and why:
  - A request is JSON, so a question that starts with "--help", or holds a quote or a line break, is
    still one line of data: it can't be read as an option, or as a second request.
  - The session REMEMBERS. Claude Code sends every earlier request and read again with each new one,
    which is why warm_sessions.py restarts it (M31: the 6th request's input was 2.83 times the 1st's).
  - Memories never come here: the system prompt is fixed when the session starts, and a memory
    belongs to one question only (M24).
  - Stopping: closing its input makes Claude Code and its pseudo_hands end by themselves (0.4 s in
    M32's step 0). Whatever is left after STOP_WAIT_SECONDS is killed: only processes THIS session
    started (claude_process.Family).
This file holds no rules about WHEN to use, restart or stop a session: those are in warm_sessions.py.
It never runs the billing check either: that is the caller's job, before open_session and before ask.
"""

import json

import anyio
from anyio.streams.buffered import BufferedByteReceiveStream

from pseudo_brain import claude_billing
from pseudo_brain.action_brain import ActionBrain
from pseudo_brain.claude_code import command_line, follow, open_claude, report_sending, too_slow, write_config
from pseudo_brain.claude_process import Family
from pseudo_brain.loop import SYSTEM_PROMPT, EventSink, TurnResult, fail

STOP_WAIT_SECONDS = 2.5  # closing its input ended a session in 0.4 s (M32 step 0); after this, what is left is killed
CLOSED = (anyio.BrokenResourceError, anyio.ClosedResourceError, OSError)  # writing to a process that has gone


class WarmSession:
    """One open Claude Code process. ask() sends one request and reads until its result line."""

    def __init__(self, brain: ActionBrain, process) -> None:
        self.brain, self.process = brain, process
        self.lines = BufferedByteReceiveStream(process.stdout)  # ONE reader for the session's whole life
        self.family = Family(process.pid)

    @property
    def alive(self) -> bool:
        return self.process.returncode is None

    def ram_mb(self) -> float:
        """The memory the session holds right now: Claude Code plus its pseudo_hands."""
        return self.family.ram_mb()

    async def ask(self, text: str, on_event: EventSink) -> TurnResult:
        """One request. ok=False means there is no answer, and the caller must stop this session:
        Claude Code may still be working on the request, and nobody is reading its output any more."""
        result = TurnResult()
        report_sending(self.brain, on_event, len(SYSTEM_PROMPT) + len(text))
        line = {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": text}]}}
        try:
            with anyio.fail_after(self.brain.timeout_seconds):
                await self.process.stdin.send(json.dumps(line).encode("ascii") + b"\n")  # json.dumps escapes line breaks
                return await follow(self.lines, self.process.pid, self.brain, result, on_event)
        except TimeoutError:
            return too_slow(self.brain, result, on_event)
        except CLOSED:
            return fail(result, f"{self.brain.name}'s session had already ended", on_event)

    async def stop(self, now: bool = False) -> int:
        """End the session and its whole process tree. Returns how many of its processes are STILL running (0 = freed).

        now=True skips the polite wait: for a request that went wrong, when Claude Code may still be working."""
        with anyio.CancelScope(shield=True):  # also while Pseudo is quitting: never leave it running
            self.family.look()
            try:
                await self.process.stdin.aclose()  # its input ends, so Claude Code ends, so its pseudo_hands ends
            except CLOSED:
                pass
            left = await anyio.to_thread.run_sync(self.family.stop, 0.0 if now else STOP_WAIT_SECONDS)
            await self.process.aclose()
            return left


async def open_session(brain: ActionBrain) -> WarmSession:
    """Start a warm session. Raises OSError if Claude Code can't be started.

    It is open at once: a request written before its pseudo_hands has loaded simply waits (M32 step 0:
    answered 2 of 2 times, with the right tools)."""
    command = command_line(claude_billing.program(brain), brain, write_config(brain), SYSTEM_PROMPT, warm=True)
    return WarmSession(brain, await open_claude(command))
