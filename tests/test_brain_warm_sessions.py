"""M32: the warm session's rules (pseudo_brain/warm_sessions.py).

Claude Code is FAKE, the clock is fake, and the billing check is replaced and counted. What is real:
the fake's processes are started, written to, restarted and stopped, and every test ends by checking
that none of them is left running.
"""

from contextlib import asynccontextmanager
from pathlib import Path

import anyio
import pytest
from claude_fakes import ONE_REQUEST, brain, fake_world, fakes_running, kinds, recorded

from pseudo_brain import claude_billing
from pseudo_brain.loop import SYSTEM_PROMPT
from pseudo_brain.warm_sessions import IDLE_SECONDS, MAX_REQUESTS, WarmSessions, restart_reason

ACTION = "Tick the fake reminders box."
OPENED = ["billing", "warm_opened"]  # a session start: its own billing check, then the session
LAUNCH = ["billing", "launch", *ONE_REQUEST]
WARM = ["billing", "warm", *ONE_REQUEST]


class Clock:
    now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict:
    world = fake_world(monkeypatch, tmp_path)
    world.update(clock=Clock(), statuses=[])
    return world


@asynccontextmanager
async def sessions(world: dict, on: bool = True):
    warm = WarmSessions(world["statuses"].append, world["clock"])
    await warm.set_on(on)
    try:
        yield warm
    finally:
        await warm.close()
        assert fakes_running() == []  # whatever the test did, nothing is left running


async def ask(world: dict, warm: WarmSessions, text: str = ACTION, memories: tuple = (), conversation: str = "c1"):
    world["events"].clear()
    return await warm.ask(brain(), text, world["on_event"], list(memories), "Notes:", conversation)


def why(world: dict, kind: str) -> str:
    return next(data["why"] for event, data in world["events"] if event == kind)


@pytest.mark.anyio
async def test_off_until_the_face_says_on_so_every_request_is_a_launch(world: dict) -> None:
    warm = WarmSessions(world["statuses"].append, world["clock"])  # nobody said on (the terminal never does)
    assert (await ask(world, warm)).ok and kinds(world) == LAUNCH and why(world, "launch") == "warm sessions are off"
    assert warm.session is None and world["checks"] == 1 and "--max-turns" in recorded(world)["args"]
    assert fakes_running() == []


@pytest.mark.anyio
async def test_with_none_open_the_request_is_a_launch_and_a_session_opens_behind_it(world: dict) -> None:
    async with sessions(world) as warm:
        result = await ask(world, warm)
        assert result.ok and kinds(world) == LAUNCH + OPENED and why(world, "launch") == "no warm session is open"
        assert world["checks"] == 2  # one before the request, one before the session start
        assert warm.session.alive and warm.status()["open"] and warm.status()["asked"] == 0


@pytest.mark.anyio
async def test_the_next_requests_are_answered_by_that_one_session(world: dict) -> None:
    async with sessions(world) as warm:
        await ask(world, warm)
        first = await ask(world, warm, "first")
        assert first.ok and kinds(world) == WARM and world["events"][1] == ("warm", {"request": 1, "of": MAX_REQUESTS})
        pid = recorded(world)["pid"]
        second = await ask(world, warm, "second")
        assert second.answer == "Fake answer 2: not approved." and world["events"][1][1]["request"] == 2
        assert recorded(world)["pid"] == pid and recorded(world)["questions"] == ["first", "second"]
        assert world["checks"] == 4 and warm.status()["asked"] == 2  # launch, session start, and each request


@pytest.mark.anyio
async def test_the_sixth_request_restarts_the_session(world: dict) -> None:
    async with sessions(world) as warm:
        await ask(world, warm)
        for number in range(1, MAX_REQUESTS):
            await ask(world, warm, f"request {number}")
            assert kinds(world) == WARM
        old = recorded(world)["pid"]
        await ask(world, warm, "the sixth")
        assert kinds(world) == WARM + ["warm_restart", *OPENED]
        assert why(world, "warm_restart") == f"it has answered {MAX_REQUESTS} requests"
        assert world["checks"] == 2 + MAX_REQUESTS + 1  # ...and one more for the new session's start
        await ask(world, warm, "the seventh")
        assert world["events"][1] == ("warm", {"request": 1, "of": MAX_REQUESTS})
        assert recorded(world)["pid"] != old and recorded(world)["questions"] == ["the seventh"]


