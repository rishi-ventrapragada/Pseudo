"""Tests for M16: same-provider fallback, private mode, keys and the provider check (D16).

Everything is FAKE (brain_fakes.py): FakeModel is the REAL Model with scripted replies,
so the fallback logic under test is the real one. No network, no real waiting, and
.env is never read: key tests point model.ENV_PATH at an empty decoy file.
"""

import dataclasses
from pathlib import Path
from types import SimpleNamespace

import pytest

from brain_fakes import FAKE_CLOUD, FAKE_LOCAL, FAKE_ONE, FakeModel, ask, rate_limited, reply, unreachable
from pseudo_brain import model
from pseudo_brain.model import Model, ModelFailure, load_key
from pseudo_brain.session import Session


def of_kind(events: list, kind: str) -> list[dict]:
    return [data for event_kind, data in events if event_kind == kind]


# ---------- fallback: only to the next model of the SAME provider ----------

@pytest.mark.anyio
async def test_a_429_switches_to_the_next_model_and_says_so_before_asking_it(waits: list) -> None:
    timeline: list = []
    fake = FakeModel(rate_limited("2"), reply("Done."), provider=FAKE_CLOUD, timeline=timeline)
    result, _, _ = await ask(fake, events=timeline)
    assert fake.used == ["big-model", "small-model"] and waits == []  # switched at once, no waiting
    kinds = [kind for kind, _ in timeline]
    assert kinds[:4] == ["sending", "request", "fallback", "request"]  # the switch is announced BEFORE it's used
    assert of_kind(timeline, "fallback") == [{"provider": "groq", "from": "big-model", "to": "small-model"}]
    answer = of_kind(timeline, "answer")[0]
    assert (answer["provider"], answer["model"], answer["fallback"]) == ("groq", "small-model", True)
    assert result.ok and result.model == "small-model"


@pytest.mark.anyio
async def test_the_next_question_starts_on_the_main_model_again() -> None:
    fake = FakeModel(rate_limited("2"), reply("First."), reply("Second."), provider=FAKE_CLOUD)
    session = Session()
    await ask(fake, session=session)
    result, events, _ = await ask(fake, "And now?", session=session)
    assert fake.used == ["big-model", "small-model", "big-model"]
    assert of_kind(events, "answer")[0]["fallback"] is False and result.model == "big-model"


@pytest.mark.anyio
async def test_a_429_on_the_last_model_waits_and_never_leaves_the_provider(waits: list) -> None:
    fake = FakeModel(rate_limited("2"), rate_limited("3"), reply("Done."), provider=FAKE_CLOUD)
    result, events, _ = await ask(fake)
    assert fake.used == ["big-model", "small-model", "small-model"] and waits == [3.0]
    assert len(of_kind(events, "fallback")) == 1 and set(fake.used) <= set(FAKE_CLOUD.models)
    assert result.ok


@pytest.mark.anyio
async def test_events_say_which_provider_and_model_did_the_work() -> None:
    _, events, _ = await ask(FakeModel(reply("Hi."), provider=FAKE_CLOUD))
    sending, answer = of_kind(events, "sending")[0], of_kind(events, "answer")[0]
    assert (sending["provider"], sending["model"]) == ("groq", "big-model")
    assert (answer["provider"], answer["model"], answer["fallback"]) == ("groq", "big-model", False)


# ---------- a session stays with one provider ----------

@pytest.mark.anyio
async def test_a_new_session_belongs_to_the_first_provider_that_answers() -> None:
    _, _, session = await ask(FakeModel(reply("Hi."), provider=FAKE_LOCAL))
    assert session.provider == "local" and session.answered_by == {0: "local · tiny-model"}


@pytest.mark.anyio
async def test_a_session_refuses_a_model_from_another_provider() -> None:
    session = Session(provider="local")  # a private conversation...
    cloud = FakeModel(reply("never sent"), provider=FAKE_CLOUD)  # ...must never reach the cloud
    result, events, _ = await ask(cloud, session=session)
    assert not result.ok and "belongs to local, not groq" in result.reason
    assert cloud.requests == [] and session.turns == [] and of_kind(events, "sending") == []


@pytest.mark.anyio
async def test_a_fallback_answer_is_labelled_as_one() -> None:
    _, _, session = await ask(FakeModel(rate_limited("2"), reply("Done."), provider=FAKE_CLOUD))
    assert session.answered_by == {0: "groq · small-model (fallback)"}


