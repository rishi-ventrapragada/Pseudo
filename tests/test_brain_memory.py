"""Tests for M24: how pseudo_brain uses memory (chat.py, hands.py, session.py, loop.py, terminal.py).

The REAL pseudo_hands server runs in memory (no subprocess) with a temporary vault, a FakeModel
plays Groq, and popup_yes / popup_no play you at the approval popup. Every task is fake.
"""

from pathlib import Path

import pytest

from brain_fakes import FAKE_CLOUD, FAKE_HANDS, FakeModel, reply, unreachable
from pseudo_brain import chat as chat_module
from pseudo_brain import session as session_module
from pseudo_brain.chat import Chat
from pseudo_brain.hands import MEMORY_TOOLS, connect_hands
from pseudo_brain.providers import Allowlist
from pseudo_brain.session import Session, TooLarge
from pseudo_brain.terminal import format_event
from pseudo_hands.core import memory_search, redactor
from pseudo_hands.mcp_server import server

TASK = "My Vercel build broke, Rahul Verma said to call +91 98765 43210"
ANSWER = "Add the NEXT_PUBLIC_API_URL variable in the Vercel project settings, then redeploy."


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict:
    """A Chat on a fake Groq; world["models"] holds every FakeModel it was given, newest last."""
    terms = tmp_path / "redaction_terms.txt"
    terms.write_text("# no terms\n", encoding="utf-8")
    monkeypatch.setattr(redactor, "TERMS_FILE", terms)
    monkeypatch.setattr(session_module, "SESSIONS_DIR", tmp_path / "sessions")
    world: dict = {"events": [], "replies": [reply(ANSWER)], "models": []}

    async def fake_connect(provider, servers, on_event):
        world["models"].append(FakeModel(*world["replies"], provider=provider))
        return world["models"][-1]
    monkeypatch.setattr(chat_module, "connect_provider", fake_connect)
    world["chat"] = Chat(Allowlist({"groq": FAKE_CLOUD}, "groq"), lambda k, d: world["events"].append((k, d)), [])
    return world


def kinds(world: dict) -> list[str]:
    return [kind for kind, _ in world["events"]]


@pytest.mark.anyio
async def test_the_model_never_sees_or_calls_the_memory_tools() -> None:
    async with connect_hands(server) as hands:
        assert hands.has_memory and not set(MEMORY_TOOLS) & set(hands.names)
        assert not set(MEMORY_TOOLS) & {schema["function"]["name"] for schema in hands.schemas}
        text, is_error = await hands.call("save_memory", '{"question": "x", "answer": "y"}')
    assert is_error and "no such tool" in text


@pytest.mark.anyio
async def test_an_approved_answer_is_saved_and_found_again_in_a_new_session(world, popup_yes, temp_vault) -> None:
    chat = world["chat"]
    await chat.start()
    async with connect_hands(server) as hands:
        assert (await chat.ask(TASK, hands)).ok
        (note,) = temp_vault.iterdir()
        assert "98765" not in note.read_text(encoding="utf-8") and "provider: groq" in note.read_text(encoding="utf-8")
        chat.new_session()
        await chat.ask("how did I fix the vercel build", hands)
    request = world["models"][-1].requests[-1]
    memories = request["messages"][1]
    assert memories["role"] == "system" and memories["content"].startswith(memory_search.INTRO)
    assert "NEXT_PUBLIC_API_URL" in memories["content"] and "98765" not in memories["content"]
    one_memory = memories["content"].split("\n", 1)[1]  # the intro, a line break, then the memory
    assert ("memories", {"count": 1, "chars": len(one_memory), "note": ""}) in world["events"]
    saved = (Path(session_module.SESSIONS_DIR) / f"{chat.session.started}.json").read_text(encoding="utf-8")
    assert memory_search.INTRO not in saved and not any(memory_search.INTRO in str(t) for t in chat.session.turns)