@pytest.mark.anyio
@pytest.mark.parametrize("third, restarts", [(21000, True), (20999, False)])
async def test_input_at_three_times_the_first_restarts_early(world: dict, monkeypatch: pytest.MonkeyPatch,
                                                             third: int, restarts: bool) -> None:
    monkeypatch.setenv("FAKE_CLAUDE_INPUTS", f"7000,9000,{third}")
    async with sessions(world) as warm:
        await ask(world, warm)
        await ask(world, warm)
        await ask(world, warm)
        assert kinds(world) == WARM
        result = await ask(world, warm)
        assert result.tokens_in == third and ("warm_restart" in kinds(world)) is restarts
        if restarts:
            assert why(world, "warm_restart") == "this request's input was 3.00 times the session's first (limit 3)"
        assert warm.status()["asked"] == (0 if restarts else 3)


@pytest.mark.anyio
async def test_an_idle_session_is_stopped_at_ten_minutes_and_not_before(world: dict) -> None:
    async with sessions(world) as warm:
        await ask(world, warm)
        await ask(world, warm)
        world["clock"].now += IDLE_SECONDS - 1
        await warm.tick()
        assert warm.session is not None and world["statuses"][-1]["ram_mb"] > 0  # still open, its memory measured
        world["clock"].now += 1
        await warm.tick()
        assert warm.session is None and fakes_running() == []
        assert world["statuses"][-1] == {"on": True, "open": False, "ram_mb": None, "asked": 0, "of": MAX_REQUESTS,
                                         "idle_minutes": 10, "note": "stopped: idle for 10 minutes"}
        await ask(world, warm)
        assert kinds(world) == LAUNCH + OPENED and why(world, "launch") == "no warm session is open"


@pytest.mark.anyio
async def test_a_billing_check_that_isnt_clean_sends_nothing_and_stops_the_session(world: dict) -> None:
    async with sessions(world) as warm:
        await ask(world, warm)
        await ask(world, warm, "sent")
        world["clean"] = False
        result = await ask(world, warm, "never sent")
        assert not result.ok and "NOT CLEAN" in result.reason and "Nothing was sent" in result.reason
        assert kinds(world) == ["billing", "failed"] and warm.session is None and fakes_running() == []
        assert recorded(world)["questions"] == ["sent"] and warm.note == "stopped: the billing check wasn't clean"


@pytest.mark.anyio
async def test_no_session_is_opened_when_the_check_before_its_start_isnt_clean(world: dict,
                                                                              monkeypatch: pytest.MonkeyPatch) -> None:
    answers = iter([(True, "billing check: CLEAN"), (False, "billing check: NOT CLEAN")])
    monkeypatch.setattr(claude_billing, "check", lambda _brain: next(answers))
    async with sessions(world) as warm:
        result = await ask(world, warm)
        assert result.ok and kinds(world) == LAUNCH + OPENED  # the launch itself was clean and answered
        assert world["events"][-1] == ("warm_opened", {"opened": False, "why": "the billing check wasn't clean",
                                                       "of": MAX_REQUESTS})
        assert warm.session is None and fakes_running() == []


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


def test_the_state_sent_to_the_face_holds_numbers_and_names_only(world: dict) -> None:
    warm = WarmSessions(world["statuses"].append, world["clock"])
    assert warm.status() == {"on": False, "open": False, "ram_mb": None, "asked": 0, "of": 6, "idle_minutes": 10, "note": ""}


@pytest.mark.parametrize("asked, first, last, reason", [
    (1, 7000, 7000, ""), (5, 7000, 20999, ""), (6, 7000, 9000, "it has answered 6 requests"),
    (2, 7000, 21000, "this request's input was 3.00 times the session's first (limit 3)"),
    (6, 7000, 23100, "this request's input was 3.30 times the session's first (limit 3)"),
    (3, 0, 50000, ""),  # no first request measured: only the count can restart it
])
def test_restart_reason(asked: int, first: int, last: int, reason: str) -> None:
    assert restart_reason(asked, first, last) == reason
