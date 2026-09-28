"""Tests for M14: pseudo_brain's loop, model client and MCP client.

Everything here is FAKE: a scripted FakeModel plays Groq, and a small in-memory
MCP server plays pseudo_hands (the real MCP protocol, no subprocess). No network,
no real windows, and no real waiting (model.wait is replaced).
"""

import json

import httpx2
import openai
import pytest
from mcp.server import MCPServer
from openai.types.chat import ChatCompletion

from pseudo_brain import loop, model
from pseudo_brain import session as session_module
from pseudo_brain.hands import connect_hands
from pseudo_brain.loop import MAX_ITERATIONS, run_turn
from pseudo_brain.session import Session

MARKER = "ZEBRA-7731"  # fake screen text: must never appear in an event


def fake_read_active_window() -> dict:
    return {"title": "Fake notes", "app": "notepad.exe", "content": f"Text: call [PERSON] about {MARKER}"}


def fake_focus_window(window_id: str) -> dict:
    return {"window_id": window_id, "status": "not approved"}


def fake_broken() -> dict:
    raise RuntimeError("fake failure")


FAKE_HANDS = MCPServer("fake_hands")
FAKE_HANDS.add_tool(fake_read_active_window, name="read_active_window", description="Read the fake window.")
FAKE_HANDS.add_tool(fake_focus_window, name="focus_window", description="Focus a fake window.")
FAKE_HANDS.add_tool(fake_broken, name="broken_tool", description="Always fails.")


def reply(content: str | None = None, tools: list = (), tokens: tuple = (100, 10)) -> ChatCompletion:
    """A fake Groq reply: plain text, or tool calls given as (name, arguments) pairs."""
    calls = [{"id": f"call_{i}", "type": "function", "function": {"name": n, "arguments": a}}
             for i, (n, a) in enumerate(tools)]
    return ChatCompletion.model_validate({
        "id": "fake", "object": "chat.completion", "created": 0, "model": "fake-model",
        "choices": [{"index": 0, "finish_reason": "tool_calls" if calls else "stop",
                     "message": {"role": "assistant", "content": content, "tool_calls": calls or None}}],
        "usage": {"prompt_tokens": tokens[0], "completion_tokens": tokens[1], "total_tokens": sum(tokens)}})


def http_response(status: int, headers: dict | None = None) -> httpx2.Response:
    return httpx2.Response(status, headers=headers or {}, request=httpx2.Request("POST", "https://fake.invalid/v1"))


def rate_limited(seconds: str = "2") -> openai.RateLimitError:
    return openai.RateLimitError("rate limited", response=http_response(429, {"retry-after": seconds}), body=None)


class FakeModel:
    """Plays Groq: returns the scripted replies in order (the last one repeats), records every request."""

    def __init__(self, *replies) -> None:
        self.replies, self.requests = list(replies), []

    async def complete(self, request: dict):
        self.requests.append(request)
        outcome = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome, {"x-ratelimit-remaining-tokens": "7000", "x-ratelimit-limit-tokens": "8000"}


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def waits(monkeypatch: pytest.MonkeyPatch) -> list:
    waited: list = []

    async def fake_wait(seconds: float) -> None:
        waited.append(seconds)
    monkeypatch.setattr(model, "wait", fake_wait)
    return waited


async def ask(fake_model: FakeModel, text: str = "What does my active window say?"):
    events: list = []
    session = Session()
    async with connect_hands(FAKE_HANDS) as hands:
        result = await run_turn(session, text, fake_model, hands, lambda kind, data: events.append((kind, data)))
    return result, events, session


# ---------- tools come from the server ----------

@pytest.mark.anyio
async def test_tools_are_discovered_from_the_server_and_the_prompt_comes_first() -> None:
    fake = FakeModel(reply("Hello."))
    result, _, _ = await ask(fake)
    tools = fake.requests[0]["tools"]
    assert [t["function"]["name"] for t in tools] == ["read_active_window", "focus_window", "broken_tool"]
    assert all(t["type"] == "function" and "parameters" in t["function"] for t in tools)
    assert fake.requests[0]["messages"][0] == {"role": "system", "content": loop.SYSTEM_PROMPT}
    assert result.ok and result.answer == "Hello."