# ---------- private mode: never falls back, fails visibly ----------

@pytest.mark.anyio
async def test_private_mode_fails_visibly_when_ollama_cant_be_reached() -> None:
    fake = FakeModel(unreachable(), provider=FAKE_LOCAL)
    result, events, _ = await ask(fake)
    assert not result.ok and result.answer is None and "could not reach Fake local" in result.reason
    assert of_kind(events, "fallback") == [] and fake.used == ["tiny-model"]


@pytest.mark.anyio
async def test_private_mode_429s_wait_on_the_same_model_and_never_switch(waits: list) -> None:
    fake = FakeModel(rate_limited("2"), provider=FAKE_LOCAL)
    result, events, _ = await ask(fake)
    assert not result.ok and len(waits) == model.MAX_RATE_LIMIT_WAITS
    assert of_kind(events, "fallback") == [] and set(fake.used) == {"tiny-model"}


def test_a_model_talks_only_to_its_providers_address() -> None:
    assert Model(FAKE_LOCAL, "no-key").client.base_url.host == "127.0.0.1"
    assert Model(FAKE_CLOUD, "fake-key").client.base_url.host == "fake.invalid"


@pytest.mark.anyio
async def test_each_provider_uses_its_own_token_budget() -> None:
    small = dataclasses.replace(FAKE_LOCAL, max_prompt_tokens=200)
    result, _, _ = await ask(FakeModel(reply("never sent"), provider=small), "y" * 1200)
    assert not result.ok and "too large" in result.reason and "limit 200" in result.reason
    result, _, _ = await ask(FakeModel(reply("Fine."), provider=FAKE_CLOUD), "y" * 1200)
    assert result.ok


# ---------- keys ----------

def test_a_missing_key_names_the_variable_and_nothing_else(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    decoy = tmp_path / "decoy.env"  # never the real .env
    decoy.write_text("SOMETHING_ELSE=1\n", encoding="utf-8")
    monkeypatch.setattr(model, "ENV_PATH", decoy)
    monkeypatch.delenv("FAKE_M16_KEY", raising=False)
    with pytest.raises(ModelFailure, match=r"^missing FAKE_M16_KEY in \.env"):
        load_key(FAKE_CLOUD)
    monkeypatch.setenv("FAKE_M16_KEY", "fake-value-123")
    assert load_key(FAKE_CLOUD) == "fake-value-123"


def test_a_provider_without_a_key_reads_no_env_file(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(model, "load_dotenv", lambda *_: pytest.fail("private mode must not read .env"))
    assert load_key(FAKE_LOCAL) == model.NO_KEY


# ---------- the provider check ----------

def listing(*ids: str, error: Exception | None = None) -> SimpleNamespace:
    """A fake client whose models.list() returns these ids (or raises)."""
    async def list_models(**_):
        if error:
            raise error
        return SimpleNamespace(data=[SimpleNamespace(id=i) for i in ids])
    return SimpleNamespace(models=SimpleNamespace(list=list_models))


@pytest.mark.anyio
async def test_the_check_passes_when_every_listed_model_is_there() -> None:
    fake = Model(FAKE_CLOUD, "fake-key")
    fake.client = listing("big-model", "small-model", "another-model")
    await fake.check()


@pytest.mark.anyio
async def test_the_check_refuses_an_unreachable_provider_or_a_missing_model() -> None:
    fake = Model(FAKE_LOCAL, "no-key")
    fake.client = listing(error=unreachable())
    with pytest.raises(ModelFailure, match="could not reach Fake local at 127.0.0.1:11434"):
        await fake.check()
    fake.client = listing("some-other-model")
    with pytest.raises(ModelFailure, match="doesn't have tiny-model"):
        await fake.check()


@pytest.mark.anyio
async def test_the_check_also_wants_the_speech_model() -> None:  # M26: a retired Whisper stops Pseudo at start
    fake = Model(dataclasses.replace(FAKE_CLOUD, transcribe_model="ears-model"), "fake-key")
    fake.client = listing("big-model", "small-model")
    with pytest.raises(ModelFailure, match="doesn't have ears-model"):
        await fake.check()
    fake.client = listing("big-model", "small-model", "ears-model")
    await fake.check()


def test_fake_one_has_a_single_model() -> None:  # the M14 tests rely on it: a 429 there must wait
    assert len(FAKE_ONE.models) == 1
