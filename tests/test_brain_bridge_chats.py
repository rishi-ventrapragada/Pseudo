"""Tests for M41: renaming, deleting and searching saved chats over the bridge (bridge_sessions.py),
and what that means for the open chat and a warm session (chat_sessions.py).

The REAL bridge runs on in-memory pipes with bridge_fakes' fake face; everything else is FAKE, and
chats are saved to a temporary folder.
"""

import json
from dataclasses import replace

import anyio
import pytest

from brain_fakes import FAKE_CLOUD, FAKE_LOCAL
from bridge_fakes import Face, run, world  # noqa: F401 - world is a pytest fixture
from pseudo_brain import bridge, chat_sessions
from pseudo_brain import session as session_module
from pseudo_brain.providers import Allowlist
from pseudo_brain.session import Session

OLD = "20261009-180000-456"


def save_old_chat() -> None:
    Session(provider="groq", started=OLD, turns=[[{"role": "user", "content": "What does the booking form say?"},
                                                  {"role": "assistant", "content": "A fake booking."}]]).save()


def saved(name: str) -> dict | None:
    path = session_module.SESSIONS_DIR / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


# ---------- rename ----------

@pytest.mark.anyio
async def test_a_rename_sends_the_list_and_then_renamed(world: dict) -> None:
    save_old_chat()

    async def rename(face: Face) -> None:
        await face.say({"type": "rename_session", "name": OLD, "title": "Booking form"})
        await face.wait_for("renamed")
    _, face = await run(rename)
    assert [r["type"] for r in face.replies()][-2:] == ["sessions", "renamed"]
    assert face.replies("sessions")[-1]["items"][0]["title"] == "Booking form"
    assert face.replies("renamed")[0] == {"type": "renamed", "name": OLD, "title": "Booking form"}
    assert saved(OLD)["title"] == "Booking form"


@pytest.mark.anyio
async def test_the_open_chat_keeps_its_new_name_after_the_next_question(world: dict) -> None:
    async def rename_open(face: Face) -> None:
        await face.say({"type": "ask", "text": "hello"})
        await face.wait_for("turn_done")
        name = face.replies("ready")[0]["session"]["name"]
        await face.say({"type": "rename_session", "name": name, "title": "Greeting"})
        await face.wait_for("renamed")
        await face.say({"type": "ask", "text": "and again"})
        await face.wait_for("turn_done", count=2)
    _, face = await run(rename_open)
    chat = saved(face.replies("ready")[0]["session"]["name"])
    assert chat["title"] == "Greeting" and [m["content"] for m in chat["messages"] if m["role"] == "user"] == [
        "hello", "and again"]


# ---------- delete ----------

@pytest.mark.anyio
async def test_deleting_the_open_chat_starts_a_new_one(world: dict) -> None:
    async def delete_open(face: Face) -> None:
        await face.say({"type": "ask", "text": "hello"})
        await face.wait_for("turn_done")
        await face.say({"type": "delete_session", "name": face.replies("ready")[0]["session"]["name"]})
        await face.wait_for("deleted")
    _, face = await run(delete_open)
    first = face.replies("ready")[0]["session"]["name"]
    assert [r["type"] for r in face.replies()][-3:] == ["session", "sessions", "deleted"]
    fresh = face.replies("session")[0]
    assert fresh["name"] != first and fresh["messages"] == [] and fresh["provider"] == "groq"
    assert face.replies("deleted")[0] == {"type": "deleted", "name": first, "title": "hello"}
    assert saved(first) is None and face.replies("sessions")[-1]["items"] == []


@pytest.mark.anyio
async def test_deleting_another_chat_leaves_the_open_one_alone(world: dict) -> None:
    save_old_chat()

    async def delete_old(face: Face) -> None:
        await face.say({"type": "delete_session", "name": OLD})
        await face.wait_for("deleted")
    _, face = await run(delete_old)
    assert face.replies("session") == [] and saved(OLD) is None


@pytest.mark.anyio
@pytest.mark.parametrize("message, reason", [
    ({"type": "delete_session", "name": "..\\..\\secret"}, "not a chat name Pseudo makes"),
    ({"type": "delete_session"}, "not a chat name Pseudo makes"),
    ({"type": "delete_session", "name": "20200101-000000-000"}, "no saved chat called"),
    ({"type": "rename_session", "name": OLD, "title": "two\nlines"}, "one line"),
])
async def test_a_refused_change_says_why_and_changes_nothing(world: dict, message: dict, reason: str) -> None:
    save_old_chat()
    before = saved(OLD)

    async def refused(face: Face) -> None:
        await face.say(message)
        await face.wait_for("refused")
    _, face = await run(refused)
    assert reason in face.replies("refused")[0]["reason"] and saved(OLD) == before
    assert face.replies("renamed") == face.replies("deleted") == []


# ---------- while a question runs ----------

@pytest.mark.anyio
async def test_rename_and_delete_wait_for_the_question_but_search_answers_at_once(world: dict) -> None:
    save_old_chat()
    world["gate"] = anyio.Event()

    async def mid_question(face: Face) -> None:
        await face.say({"type": "ask", "text": "hello"})
        await face.say({"type": "rename_session", "name": OLD, "title": "Renamed"})
        await face.say({"type": "delete_session", "name": OLD})
        await face.wait_for("refused", count=2)
        await face.say({"type": "search_sessions", "text": "BOOKING"})
        await face.wait_for("found")
        assert face.replies("turn_done") == []  # the question is still running
        world["gate"].set()
        await face.wait_for("turn_done")
    _, face = await run(mid_question)
    assert all(r["reason"] == bridge.BUSY for r in face.replies("refused"))
    assert saved(OLD)["title"] == "" and face.replies("renamed") == face.replies("deleted") == []
    found = face.replies("found")[0]
    assert found["text"] == "BOOKING" and [item["name"] for item in found["items"]] == [OLD]


# ---------- providers ----------

@pytest.mark.anyio
async def test_ready_says_which_providers_are_disabled(world: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    off = replace(FAKE_LOCAL, disabled="fake reason")
    monkeypatch.setattr(bridge, "load_allowlist", lambda: Allowlist({"groq": FAKE_CLOUD, "local": off}, "groq"))

    async def nothing(face: Face) -> None:
        pass
    _, face = await run(nothing)
    assert {p["id"]: p["disabled"] for p in face.replies("ready")[0]["providers"]} == {"groq": "", "local": "fake reason"}


# ---------- the warm session (chat_sessions.py, without the bridge) ----------

class FakeWarm:
    def __init__(self, conversation: str) -> None:
        self.conversation, self.ended = conversation, []

    async def end(self, why: str) -> None:
        self.ended.append(why)


class FakeChat:
    def __init__(self, open_name: str, warm_for: str) -> None:
        self.session, self.warm = Session(started=open_name, provider="groq"), FakeWarm(warm_for)

    def new_session(self) -> None:
        self.session = Session(provider="groq")


@pytest.mark.anyio
@pytest.mark.parametrize("warm_for, stopped", [(OLD, ["its chat was deleted"]), ("20261010-000000-000", [])])
async def test_a_warm_session_that_served_the_deleted_chat_is_stopped(world: dict, warm_for: str, stopped) -> None:
    save_old_chat()
    chat = FakeChat(open_name="20261010-120000-000", warm_for=warm_for)
    assert await chat_sessions.delete(chat, OLD) == ("What does the booking form say?", False)
    assert chat.warm.ended == stopped and chat.session.started == "20261010-120000-000"
