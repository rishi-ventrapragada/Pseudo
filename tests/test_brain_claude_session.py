"""M32: one warm Claude Code session (pseudo_brain/claude_session.py, claude_process.py).

Claude Code is FAKE (tests/fixtures/fake_claude.py in its warm mode). What is real: one child process
kept open, each request written to its stdin as a JSON line, its lines read back, and stopping it.
"""

import os
import time
from pathlib import Path

import psutil
import pytest
from claude_fakes import ONE_REQUEST, TOOLS, brain, fake_world, fakes_running, kinds, recorded

from pseudo_brain import claude_session
from pseudo_brain.claude_code import command_line
from pseudo_brain.claude_process import Family
from pseudo_brain.claude_session import STOP_WAIT_SECONDS, open_session
from pseudo_brain.loop import MAX_ITERATIONS, SYSTEM_PROMPT

FIRST, SECOND = "Tick the fake box.", "Press the fake button."
ODD = '--help; say "tick"\nthe fake box \\ {"type": "user"}'  # an option, a quote, a line break, JSON of its own


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict:
    return fake_world(monkeypatch, tmp_path)


@pytest.mark.anyio
async def test_one_process_answers_several_requests(world: dict) -> None:
    session = await open_session(brain())
    try:
        first = await session.ask(FIRST, world["on_event"])
        pid = recorded(world)["pid"]
        second = await session.ask(SECOND, world["on_event"])
    finally:
        left = await session.stop()
    assert first.ok and first.answer == "Fake answer 1: not approved." and first.model == "claude-sonnet-fake"
    assert second.ok and second.answer == "Fake answer 2: not approved."
    assert recorded(world)["questions"] == [FIRST, SECOND] and recorded(world)["pid"] == pid  # ONE process
    assert kinds(world) == ONE_REQUEST * 2  # every request has its own init check and names its pseudo_hands
    assert second.tools == ["read_active_window", "act_on_control"]
    assert (second.tokens_in, second.tokens_out, second.calls) == (8206, 200, 3)  # this request's, not a running total
    assert left == 0 and fakes_running() == []


@pytest.mark.anyio
async def test_it_is_started_like_a_launch_except_that_it_stays_open(world: dict) -> None:
    session = await open_session(brain())
    await session.ask(FIRST, world["on_event"])
    await session.stop()
    args = recorded(world)["args"]
    assert args[0] == "-p" and "--strict-mcp-config" in args and "--no-session-persistence" in args
    assert args[args.index("--tools") + 1] == ""  # no built-in tools
    assert args[args.index("--allowedTools") + 1:args.index("--system-prompt")] == ["mcp__pseudo_hands__" + t for t in TOOLS]
    assert args[args.index("--system-prompt") + 1] == SYSTEM_PROMPT  # Pseudo's prompt alone: never a memory
    assert args[args.index("--input-format") + 1] == "stream-json" and "--max-turns" not in args
    assert recorded(world)["env"] == ["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"]  # nothing that could outrank the login
    launch = command_line(["claude"], brain(), Path("hands.json"), SYSTEM_PROMPT)
    warm = command_line(["claude"], brain(), Path("hands.json"), SYSTEM_PROMPT, warm=True)
    assert set(launch) ^ set(warm) == {"--max-turns", str(MAX_ITERATIONS), "--input-format"}  # the only difference


@pytest.mark.anyio
async def test_a_question_is_one_line_of_data_whatever_it_holds(world: dict) -> None:
    session = await open_session(brain())
    try:
        first = await session.ask(ODD, world["on_event"])
        second = await session.ask(SECOND, world["on_event"])
    finally:
        await session.stop()
    assert first.ok and second.ok and recorded(world)["questions"] == [ODD, SECOND]
    assert ODD not in recorded(world)["args"]


@pytest.mark.anyio
@pytest.mark.parametrize("mode, reason", [
    ("extra_tool", "other tools than the ones in providers.toml"),
    ("api_key", "isn't using the subscription login"),
    ("other_model", "another model"),
    ("dies", "stopped without an answer"),
    ("max_turns", "ended without an answer"),
    ("too_many", f"stopped after {MAX_ITERATIONS} tool calls"),
])
async def test_a_later_request_that_goes_wrong_has_no_answer(world: dict, monkeypatch: pytest.MonkeyPatch,
                                                              mode: str, reason: str) -> None:
    monkeypatch.setenv("FAKE_CLAUDE_MODE", mode)
    monkeypatch.setenv("FAKE_CLAUDE_AT", "2")  # the session's FIRST request is fine: each one is checked again
    session = await open_session(brain())
    try:
        assert (await session.ask(FIRST, world["on_event"])).ok
        world["events"].clear()
        result = await session.ask(SECOND, world["on_event"])
    finally:
        left = await session.stop(now=True)
    assert not result.ok and result.answer is None and reason in result.reason
    assert kinds(world)[-1] == "failed" and "answer" not in kinds(world)
    if mode in ("extra_tool", "api_key", "other_model"):
        assert "tool_call" not in kinds(world)  # stopped before any tool ran
    assert left == 0 and fakes_running() == []


@pytest.mark.anyio
async def test_a_hung_request_times_out_and_nothing_is_left_running(world: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "hang")
    session = await open_session(brain(timeout=2.0))
    result = await session.ask(FIRST, world["on_event"])
    left = await session.stop(now=True)
    assert not result.ok and "didn't finish within 2 seconds" in result.reason
    assert left == 0 and fakes_running() == []


@pytest.mark.anyio
async def test_closing_its_input_ends_it_by_itself(world: dict) -> None:
    session = await open_session(brain())
    await session.ask(FIRST, world["on_event"])
    assert session.alive and session.ram_mb() > 0 and session.family.left() != []
    started = time.monotonic()
    left = await session.stop()
    assert left == 0 and not session.alive and time.monotonic() - started < STOP_WAIT_SECONDS  # no kill was needed
    assert session.family.left() == [] and session.ram_mb() == 0 and fakes_running() == []


@pytest.mark.anyio
async def test_a_session_that_wont_end_is_killed(world: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "stuck")  # it ignores its input being closed
    monkeypatch.setattr(claude_session, "STOP_WAIT_SECONDS", 0.5)
    session = await open_session(brain())
    await session.ask(FIRST, world["on_event"])
    assert await session.stop() == 0 and not session.alive and fakes_running() == []


@pytest.mark.anyio
async def test_a_session_that_has_ended_gives_no_answer(world: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "dies")
    session = await open_session(brain())
    assert not (await session.ask(FIRST, world["on_event"])).ok
    await session.process.wait()
    result = await session.ask(SECOND, world["on_event"])
    assert not session.alive and not result.ok and result.answer is None
    assert await session.stop() == 0


def test_a_family_never_counts_someone_elses_process_with_a_reused_pid() -> None:
    me = psutil.Process()
    family = Family(os.getpid())
    assert [p.pid for p in family.left()] == [me.pid]
    family.seen = {me.pid: me.create_time() - 100}  # the same pid, but a process that started at another time
    assert family.left() == []  # so it would never be killed


def test_a_family_whose_root_is_gone_holds_nothing() -> None:
    family = Family(2 ** 31 - 2)  # no such process
    assert family.look() == [] and family.ram_mb() == 0 and family.left() == [] and family.stop(0.0) == 0