@pytest.mark.anyio
async def test_a_tool_call_goes_over_mcp_and_its_result_reaches_the_model() -> None:
    fake = FakeModel(reply(tools=[("read_active_window", "{}")]), reply("It mentions [PERSON]."))
    result, events, _ = await ask(fake)
    tool_message = fake.requests[1]["messages"][-1]
    assert tool_message["role"] == "tool" and MARKER in tool_message["content"]
    assert result.ok and result.answer == "It mentions [PERSON]." and result.calls == 2
    assert [kind for kind, _ in events] == ["sending", "tokens", "tool_call", "tool_result",
                                             "sending", "tokens", "answer"]


@pytest.mark.anyio
async def test_an_action_result_reaches_the_model_unchanged() -> None:
    fake = FakeModel(reply(tools=[("focus_window", '{"window_id": "w3"}')]), reply("It was not approved."))
    await ask(fake)
    assert json.loads(fake.requests[1]["messages"][-1]["content"]) == {"window_id": "w3", "status": "not approved"}


@pytest.mark.anyio
async def test_unknown_tools_bad_arguments_and_tool_errors_go_back_as_errors() -> None:
    fake = FakeModel(reply(tools=[("delete_everything", "{}"), ("broken_tool", "{}"), ("focus_window", "not json")]),
                     reply("Sorry, that didn't work."))
    result, events, _ = await ask(fake)
    tool_texts = [m["content"] for m in fake.requests[1]["messages"] if m["role"] == "tool"]
    assert all(text.startswith("ERROR:") for text in tool_texts) and "no such tool" in tool_texts[0]
    assert [data["is_error"] for kind, data in events if kind == "tool_result"] == [True, True, True]
    assert result.ok


@pytest.mark.anyio
async def test_no_event_carries_tool_result_text() -> None:
    fake = FakeModel(reply(tools=[("read_active_window", "{}")]), reply("A summary."))
    _, events, _ = await ask(fake)
    assert MARKER not in json.dumps(events)


# ---------- honest failures ----------

@pytest.mark.anyio
async def test_a_model_that_never_answers_stops_at_the_cap_without_an_answer() -> None:
    fake = FakeModel(reply(tools=[("read_active_window", "{}")]))
    result, events, _ = await ask(fake)
    assert not result.ok and result.answer is None and len(fake.requests) == MAX_ITERATIONS
    assert events[-1] == ("failed", {"reason": f"stopped after {MAX_ITERATIONS} model calls without an answer"})


@pytest.mark.anyio
async def test_a_429_waits_as_long_as_asked_then_succeeds(waits: list) -> None:
    result, events, _ = await ask(FakeModel(rate_limited("2"), reply("Done.")))
    assert result.ok and waits == [2.0]
    assert ("rate_limited", {"seconds": 2.0, "wait": 1, "of": model.MAX_RATE_LIMIT_WAITS}) in events


@pytest.mark.anyio
async def test_repeated_429s_fail_clearly_and_leave_no_answer(waits: list) -> None:
    result, _, session = await ask(FakeModel(rate_limited("2")))
    assert not result.ok and result.answer is None and "rate limiting (429)" in result.reason
    assert len(waits) == model.MAX_RATE_LIMIT_WAITS
    assert not any(m["role"] == "assistant" for m in session.turns[-1])


@pytest.mark.anyio
async def test_a_429_asking_for_too_long_a_wait_fails_without_waiting(waits: list) -> None:
    result, _, _ = await ask(FakeModel(rate_limited("120")))
    assert not result.ok and waits == []


@pytest.mark.anyio
async def test_a_413_fails_at_once() -> None:
    fake = FakeModel(openai.APIStatusError("too large", response=http_response(413), body=None))
    result, _, _ = await ask(fake)
    assert not result.ok and "bigger than Groq's per-minute token limit" in result.reason and len(fake.requests) == 1


@pytest.mark.anyio
async def test_an_invalid_tool_call_400_asks_the_model_again() -> None:
    bad = openai.BadRequestError("bad tool call", response=http_response(400), body={"code": "tool_use_failed"})
    fake = FakeModel(bad, reply("OK."))
    result, events, _ = await ask(fake)
    assert result.ok and len(fake.requests) == 2 and ("model_retry", {"reason": "the model wrote an invalid tool call"}) in events


@pytest.mark.anyio
async def test_an_oversized_question_fails_before_any_model_call(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(session_module, "MAX_PROMPT_TOKENS", 100)
    fake = FakeModel(reply("never sent"))
    result, _, _ = await ask(fake, "y" * 2000)
    assert not result.ok and "too large" in result.reason and fake.requests == []
