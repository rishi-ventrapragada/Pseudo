"""Tests for M18: the Chat shared by the terminal and the face (pseudo_brain/chat.py), and the
session list the face shows (list_sessions, load_session in session.py).

Everything is FAKE: brain_fakes' providers, FakeModels instead of real connections, the
in-memory fake pseudo_hands, and sessions saved to a temporary folder.
"""

import json
from pathlib import Path

import pytest

from brain_fakes import FAKE_CLOUD, FAKE_HANDS, FAKE_LOCAL, FakeModel, reply
from pseudo_brain import chat as chat_module
from pseudo_brain import session as session_module
from pseudo_brain.chat import Chat
from pseudo_brain.hands import connect_hands
from pseudo_brain.local_server import ServerFailure
from pseudo_brain.providers import Allowlist, ProviderRefused
from pseudo_brain.session import Session, SessionNotFound, list_sessions, load_session


class FakeServer:
    def __init__(self, provider) -> None:
        self.provider, self.running = provider, True

    def stop(self) -> bool:
        was_running, self.running = self.running, False
        return was_running


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict:
    """world["refuse"][id] makes that provider fail; world["connected"] lists every connection made."""
    world: dict = {"refuse": {}, "connected": [], "secrets": []}
    monkeypatch.setattr(session_module, "SESSIONS_DIR", tmp_path / "sessions")

    async def fake_connect(provider, servers, on_event):
        if provider.id in world["refuse"]:
            raise world["refuse"][provider.id]
        if not provider.leaves_laptop:
            servers.setdefault(provider.id, FakeServer(provider))
        world["connected"].append(provider.id)
        return FakeModel(reply("fake answer"), provider=provider)
    monkeypatch.setattr(chat_module, "connect_provider", fake_connect)
    world["chat"] = Chat(Allowlist({"groq": FAKE_CLOUD, "local": FAKE_LOCAL}, "groq"), lambda k, d: None,
                         world["secrets"])
    return world


def saved(provider: str, started: str, questions: list[str]) -> Session:
    session = Session(provider=provider, started=started,
                      turns=[[{"role": "user", "content": q}, {"role": "assistant", "content": "ok"}] for q in questions])
    session.save()
    return session


# ---------- starting and switching ----------

@pytest.mark.anyio
async def test_start_uses_the_default_provider_and_remembers_its_key(world: dict) -> None:
    await world["chat"].start()
    assert world["chat"].provider.id == "groq" and world["chat"].session.provider == "groq"
    assert world["secrets"] == ["fake-key"]


@pytest.mark.anyio
async def test_continue_starts_on_the_latest_sessions_own_provider(world: dict) -> None:
    saved("local", "20260101-000000-000", ["earlier"])
    await world["chat"].start(resume=True)
    assert world["connected"] == ["local"] and len(world["chat"].session.turns) == 1


@pytest.mark.anyio
async def test_continue_refuses_another_provider_before_connecting(world: dict) -> None:
    saved("local", "20260101-000000-000", ["private"])
    with pytest.raises(ProviderRefused, match="a session never changes provider"):
        await world["chat"].start(resume=True, wanted="groq")
    assert world["connected"] == []


@pytest.mark.anyio
async def test_a_switch_starts_a_new_session(world: dict) -> None:
    chat = world["chat"]
    await chat.start()
    first = chat.session
    assert await chat.switch("local") is True
    assert chat.provider.id == "local" and chat.session is not first and chat.session.provider == "local"
    assert await chat.switch("local") is False  # already in use: nothing happens


@pytest.mark.anyio
@pytest.mark.parametrize("refusal", [ServerFailure("cloud isn't switched off: fake"), None])
async def test_a_refused_switch_changes_nothing(world: dict, refusal) -> None:
    chat = world["chat"]
    await chat.start()
    session = chat.session
    if refusal:
        world["refuse"]["local"] = refusal
    with pytest.raises((ServerFailure, ProviderRefused)):
        await chat.switch("local" if refusal else "cloudy")  # a failing server, or not on the allowlist
    assert chat.provider.id == "groq" and chat.session is session


# ---------- asking, opening, closing ----------

@pytest.mark.anyio
async def test_asking_saves_the_session_after_every_turn(world: dict) -> None:
    chat = world["chat"]
    await chat.start()
    async with connect_hands(FAKE_HANDS) as hands:
        result = await chat.ask("hello", hands)
    assert result.ok and result.answer == "fake answer"
    assert [item["questions"] for item in list_sessions()] == [1]


@pytest.mark.anyio
async def test_opening_a_session_continues_it_on_its_own_provider(world: dict) -> None:
    saved("local", "20260101-000000-000", ["earlier"])
    chat = world["chat"]
    await chat.start()
    await chat.open_session("20260101-000000-000")
    assert chat.provider.id == "local" and chat.session.started == "20260101-000000-000"
    assert world["connected"] == ["groq", "local"]


@pytest.mark.anyio
@pytest.mark.parametrize("name", ["..\\..\\secret", "../x", "20260101-000000-000.json", "", "C:\\x", 42])
async def test_a_name_that_is_not_a_session_is_refused(world: dict, name) -> None:
    chat = world["chat"]
    await chat.start()
    with pytest.raises(SessionNotFound, match="not a session name"):
        await chat.open_session(name)
    assert chat.provider.id == "groq" and world["connected"] == ["groq"]


@pytest.mark.anyio
async def test_a_missing_session_is_refused(world: dict) -> None:
    await world["chat"].start()
    with pytest.raises(SessionNotFound, match="no readable saved session"):
        await world["chat"].open_session("20990101-000000-000")


@pytest.mark.anyio
async def test_close_stops_only_the_servers_pseudo_started(world: dict) -> None:
    chat = world["chat"]
    await chat.start()
    assert chat.close() == []  # Groq has no server
    await chat.switch("local")
    assert chat.close() == ["local"] and chat.close() == []  # stopped once


# ---------- the session list the face shows ----------

def test_sessions_are_listed_newest_first_with_provider_and_first_question(world: dict) -> None:
    saved("groq", "20260101-000000-000", ["first question", "second"])
    saved("local", "20260102-000000-000", ["x" * 100])
    items = list_sessions()
    assert [(i["name"], i["provider"], i["questions"]) for i in items] == [
        ("20260102-000000-000", "local", 1), ("20260101-000000-000", "groq", 2)]
    assert items[0]["title"] == "x" * session_module.TITLE_CHARS and items[1]["title"] == "first question"


def test_a_damaged_session_file_is_left_out_of_the_list(world: dict) -> None:
    saved("groq", "20260101-000000-000", ["fine"])
    (session_module.SESSIONS_DIR / "20260102-000000-000.json").write_text("{not json", encoding="utf-8")
    assert [i["name"] for i in list_sessions()] == ["20260101-000000-000"]


def test_a_loaded_session_keeps_its_answer_labels(world: dict) -> None:
    session = saved("local", "20260101-000000-000", ["q"])
    session.note_answer("local · tiny-model")
    session.save()
    loaded = load_session("20260101-000000-000")
    assert loaded.transcript() == [{"role": "user", "content": "q"},
                                   {"role": "assistant", "content": "ok", "answered_by": "local · tiny-model"}]
    saved_file = json.loads((session_module.SESSIONS_DIR / "20260101-000000-000.json").read_text(encoding="utf-8"))
    assert saved_file["messages"] == loaded.transcript()  # what is shown is exactly what is saved