@pytest.mark.anyio
async def test_the_save_comes_after_the_answer_as_pseudos_own_tool_call(world, popup_yes) -> None:
    await world["chat"].start()
    async with connect_hands(server) as hands:
        await world["chat"].ask(TASK, hands)
    order = kinds(world)
    assert order[order.index("answer"):] == ["answer", "tool_call", "tool_result", "memory_saved"]
    assert world["events"][order.index("tool_call")][1] == {"name": "save_memory", "arguments": "{}", "by": "pseudo"}
    assert len(popup_yes.previews) == 1


@pytest.mark.anyio
async def test_a_denied_save_writes_nothing_and_says_so(world, popup_no, temp_vault) -> None:
    await world["chat"].start()
    async with connect_hands(server) as hands:
        assert (await world["chat"].ask(TASK, hands)).ok
    assert kinds(world)[-1] == "memory_not_saved" and not temp_vault.exists()


@pytest.mark.anyio
async def test_a_failed_turn_is_never_offered_to_memory(world, popup_yes, temp_vault) -> None:
    world["replies"] = [unreachable()]
    await world["chat"].start()
    async with connect_hands(server) as hands:
        assert not (await world["chat"].ask(TASK, hands)).ok
    assert popup_yes.previews == [] and "memory_saved" not in kinds(world) and not temp_vault.exists()


@pytest.mark.anyio
async def test_a_broken_memory_search_only_means_no_memories(world, popup_no, monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(memory_search, "BACKGROUND_FILE", tmp_path / "missing.txt")
    await world["chat"].start()
    async with connect_hands(server) as hands:
        assert (await world["chat"].ask("how did I fix the vercel build", hands)).ok
    assert world["events"][0][0] == "memories" and world["events"][0][1]["count"] == 0
    assert len(world["models"][-1].requests[0]["messages"]) == 2  # system prompt + question: nothing extra


@pytest.mark.anyio
async def test_hands_without_memory_tools_work_as_before(world, popup_yes) -> None:
    await world["chat"].start()
    async with connect_hands(FAKE_HANDS) as hands:
        assert not hands.has_memory and (await world["chat"].ask(TASK, hands)).ok
    assert "memories" not in kinds(world) and popup_yes.previews == []


def test_over_budget_old_turns_go_first_then_memories_then_the_turn_fails() -> None:
    session = Session(turns=[[{"role": "user", "content": "old " * 200}], [{"role": "user", "content": "now"}]])
    memories = ["- 2026-09-01: first " + "x" * 300, "- 2026-09-02: second " + "y" * 300]
    _, _, dropped, used = session.messages_for_request("system", [], 250, memories, "intro")
    assert (dropped, used) == (1, 2)
    _, _, dropped, used = session.messages_for_request("system", [], 120, memories, "intro")
    assert (dropped, used) == (1, 1)  # the weakest memory went, the best one stayed
    with pytest.raises(TooLarge):
        session.messages_for_request("system", [], 5, memories, "intro")


def test_the_terminal_words_every_memory_event() -> None:
    assert format_event("memories", {"count": 2, "chars": 500, "note": ""}) == (
        "--- MEMORY: 2 past task(s) added to this question (500 chars, redacted) ---")
    assert "none added (no past task" in format_event("memories", {"count": 0, "chars": 0,
                                                                   "note": "no past task is relevant enough"})
    assert format_event("tool_call", {"name": "save_memory", "arguments": "{}", "by": "pseudo"}).startswith(
        "--- SAVING TO MEMORY: the approval popup asks you first")
    assert format_event("tool_result", {"name": "save_memory", "chars": 0, "is_error": False, "by": "pseudo"}) is None
    assert format_event("memory_saved", {"note": "2026-10-02-120000-001.md"}).endswith("as 2026-10-02-120000-001.md ---")
    assert format_event("memory_not_saved", {"reason": "you didn't approve it"}) == (
        "--- MEMORY: not saved (you didn't approve it) ---")
