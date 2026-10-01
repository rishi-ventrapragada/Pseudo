"""Tests for M18: the bridge's provider switches, refusals and saved sessions (pseudo_brain/bridge.py).

The REAL bridge runs on in-memory pipes with bridge_fakes' fake face; everything else is FAKE,
and sessions are saved to a temporary folder.
"""

import json

import pytest

from bridge_fakes import Face, run, world  # noqa: F401 - world is a pytest fixture
from pseudo_brain import session as session_module
from pseudo_brain.local_server import ServerFailure

# ---------- providers and sessions ----------

@pytest.mark.anyio
async def test_switching_provider_starts_a_new_session(world: dict) -> None:
    async def switch(face: Face) -> None:
        await face.say({"type": "ask", "text": "hello"})
        await face.wait_for("turn_done")
        await face.say({"type": "provider", "id": "local"})
        await face.wait_for("switched")
    _, face = await run(switch)
    switched = face.replies("switched")[0]
    assert switched["provider"] == "local" and switched["session"]["messages"] == []
    assert switched["session"]["name"] != face.replies("ready")[0]["session"]["name"]
    assert face.replies("event")[-1] == {"type": "event", "kind": "server_starting",
                                         "data": {"provider": "local", "address": "127.0.0.1:11434"}}


@pytest.mark.anyio
@pytest.mark.parametrize("message, reason", [
    ({"type": "provider", "id": "cloudy"}, '"cloudy" is not in the allowlist'),
    ({"type": "provider", "id": "groq"}, "already using groq"),
    ({"type": "provider", "id": "local"}, "cloud isn't switched off: fake"),
    ({"type": "open_session", "name": "..\\..\\secret"}, "that is not a session name"),
    ({"type": "delete_everything"}, "not a message the brain understands"),
    (b"this is not json\n", "not a message the brain understands"),
])
async def test_refusals_say_why_and_change_nothing(world: dict, message, reason: str) -> None:
    world["refuse"]["local"] = ServerFailure("cloud isn't switched off: fake")

    async def refused(face: Face) -> None:
        await face.say(message)
        await face.wait_for("refused")
    _, face = await run(refused)
    assert reason in face.replies("refused")[0]["reason"] and face.replies("switched") == []


@pytest.mark.anyio
async def test_sessions_are_listed_and_one_opens_on_its_own_provider(world: dict) -> None:
    session_module.Session(provider="local", started="20260101-000000-000",
                           turns=[[{"role": "user", "content": "private question"},
                                   {"role": "assistant", "content": "private answer"}]]).save()

    async def reopen(face: Face) -> None:
        await face.say(b"\xef\xbb\xbf" + json.dumps({"type": "list_sessions"}).encode() + b"\n")  # with a BOM
        await face.wait_for("sessions")
        await face.say({"type": "open_session", "name": "20260101-000000-000"})
        await face.wait_for("session")
        await face.say({"type": "ask", "text": "and now?"})
        await face.wait_for("turn_done")
    _, face = await run(reopen)
    assert face.replies("sessions")[0]["items"] == [{"name": "20260101-000000-000", "provider": "local",
                                                     "questions": 1, "title": "private question"}]
    opened = face.replies("session")[0]
    assert opened["provider"] == "local" and [m["content"] for m in opened["messages"]] == ["private question",
                                                                                          "private answer"]
    assert face.replies("event")[-1]["data"]["provider"] == "local"  # the next answer came from local
