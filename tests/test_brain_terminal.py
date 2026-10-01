"""Tests for M16: /provider, --provider and --continue in the terminal (pseudo_brain/terminal.py).
Since M18 the rules live in chat.py, so connecting is faked there; these tests check the terminal still
behaves exactly as in M16.

Everything is FAKE: the allowlist holds brain_fakes' providers, connecting to a provider
returns a FakeModel (no network, no real server), pseudo_hands is the in-memory fake, and
your typing is a scripted list. The real chat() runs; what it prints is checked.
"""

import sys
from dataclasses import replace
from pathlib import Path

import pytest

from brain_fakes import FAKE_CLOUD, FAKE_HANDS, FAKE_LOCAL, FakeModel, reply
from pseudo_brain import chat as chat_module
from pseudo_brain import session as session_module
from pseudo_brain import terminal
from pseudo_brain.hands import connect_hands
from pseudo_brain.local_server import ServerFailure
from pseudo_brain.providers import Allowlist, ProviderRefused
from pseudo_brain.session import Session


class FakeServer:
    """Stands in for LocalServer: remembers whether it was stopped."""

    def __init__(self, provider) -> None:
        self.provider, self.running = provider, True

    def stop(self) -> bool:
        was_running, self.running = self.running, False
        return was_running


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict:
    """A fake world: script it through world["typed"] (what you type) and world["refuse"] (failing providers)."""
    world: dict = {"typed": [], "refuse": {}, "models": {}, "servers": [], "answer": "an answer"}
    monkeypatch.setattr(session_module, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(terminal, "load_allowlist", lambda: Allowlist({"groq": FAKE_CLOUD, "local": FAKE_LOCAL}, "groq"))
    monkeypatch.setattr(terminal, "connect_hands", lambda: connect_hands(FAKE_HANDS))

    async def fake_connect(provider, servers, on_event):
        if provider.id in world["refuse"]:
            raise world["refuse"][provider.id]
        if not provider.leaves_laptop:  # private mode: pretend its server was started
            world["servers"].append(servers.setdefault(provider.id, FakeServer(provider)))
        model = FakeModel(reply(world["answer"]), provider=provider)
        world["models"].setdefault(provider.id, []).append(model)
        return model

    async def fake_ask(prompt: str) -> str:
        if not world["typed"]:
            raise EOFError
        return world["typed"].pop(0)
    monkeypatch.setattr(chat_module, "connect_provider", fake_connect)
    monkeypatch.setattr(terminal, "ask", fake_ask)
    return world


async def run(world: dict, typed: list[str], capsys, resume: bool = False, wanted: str | None = None) -> str:
    world["typed"] = list(typed)
    await terminal.chat(resume, wanted)
    return capsys.readouterr().out


def questions_sent(model: FakeModel) -> list[list[str]]:
    """For each request: the user messages it carried (the history the provider saw)."""
    return [[m["content"] for m in request["messages"] if m["role"] == "user"] for request in model.requests]


@pytest.mark.anyio
async def test_provider_lists_every_allowed_provider_with_its_privacy_note(world: dict, capsys) -> None:
    out = await run(world, ["/provider"], capsys)
    assert " * groq (Fake cloud): big-model, fallback small-model | data leaves this laptop: YES | fake note" in out
    assert "   local (Fake local): tiny-model | data leaves this laptop: NO | fake note" in out


@pytest.mark.anyio
async def test_an_unknown_provider_is_refused_and_nothing_changes(world: dict, capsys) -> None:
    out = await run(world, ["/provider cloudy", "hello"], capsys)
    assert '--- REFUSED: "cloudy" is not in the allowlist' in out and "Still on groq. ---" in out
    assert list(world["models"]) == ["groq"] and questions_sent(world["models"]["groq"][0]) == [["hello"]]


@pytest.mark.anyio
async def test_switching_starts_a_new_session_so_history_never_moves(world: dict, capsys) -> None:
    out = await run(world, ["hello", "/provider local", "hi again"], capsys)
    assert "--- SWITCHED TO local: NEW SESSION" in out and "--- ANSWER (groq · big-model |" in out
    assert "--- ANSWER (local · tiny-model |" in out
    assert questions_sent(world["models"]["local"][0]) == [["hi again"]]  # "hello" stayed with groq
    assert len(list(session_module.SESSIONS_DIR.glob("*.json"))) == 2  # two sessions, two files


@pytest.mark.anyio
async def test_a_failed_switch_keeps_the_provider_and_the_session(world: dict, capsys) -> None:
    world["refuse"]["local"] = ServerFailure("cloud isn't switched off: fake")
    out = await run(world, ["hello", "/provider local", "again"], capsys)
    assert "--- REFUSED: cloud isn't switched off: fake. Still on groq. ---" in out
    assert questions_sent(world["models"]["groq"][0])[-1] == ["hello", "again"]  # same session


@pytest.mark.anyio
async def test_asking_for_the_provider_in_use_changes_nothing(world: dict, capsys) -> None:
    out = await run(world, ["/provider groq"], capsys)
    assert "--- ALREADY USING groq ---" in out and len(world["models"]["groq"]) == 1


@pytest.mark.anyio
async def test_private_mode_at_launch_and_its_server_is_stopped_at_exit(world: dict, capsys) -> None:
    out = await run(world, ["hi"], capsys, wanted="local")
    assert "--- PROVIDER local (Fake local): tiny-model | data leaves this laptop: NO" in out
    assert "--- STOPPED the local server (Pseudo started it) ---" in out and not world["servers"][0].running


@pytest.mark.anyio
async def test_continue_resumes_on_the_sessions_own_provider(world: dict, capsys) -> None:
    Session(turns=[[{"role": "user", "content": "earlier"}, {"role": "assistant", "content": "ok"}]],
            provider="local").save()
    out = await run(world, ["next"], capsys, resume=True)
    assert "provider: local | 1 earlier turn(s) loaded" in out
    assert questions_sent(world["models"]["local"][0]) == [["earlier", "next"]] and "groq" not in world["models"]


@pytest.mark.anyio
async def test_continue_refuses_a_different_provider(world: dict, capsys) -> None:
    Session(turns=[[{"role": "user", "content": "private"}]], provider="local").save()
    with pytest.raises(ProviderRefused, match="belongs to local, and a session never changes provider"):
        await run(world, [], capsys, resume=True, wanted="groq")
    assert world["models"] == {}  # nothing was connected, nothing was sent


@pytest.mark.anyio
async def test_a_key_in_an_answer_is_hidden(world: dict, capsys) -> None:
    world["answer"] = "the key is fake-key"
    out = await run(world, ["hi"], capsys)
    assert "fake-key" not in out and "the key is <hidden>" in out


def test_an_unknown_provider_at_launch_cannot_start(world: dict, capsys, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["pseudo_brain", "--provider", "cloudy"])
    assert terminal.main() == 1
    assert '--- CANNOT START: "cloudy" is not in the allowlist' in capsys.readouterr().out


@pytest.mark.anyio
async def test_a_mistyped_command_is_never_sent_to_the_model(world: dict, capsys) -> None:
    out = await run(world, ["/provder local"], capsys)
    assert "--- UNKNOWN COMMAND /provder: nothing was sent." in out and world["models"]["groq"][0].requests == []


@pytest.mark.anyio
async def test_a_byte_order_mark_before_a_command_is_ignored(world: dict, capsys) -> None:
    out = await run(world, ["﻿/provider"], capsys)  # PowerShell starts piped text with one (found in M16)
    assert "--- ALLOWED PROVIDERS" in out and world["models"]["groq"][0].requests == []


def test_the_provider_list_shows_why_a_provider_is_disabled() -> None:
    assert terminal.describe(replace(FAKE_LOCAL, disabled="fake reason")).endswith("| DISABLED: fake reason")
    assert "DISABLED" not in terminal.describe(FAKE_CLOUD)
