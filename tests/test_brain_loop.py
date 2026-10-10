"""Tests for M14: pseudo_brain's loop, model client and MCP client.

Everything here is FAKE (see brain_fakes.py): a scripted FakeModel plays Groq, and a
small in-memory MCP server plays pseudo_hands (the real MCP protocol, no subprocess).
No network, no real windows, and no real waiting (the waits fixture replaces it).
FakeModel's default provider has ONE model, so a 429 waits here as it did in M14;
M16's fallback between models is tested in test_brain_fallback.py.
"""

import dataclasses
import json

import openai
import pytest

from brain_fakes import FAKE_ONE, MARKER, FakeModel, ask, http_response, rate_limited, reply
from pseudo_brain import loop, model
from pseudo_brain.loop import MAX_ITERATIONS


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
    assert events[-1] == ("failed", {"reason": f"stopped after {MAX_ITERATIONS} model calls without an answer",
                                     "tokens_in": 100 * MAX_ITERATIONS, "tokens_out": 10 * MAX_ITERATIONS})  # (M42)


@pytest.mark.anyio
async def test_a_429_waits_as_long_as_asked_then_succeeds(waits: list) -> None:
    result, events, _ = await ask(FakeModel(rate_limited("2"), reply("Done.")))
    assert result.ok and waits == [2.0]
    assert ("rate_limited", {"seconds": 2.0, "wait": 1, "of": model.MAX_RATE_LIMIT_WAITS,
                             "provider": "Fake cloud", "model": "only-model"}) in events


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
    assert not result.ok and "bigger than Fake cloud's per-minute token limit" in result.reason and len(fake.requests) == 1


@pytest.mark.anyio
async def test_an_invalid_tool_call_400_asks_the_model_again() -> None:
    bad = openai.BadRequestError("bad tool call", response=http_response(400), body={"code": "tool_use_failed"})
    fake = FakeModel(bad, reply("OK."))
    result, events, _ = await ask(fake)
    assert result.ok and len(fake.requests) == 2 and ("model_retry", {"reason": "the model wrote an invalid tool call"}) in events


@pytest.mark.anyio
async def test_an_oversized_question_fails_before_any_model_call() -> None:
    fake = FakeModel(reply("never sent"), provider=dataclasses.replace(FAKE_ONE, max_prompt_tokens=100))
    result, _, _ = await ask(fake, "y" * 2000)
    assert not result.ok and "too large" in result.reason and fake.requests == []
