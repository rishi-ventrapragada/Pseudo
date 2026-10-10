"""Tests for M42: the look-at chip, the memory browser and the masked count, over the bridge (bridge_sees.py).

The REAL bridge runs on in-memory pipes with bridge_fakes' fake face. pseudo_hands is a fake that publishes
the brain-only tools and records every call; nothing reads a real window or vault.
"""

import anyio
import pytest
from brain_fakes import fake_read_active_window
from bridge_fakes import Face, run, world  # noqa: F401 - world is a pytest fixture
from mcp.server import MCPServer

from pseudo_brain import bridge
from pseudo_brain.hands import connect_hands
from pseudo_brain.masks import REDACTOR_LABELS, count_masks
from pseudo_hands.core import redactor
from pseudo_hands.core.looking_at import LookingAt
from pseudo_hands.core.memory import SaveResult
from pseudo_hands.core.memory_browse import MemoryList, MemoryNote
from pseudo_hands.core.memory_search import MemoryResult

NOTE = "2026-10-07-101500-123.md"
CALLS: list[tuple[str, str]] = []  # (tool, its name argument) for every brain-only call that ran


def fake_looking_at() -> LookingAt:
    CALLS.append(("looking_at", ""))
    return {"app": "Fake Notes", "private": False, "note": ""}


def fake_list_memories() -> MemoryList:
    CALLS.append(("list_memories", ""))
    return {"items": [{"name": NOTE, "date": "2026-10-07", "title": "Read the booking form"}], "note": ""}


def fake_open_memory(name: str) -> MemoryNote:
    CALLS.append(("open_memory", name))
    return {"name": name, "date": "2026-10-07", "title": "Read the booking form", "question": "Read the booking form",
            "answer": "Booked by [PERSON].", "note": ""}


def fake_search(question: str) -> MemoryResult:
    return {"intro": "Past tasks.", "memories": ["- 2026-10-07: Read the booking form\n  Answer: Booked by [PERSON]."],
            "note": ""}


def fake_save(question: str, answer: str, tools: list[str], provider: str, model: str, session: str) -> SaveResult:
    return {"status": "saved", "note": NOTE, "reason": ""}


SEEING = MCPServer("fake_hands_that_see")
for function, name in [(fake_read_active_window, "read_active_window"), (fake_looking_at, "looking_at"),
                       (fake_list_memories, "list_memories"), (fake_open_memory, "open_memory"),
                       (fake_search, "search_memories"), (fake_save, "save_memory")]:
    SEEING.add_tool(function, name=name, description=f"Fake {name}.")


@pytest.fixture
def seeing(world: dict, monkeypatch: pytest.MonkeyPatch) -> dict:
    CALLS.clear()
    monkeypatch.setattr(bridge, "connect_hands", lambda: connect_hands(SEEING, ("read_active_window",)))
    return world


def tool_calls(face: Face) -> list[str]:
    return [r["data"]["name"] for r in face.replies("event") if r["kind"] == "tool_call"]


@pytest.mark.anyio
async def test_each_idle_read_gets_its_reply_and_sends_no_tool_call(seeing: dict) -> None:
    async def browse(face: Face) -> None:
        for message in ({"type": "look"}, {"type": "list_memories"}, {"type": "open_memory", "name": NOTE},
                        {"type": "open_memory", "name": ["not", "a", "name"]}):
            await face.say(message)
        await face.wait_for("memory_note", count=2)
    _, face = await run(browse)
    assert face.replies("looking_at")[0] == {"type": "looking_at", "app": "Fake Notes", "private": False, "note": ""}
    assert face.replies("memory_list")[0]["items"] == [{"name": NOTE, "date": "2026-10-07",
                                                       "title": "Read the booking form"}]
    assert face.replies("memory_note")[0]["answer"] == "Booked by [PERSON]." and face.replies("memory_note")[0]["note"] == ""
    assert CALLS[-2:] == [("open_memory", NOTE), ("open_memory", "")]  # a name that isn't text goes as ""
    assert tool_calls(face) == []  # no popup, so no foreground permission and always-on-top stays (D29)


@pytest.mark.anyio
async def test_a_question_sends_the_chip_first_and_only_save_memory_sends_a_tool_call(seeing: dict) -> None:
    async def ask(face: Face) -> None:
        await face.say({"type": "ask", "text": "What does my window say?"})
        await face.wait_for("turn_done")
    _, face = await run(ask)
    types = [r["type"] for r in face.replies()]
    assert types.index("looking_at") < types.index("event")  # before the question's first event
    assert tool_calls(face) == ["read_active_window", "save_memory"]  # the model's read, then memory's popup
    memories = [r["data"] for r in face.replies("event") if r["kind"] == "memories"]
    assert memories[0]["titles"] == ["Read the booking form"]
    results = [r["data"] for r in face.replies("event") if r["kind"] == "tool_result" and "masked" in r["data"]]
    assert [(r["name"], r["masked"]) for r in results] == [("read_active_window", 1)]  # one [PERSON] in the fake read


@pytest.mark.anyio
async def test_while_a_question_runs_look_is_skipped_and_the_browser_is_busy(seeing: dict) -> None:
    seeing["gate"] = anyio.Event()

    async def busy(face: Face) -> None:
        await face.say({"type": "ask", "text": "hello"})
        await face.wait_for("event", event="sending")  # the question is waiting for the model now
        for message in ({"type": "look"}, {"type": "list_memories"}, {"type": "open_memory", "name": NOTE}):
            await face.say(message)
        await face.wait_for("refused", count=2)
        seeing["gate"].set()
        await face.wait_for("turn_done")
    _, face = await run(busy)
    assert [r["reason"] for r in face.replies("refused")] == [bridge.BUSY, bridge.BUSY]
    assert len(face.replies("looking_at")) == 1 and ("list_memories", "") not in CALLS  # only the question's own look


@pytest.mark.anyio
async def test_a_pseudo_hands_without_the_tools_gets_empty_replies(world: dict) -> None:
    async def browse(face: Face) -> None:
        for message in ({"type": "look"}, {"type": "list_memories"}, {"type": "open_memory", "name": NOTE}):
            await face.say(message)
        await face.wait_for("memory_note")
    _, face = await run(browse)
    assert face.replies("looking_at")[0]["app"] == "" and face.replies("looking_at")[0]["note"] == "the look-at tool failed"
    assert face.replies("memory_list")[0] == {"type": "memory_list", "items": [], "note": "the memory list failed"}
    assert face.replies("memory_note")[0]["note"] == "that memory can't be opened"


# ---------- the masked count ----------

def test_the_brains_labels_are_exactly_the_redactors() -> None:
    analyzer = redactor.build_analyzer()
    labels = set(analyzer.get_supported_entities(language="en")) - redactor.NOT_MASKED | {"PRIVATE"}
    assert REDACTOR_LABELS == labels


@pytest.mark.parametrize("text, count", [
    ("Call [PERSON] on [IN_PHONE], then [PERSON] again", 3),
    ('{"content": "Button #c3: Email [EMAIL_ADDRESS]"}', 1),
    ("[TODO] fix the [restricted app] note [Not A Label] [PERSON", 0),
    ("", 0),
])
def test_only_the_redactors_own_labels_are_counted(text: str, count: int) -> None:
    assert count_masks(text) == count
