"""M30: routing in chat.py. Which brain gets a question, and whether the switch tool is offered.

Everything is FAKE: a scripted model plays Groq, a small in-memory server plays pseudo_hands, and
Claude Code is replaced by a function that records what it was asked. Nothing is launched.
"""

import json
from pathlib import Path

import pytest
from brain_fakes import FAKE_CLOUD, FAKE_HANDS, FAKE_LOCAL, FakeModel, reply

from pseudo_brain import chat as chat_module
from pseudo_brain import session as session_module
from pseudo_brain.action_brain import ActionBrain, Routing
from pseudo_brain.chat import Chat
from pseudo_brain.hands import connect_hands
from pseudo_brain.loop import TurnResult
from pseudo_brain.providers import Allowlist

BRAIN = ActionBrain("Fake Code", ("fake-claude",), "sonnet", ("read_active_window",), "FAKE_ACCOUNT_VAR", "fake note", 5.0)
ROUTING = Routing("focus_window", BRAIN)
ACTION = "Tick the fake reminders box."
QUESTION = "What does my active window say?"
SWITCH = "Switch to the fake notes window."


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict:
    world: dict = {"events": [], "models": [], "asked": [], "claude": TurnResult(ok=True, answer="Fake: ticked.",
                                                                                 model="claude-sonnet-fake")}
    monkeypatch.setattr(session_module, "SESSIONS_DIR", tmp_path / "sessions")

    async def fake_connect(provider, servers, on_event):
        world["models"].append(FakeModel(reply("a fake Groq answer"), provider=provider))
        return world["models"][-1]

    async def fake_claude(brain, text, on_event, memories=(), intro=""):
        world["asked"].append((brain, text))
        return world["claude"]
    monkeypatch.setattr(chat_module, "connect_provider", fake_connect)
    monkeypatch.setattr(chat_module, "ask_claude", fake_claude)
    return world


async def chat_on(world: dict, routing: Routing | None = ROUTING, provider: str = "groq") -> Chat:
    chat = Chat(Allowlist({"groq": FAKE_CLOUD, "local": FAKE_LOCAL}, "groq"),
                lambda kind, data: world["events"].append((kind, data)), [], routing)
    await chat.start(wanted=provider)
    return chat


def offered(world: dict) -> list[str]:
    """The tools in the last request the fake Groq model received."""
    return [tool["function"]["name"] for tool in world["models"][-1].requests[-1]["tools"]]


@pytest.mark.anyio
async def test_an_action_request_goes_to_claude_code_and_not_to_groq(world: dict) -> None:
    chat = await chat_on(world)
    async with connect_hands(FAKE_HANDS) as hands:
        result = await chat.ask(ACTION, hands)
    assert result.ok and world["asked"] == [(BRAIN, ACTION)] and world["models"][-1].requests == []
    assert ("routed", {"to": "claude-code", "name": "Fake Code", "model": "sonnet", "privacy": "fake note"}) in world["events"]


@pytest.mark.anyio
async def test_the_session_keeps_the_action_turn_labelled_with_who_answered(world: dict) -> None:
    chat = await chat_on(world)
    async with connect_hands(FAKE_HANDS) as hands:
        await chat.ask(ACTION, hands)
        await chat.ask(QUESTION, hands)
    saved = json.loads((session_module.SESSIONS_DIR / f"{chat.session.started}.json").read_text(encoding="utf-8"))
    assert [m.get("answered_by") for m in saved["messages"] if m["role"] == "assistant"] == [
        "claude-code · claude-sonnet-fake", "groq · big-model"]
    assert saved["provider"] == "groq"
    sent = world["models"][-1].requests[-1]["messages"]  # the next Groq question sees that question and answer
    assert {"role": "user", "content": ACTION} in sent and {"role": "assistant", "content": "Fake: ticked."} in sent


@pytest.mark.anyio
async def test_a_failed_action_request_is_never_retried_on_groq(world: dict) -> None:
    world["claude"] = TurnResult(ok=False, reason="billing check: NOT CLEAN")
    chat = await chat_on(world)
    async with connect_hands(FAKE_HANDS) as hands:
        result = await chat.ask(ACTION, hands)
    assert not result.ok and result.answer is None and world["models"][-1].requests == []
    assert chat.session.turns[-1] == [{"role": "user", "content": ACTION}]  # asked, never answered


@pytest.mark.anyio
async def test_a_plain_question_stays_on_groq_without_the_switch_tool(world: dict) -> None:
    chat = await chat_on(world)
    async with connect_hands(FAKE_HANDS) as hands:
        await chat.ask(QUESTION, hands)
        assert world["asked"] == [] and "focus_window" not in offered(world) and "read_active_window" in offered(world)
        await chat.ask(SWITCH, hands)
    assert world["asked"] == [] and "focus_window" in offered(world)


@pytest.mark.anyio
async def test_a_withheld_tool_cant_be_called_even_if_the_model_asks(world: dict) -> None:
    from pseudo_brain.hands import OfferedHands
    async with connect_hands(FAKE_HANDS) as hands:
        view = OfferedHands(hands, "focus_window")
        assert await view.call("focus_window", '{"window_id": "w1"}') == ("ERROR: no such tool: focus_window", True)
        text, is_error = await view.call("read_active_window", "{}")
    assert not is_error and "Fake notes" in text


@pytest.mark.anyio
async def test_private_mode_never_routes_to_the_cloud(world: dict) -> None:
    chat = await chat_on(world, provider="local")
    async with connect_hands(FAKE_HANDS) as hands:
        result = await chat.ask(ACTION, hands)
    assert result.ok and world["asked"] == [] and len(world["models"][-1].requests) == 1
    assert not any(kind == "routed" for kind, _data in world["events"])


@pytest.mark.anyio
async def test_without_routing_nothing_changes(world: dict) -> None:
    chat = await chat_on(world, routing=None)
    async with connect_hands(FAKE_HANDS) as hands:
        await chat.ask(ACTION, hands)
    assert world["asked"] == [] and "focus_window" in offered(world)


@pytest.mark.anyio
async def test_no_action_brain_still_applies_the_switch_rule(world: dict) -> None:
    chat = await chat_on(world, routing=Routing("focus_window", None))
    async with connect_hands(FAKE_HANDS) as hands:
        await chat.ask(ACTION, hands)
    assert world["asked"] == [] and "focus_window" not in offered(world)


def test_the_terminal_shows_the_route_and_the_billing_line() -> None:
    from pseudo_brain.terminal import format_event
    routed = format_event("routed", {"to": "claude-code", "name": "Fake Code", "model": "sonnet", "privacy": "fake note"})
    assert "ACTION REQUEST: going to Fake Code (sonnet)" in routed and "fake note" in routed
    assert format_event("billing", {"clean": True, "line": "billing check: CLEAN"}) == "--- billing check: CLEAN ---"
    assert format_event("hands_pid", {"pid": 123}) is None


def test_the_face_is_told_who_answers_action_requests() -> None:
    from pseudo_brain.bridge import action_brain_info
    assert action_brain_info(ROUTING) == {"id": "claude-code", "name": "Fake Code", "model": "sonnet", "privacy": "fake note"}
    assert action_brain_info(Routing("focus_window", None)) is None and action_brain_info(None) is None
