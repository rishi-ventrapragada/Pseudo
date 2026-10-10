"""M32: the warm session's rules, part 2 (moved here from test_brain_warm_sessions.py in M39, unchanged,
to keep each file under 200 lines): which requests a session serves, and how it stops.

Claude Code is FAKE, the clock is fake, and the billing check is replaced and counted. Every test ends by
checking that none of the fake's processes is left running (the `sessions` helper does that).
"""

import anyio
import pytest
from claude_fakes import brain, fakes_running, kinds, recorded
from test_brain_warm_sessions import LAUNCH, OPENED, WARM, ask, sessions, why, world  # noqa: F401 - world is a fixture

from pseudo_brain.loop import SYSTEM_PROMPT
from pseudo_brain.warm_sessions import WarmSessions

@pytest.mark.anyio
async def test_a_request_that_brings_memories_gets_a_launch_and_the_session_never_sees_them(world: dict) -> None:
    async with sessions(world) as warm:
        await ask(world, warm)
        await ask(world, warm, "first")
        session_pid = recorded(world)["pid"]
        result = await ask(world, warm, "with a memory", memories=("a fake memory",))
        assert result.ok and kinds(world) == LAUNCH  # a launch, and no second session is opened
        assert why(world, "launch") == "this request brings memories, which never enter a warm session"
        args = recorded(world)["args"]
        assert args[args.index("--system-prompt") + 1] == SYSTEM_PROMPT + "\n\nNotes:\na fake memory"
        await ask(world, warm, "second")
        assert recorded(world)["pid"] == session_pid and recorded(world)["questions"] == ["first", "second"]
        assert world["events"][1][1]["request"] == 2


@pytest.mark.anyio
async def test_a_session_serves_one_conversation(world: dict) -> None:
    async with sessions(world) as warm:
        await ask(world, warm)
        await ask(world, warm, "in the first conversation")
        old = recorded(world)["pid"]
        await ask(world, warm, "in another", conversation="c2")
        assert kinds(world) == LAUNCH + OPENED and why(world, "launch") == "the open session belongs to another conversation"
        await ask(world, warm, "again in the other", conversation="c2")
        assert kinds(world) == WARM and world["events"][1][1]["request"] == 1
        assert recorded(world)["pid"] != old and recorded(world)["questions"] == ["again in the other"]


@pytest.mark.anyio
async def test_a_request_that_fails_inside_the_session_stops_it_and_is_never_asked_again(
        world: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "dies")
    monkeypatch.setenv("FAKE_CLAUDE_AT", "2")
    async with sessions(world) as warm:
        await ask(world, warm)
        await ask(world, warm, "answered")
        result = await ask(world, warm, "fails")
        assert not result.ok and result.answer is None and kinds(world)[-1] == "failed" and "launch" not in kinds(world)
        assert warm.session is None and fakes_running() == [] and warm.note == "stopped: a request failed inside it"
        assert recorded(world)["questions"] == ["answered", "fails"]  # sent once, to the session only


@pytest.mark.anyio
async def test_switching_off_stops_the_session_and_requests_become_launches(world: dict) -> None:
    async with sessions(world) as warm:
        await ask(world, warm)
        assert warm.session.alive
        await warm.set_on(False)
        assert warm.session is None and fakes_running() == []
        assert world["statuses"][-1]["on"] is False and world["statuses"][-1]["note"] == "stopped: warm sessions were turned off"
        await ask(world, warm)
        assert kinds(world) == LAUNCH and why(world, "launch") == "warm sessions are off" and warm.session is None


@pytest.mark.anyio
async def test_switching_off_during_a_request_lets_it_finish_first(world: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "slow")
    monkeypatch.setenv("FAKE_CLAUDE_AT", "1")
    results = []

    async def slow_request(warm: WarmSessions) -> None:
        results.append(await warm.ask(brain(), "slow", world["on_event"], [], "", "c1"))

    async with sessions(world) as warm:
        await ask(world, warm)  # the launch is slow too; the session opens behind it
        async with anyio.create_task_group() as tasks:
            tasks.start_soon(slow_request, warm)
            await anyio.sleep(0.5)
            await warm.set_on(False)  # returns only once the running request has ended
            assert results and results[0].ok and results[0].answer == "Fake answer 1: not approved."
        assert warm.session is None and fakes_running() == []


@pytest.mark.anyio
async def test_a_session_that_ended_by_itself_is_noticed(world: dict) -> None:
    async with sessions(world) as warm:
        await ask(world, warm)
        for process in warm.session.family.left():
            process.kill()
        await warm.session.process.wait()
        await warm.tick()
        assert warm.session is None and warm.note == "stopped: it had ended by itself"
        await ask(world, warm)
        assert kinds(world) == LAUNCH + OPENED


@pytest.mark.anyio
async def test_quitting_during_a_request_leaves_nothing_running(world: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    async with sessions(world) as warm:
        await ask(world, warm)
        monkeypatch.setenv("FAKE_CLAUDE_MODE", "hang")  # read by the NEXT process: the session is already running
        await warm.stop("to start one that hangs")
        await warm.open(brain(), world["on_event"], "c1")
        async with anyio.create_task_group() as tasks:
            tasks.start_soon(warm.ask, brain(), "hangs", world["on_event"], [], "", "c1")
            await anyio.sleep(1.0)
            tasks.cancel_scope.cancel()  # what the bridge does when you quit
        assert warm.session is None and fakes_running() == []
