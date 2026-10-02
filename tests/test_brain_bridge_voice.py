"""Tests for M26: voice over the bridge (pseudo_brain/bridge_voice.py, D24).

The REAL bridge runs on in-memory pipes with bridge_fakes' fake face. The speech model is replaced by
a fake transcribe(), and the Windows voice by FAKE_WAV (bridge_fakes), so nothing here touches the
network, a microphone or the speakers.
"""

import base64

import anyio
import pytest

from bridge_fakes import FAKE_WAV, Face, run, world  # noqa: F401 - world is a pytest fixture
from pseudo_brain import bridge, bridge_voice
from pseudo_brain.voice_in import Heard, VoiceRefused
from pseudo_brain.voice_out import VoiceUnavailable

RECORDING = base64.b64encode(bytes(3200)).decode("ascii")  # a FAKE 0.1 s recording


@pytest.fixture
def heard(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Replace the speech model. heard["refuse_first"] (if set) is raised once; after that every recording
    is heard as heard["result"]. heard["audio"] records what each call was given."""
    heard: dict = {"result": Heard("Say hello to me.", "", 3.9, sent=True), "refuse_first": None, "audio": []}

    async def fake_transcribe(model, audio):
        heard["audio"].append(audio)
        refusal, heard["refuse_first"] = heard["refuse_first"], None
        if refusal:
            raise refusal
        return heard["result"]
    monkeypatch.setattr(bridge_voice, "transcribe", fake_transcribe)
    return heard


@pytest.mark.anyio
async def test_a_recording_comes_back_as_a_transcript_and_is_never_sent_as_a_question(world: dict, heard: dict,
                                                                                       capsys) -> None:
    async def talk(face: Face) -> None:
        await face.say({"type": "transcribe", "audio": RECORDING})
        await face.wait_for("transcript")
    _, face = await run(talk)
    assert face.replies("transcript") == [{"type": "transcript", "text": "Say hello to me.", "note": "", "seconds": 3.9}]
    assert heard["audio"] == [RECORDING]
    assert face.replies("event") == [] and face.replies("turn_done") == []  # L8: nothing asked until you press Ask
    log = capsys.readouterr().err
    assert "3.9 s recording, sent to Fake cloud, 16 characters heard" in log and "Say hello" not in log  # counts only


@pytest.mark.anyio
async def test_a_refused_recording_is_reported_and_the_bridge_is_free_again(world: dict, heard: dict) -> None:
    heard["refuse_first"] = VoiceRefused("the recording is longer than 30 seconds, so it wasn't sent")

    async def talk_twice(face: Face) -> None:
        await face.say({"type": "transcribe", "audio": RECORDING})
        await face.wait_for("refused")
        await face.say({"type": "transcribe", "audio": RECORDING})
        await face.wait_for("transcript")
    _, face = await run(talk_twice)
    assert face.replies("refused")[0]["reason"] == "the recording is longer than 30 seconds, so it wasn't sent"
    assert len(face.replies("transcript")) == 1


@pytest.mark.anyio
async def test_recording_while_a_question_runs_is_refused_as_busy(world: dict, heard: dict) -> None:
    world["gate"] = anyio.Event()

    async def talk_while_busy(face: Face) -> None:
        await face.say({"type": "ask", "text": "first"})
        await face.wait_for("event", event="sending")
        await face.say({"type": "transcribe", "audio": RECORDING})
        await face.wait_for("refused")
        world["gate"].set()
        await face.wait_for("turn_done")
    _, face = await run(talk_while_busy)
    assert [r["reason"] for r in face.replies("refused")] == [bridge.BUSY] and heard["audio"] == []


@pytest.mark.anyio
async def test_answers_are_spoken_by_default_and_not_after_speak_answers_off(world: dict) -> None:
    async def ask_twice(face: Face) -> None:
        await face.say({"type": "ask", "text": "first"})
        await face.wait_for("speech")
        await face.wait_for("turn_done")
        await face.say({"type": "speak_answers", "on": "no"})  # not a real false: ignored
        await face.say({"type": "speak_answers", "on": False})
        await face.say({"type": "ask", "text": "second"})
        await face.wait_for("turn_done", count=2)
    _, face = await run(ask_twice)
    (speech,) = face.replies("speech")
    assert base64.b64decode(speech["audio"]) == FAKE_WAV and speech["reason"] == ""
    assert world["spoken"] == ["Your window says BLUE."]  # the answer, as spoken_text() made it


@pytest.mark.anyio
async def test_a_missing_voice_is_reported_and_the_question_still_succeeds(world: dict,
                                                                           monkeypatch: pytest.MonkeyPatch) -> None:
    def no_voice(text: str) -> bytes:
        raise VoiceUnavailable("the Windows voice MSTTS_V110_enIN_RaviM isn't installed")
    monkeypatch.setattr(bridge_voice, "synthesize", no_voice)

    async def ask(face: Face) -> None:
        await face.say({"type": "ask", "text": "first"})
        await face.wait_for("speech")
        await face.wait_for("turn_done")
    _, face = await run(ask)
    assert face.replies("speech") == [{"type": "speech", "audio": "", "reason": "the Windows voice "
                                       "MSTTS_V110_enIN_RaviM isn't installed"}]
    assert face.replies("turn_done") == [{"type": "turn_done", "ok": True}]


def test_only_a_real_answer_is_spoken() -> None:
    class FakeBridge:
        speak_answers, started = True, []
        tasks = type("Tasks", (), {"start_soon": lambda self, *args: FakeBridge.started.append(args[2])})()
    for data in ({"text": ""}, {"text": "   "}, {"text": None}, {}):
        bridge_voice.on_answer(FakeBridge, data)
    bridge_voice.on_answer(FakeBridge, {"text": "Hello."})
    assert FakeBridge.started == ["Hello."]
