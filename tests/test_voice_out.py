"""Tests for M26: spoken answers (pseudo_brain/voice_out.py, D24).

All text is FAKE. The last test uses the real Windows voice, silently: SAPI speaks into memory,
never to the speakers, and no microphone or window is involved. It is skipped if the English
(India) voice pack has been removed.
"""

import io
import wave

import anyio
import pytest

from pseudo_brain.voice_out import MAX_CHARS, REST, VOICE, VoiceUnavailable, find_voice, spoken_text, synthesize


def test_markdown_is_not_read_out() -> None:
    answer = "## Summary\n**Two** windows are open:\n- `Notepad`\n- [Chrome](https://example.invalid)\n1. Done"
    assert spoken_text(answer) == "Summary Two windows are open: Notepad Chrome Done"
    assert spoken_text("Run this:\n```\nnpm start\n```\nthen wait.") == "Run this: There's code on screen. then wait."


def test_placeholders_are_read_as_words() -> None:
    said = spoken_text("Meeting with [PERSON] in [LOCATION]; call [IN_PHONE]. Code [SOMETHING_NEW].")
    assert said == "Meeting with a name in a place; call a phone number. Code a hidden detail."


def test_long_answers_stop_at_a_sentence_and_say_so() -> None:
    answer = "This is one fake sentence. " * 100  # 2,700 characters
    said = spoken_text(answer)
    assert said.endswith(". " + REST) and len(said) <= MAX_CHARS + len(REST) + 1
    assert spoken_text("Short answer.") == "Short answer."


def test_a_missing_voice_is_refused_with_a_reason() -> None:
    with pytest.raises(VoiceUnavailable, match="isn't installed"):
        find_voice("MSTTS_V110_xxXX_NoSuchVoiceM")


@pytest.mark.anyio
async def test_the_real_voice_speaks_into_memory_in_a_worker_thread() -> None:
    """Silent: SAPI writes into memory. An answer that STARTS with a SAPI command is read as text: SAPI's
    default flag would obey it (measured: 21.2 s with the 20 s of silence, 5.0 s read as text)."""
    try:
        data = await anyio.to_thread.run_sync(synthesize, '<silence msec="20000"/>Hello.')
    except VoiceUnavailable as missing:
        pytest.skip(str(missing))
    with wave.open(io.BytesIO(data)) as wav:
        seconds = wav.getnframes() / wav.getframerate()
        assert (wav.getnchannels(), wav.getframerate(), wav.getsampwidth()) == (1, 16000, 2)
    assert 0.3 < seconds < 15, seconds
    assert VOICE.startswith("MSTTS_V110_enIN_")  # D24: an English (India) voice by default
