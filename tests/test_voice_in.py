"""Tests for M26: voice input (pseudo_brain/voice_in.py, D24).

Every recording here is FAKE, made in memory: a tone, a whisper-quiet tone, or silence. The speech
model is a fake client that records what it was sent, so no test touches the network or a microphone.
"""

import base64
import builtins
import dataclasses
import io
import math
import wave
from array import array
from types import SimpleNamespace

import pytest

from brain_fakes import FAKE_CLOUD, FAKE_LOCAL, rate_limited, unreachable
from pseudo_brain.model import Model
from pseudo_brain.voice_in import (GATE_DBFS, RATE, Heard, VoiceRefused, kept_text, loudest_100ms_dbfs,
                                   pcm_from_base64, transcribe, wav_bytes)

WITH_EARS = dataclasses.replace(FAKE_CLOUD, transcribe_model="ears-model")


def tone(seconds: float, level: float = 0.5) -> array:
    """A 440 Hz tone; level 0.5 is loud (about -9 dBFS), 0.004 is quieter than the gate."""
    return array("h", (int(level * 32767 * math.sin(2 * math.pi * 440 * i / RATE)) for i in range(int(seconds * RATE))))


def b64(samples: array) -> str:
    return base64.b64encode(samples.tobytes()).decode("ascii")


def segment(text: str, nsp: float = 0.0, lp: float = -0.2) -> dict:
    return {"text": text, "no_speech_prob": nsp, "avg_logprob": lp}


def fake_model(provider=WITH_EARS, reply=None, error=None) -> tuple[Model, list]:
    """The real Model, with a fake client whose transcriptions.create() records its call."""
    calls = []

    async def create(**kwargs):
        calls.append(kwargs)
        if error:
            raise error
        return reply or SimpleNamespace(text=" Say hello.", segments=[segment(" Say hello.")])

    model = Model(provider, "fake-key")
    model.client = SimpleNamespace(audio=SimpleNamespace(transcriptions=SimpleNamespace(create=create)))
    return model, calls


# ---------- the recording itself ----------

def test_loudness_in_dbfs() -> None:
    assert loudest_100ms_dbfs(array("h", [0] * RATE)) == -math.inf
    assert -10 < loudest_100ms_dbfs(tone(1.0)) < -8  # a sine's RMS is 0.707 of its peak: 0.5 -> -9 dBFS
    assert loudest_100ms_dbfs(tone(1.0, level=0.004)) < GATE_DBFS
    loud_moment = tone(0.2) + array("h", [0] * RATE * 3)  # 0.2 s of sound in 3 s of silence still counts
    assert loudest_100ms_dbfs(loud_moment) > GATE_DBFS


def test_up_to_30_seconds_is_accepted_and_more_is_refused() -> None:
    assert len(pcm_from_base64(b64(array("h", [1] * int(30.0 * RATE))))) == 30 * RATE
    with pytest.raises(VoiceRefused, match="longer than 30 seconds"):
        pcm_from_base64(b64(array("h", [1] * int(30.6 * RATE))))


@pytest.mark.parametrize("audio, reason", [(None, "no recording"), ("", "no recording"), (42, "no recording"),
                                           ("not base64!", "valid base64"), (base64.b64encode(b"abc").decode(), "16-bit")])
def test_broken_recordings_are_refused(audio, reason: str) -> None:
    with pytest.raises(VoiceRefused, match=reason):
        pcm_from_base64(audio)


def test_the_wav_is_16_khz_mono_16_bit_and_holds_every_sample() -> None:
    samples = tone(0.5)
    data = wav_bytes(samples)
    assert data[:4] == b"RIFF" and data[8:12] == b"WAVE"
    with wave.open(io.BytesIO(data)) as wav:
        assert (wav.getnchannels(), wav.getframerate(), wav.getsampwidth(), wav.getnframes()) == (1, RATE, 2, len(samples))


# ---------- Whisper's silence rule ----------

def test_silent_segments_are_dropped_and_punctuation_alone_is_nothing() -> None:
    reply = SimpleNamespace(text="Open notepad. you", segments=[segment("Open notepad."), segment(" you", 0.77, -1.04)])
    assert kept_text(reply) == "Open notepad."  # M25: clicks came back as "you" at -1.04
    assert kept_text(SimpleNamespace(text=" .", segments=[segment(" .")])) == ""
    assert kept_text(SimpleNamespace(text=" Thank you.", segments=None)) == "Thank you."  # no segments: the text


# ---------- transcribe ----------

@pytest.mark.anyio
async def test_a_clip_goes_to_the_speech_model_in_english_with_no_prompt() -> None:
    model, calls = fake_model()
    heard = await transcribe(model, b64(tone(1.0)))
    assert heard == Heard("Say hello.", "", 1.0, sent=True)
    (call,) = calls
    assert call["model"] == "ears-model" and call["language"] == "en" and call["response_format"] == "verbose_json"
    assert "prompt" not in call  # a prompt of names would send them to the provider
    name, data, kind = call["file"]
    assert name == "speech.wav" and kind == "audio/wav" and data[:4] == b"RIFF"


@pytest.mark.anyio
async def test_a_silent_clip_never_leaves_the_laptop() -> None:
    model, calls = fake_model()
    heard = await transcribe(model, b64(tone(2.0, level=0.004)))
    assert calls == [] and not heard.sent and heard.text == "" and "nothing was sent" in heard.note


@pytest.mark.anyio
async def test_no_words_heard_leaves_the_input_box_alone() -> None:
    model, _ = fake_model(reply=SimpleNamespace(text=" you", segments=[segment(" you", 0.8, -1.2)]))
    heard = await transcribe(model, b64(tone(1.0)))
    assert heard.sent and heard.text == "" and "unchanged" in heard.note


@pytest.mark.anyio
async def test_a_provider_without_a_speech_model_never_gets_voice() -> None:
    for provider in (FAKE_CLOUD, FAKE_LOCAL):
        model, calls = fake_model(provider=provider)
        with pytest.raises(VoiceRefused, match="stays on this laptop"):
            await transcribe(model, b64(tone(1.0)))
        assert calls == []


@pytest.mark.anyio
async def test_a_429_or_an_unreachable_provider_is_a_plain_refusal() -> None:
    model, calls = fake_model(error=rate_limited("7"))
    with pytest.raises(VoiceRefused, match="speech limit was reached; try again in 7 s"):
        await transcribe(model, b64(tone(1.0)))
    assert len(calls) == 1  # no retry and no fallback model (turbo failed M25)
    model, _ = fake_model(error=unreachable())
    with pytest.raises(VoiceRefused, match="could not reach"):
        await transcribe(model, b64(tone(1.0)))


@pytest.mark.anyio
async def test_no_file_is_opened_while_transcribing(monkeypatch: pytest.MonkeyPatch) -> None:
    def no_files(*args, **kwargs):
        raise AssertionError("voice input must never open a file")
    monkeypatch.setattr(builtins, "open", no_files)
    model, calls = fake_model()
    assert (await transcribe(model, b64(tone(1.0)))).text == "Say hello." and len(calls) == 1
