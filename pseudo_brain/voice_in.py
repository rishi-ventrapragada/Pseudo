"""M26: voice input. A push-to-talk recording becomes words, through the provider's speech model (D24).

What it demonstrates: privacy rules for AUDIO. Text can be redacted before it leaves the laptop;
a recording can't (M25): your voice, the names you say and the room are all mixed into it. So
the rules decide WHETHER a recording leaves at all, and how much of it:
  - It arrives from the face as base64 PCM: 16,000 samples a second, mono, 16-bit (what
    Whisper hears best). More than 30 seconds is refused. The face stops at 30; this rule
    holds even if a face didn't.
  - A recording whose loudest 100 ms is quieter than -45 dBFS is never sent: silence stays here.
  - Only a provider with a transcribe_model gets voice (providers.toml), so private mode never
    sends it anywhere. Whisper gets language="en" and never a prompt: a prompt listing your
    contacts' names would improve their spelling, and send them to Groq.
  - Whisper's own silence rule drops a segment with no_speech_prob > 0.6 and avg_logprob < -1.0,
    so a "Thank you." heard in keyboard clicks doesn't become your question (M25).
  - The WAV file is built in memory (BytesIO): no recording is ever written to disk.
  - A 429 is reported with the wait. There is no fallback model: turbo failed M25.
Nothing here prints; the Heard result says what happened.
"""

import base64
import binascii
import io
import math
import wave
from array import array
from dataclasses import dataclass
from itertools import accumulate

import openai

from pseudo_brain.model import Model, retry_after

RATE = 16000  # samples per second
MAX_SECONDS = 30.0
SLACK_SECONDS = 0.5  # the face's timer and its encoder can run a few milliseconds over
MAX_BYTES = int((MAX_SECONDS + SLACK_SECONDS) * RATE) * 2  # 2 bytes per 16-bit sample
GATE_DBFS = -45.0  # dBFS: decibels below the loudest sound a file can hold (0)
WINDOW = RATE // 10  # 100 ms of samples
FULL_SCALE = 32768  # the largest 16-bit sample


class VoiceRefused(Exception):
    """This recording can't be used, or voice is off for this provider. The message says why."""


@dataclass(frozen=True)
class Heard:
    text: str  # what goes into the input box; "" = nothing
    note: str  # plain words for the face when there's no text
    seconds: float
    sent: bool  # did the recording leave the laptop?


def pcm_from_base64(audio: object) -> array:
    """The face's base64 text -> 16-bit samples. VoiceRefused if it isn't a usable recording."""
    if not isinstance(audio, str) or not audio:
        raise VoiceRefused("there is no recording")
    if len(audio) > (MAX_BYTES + 2) // 3 * 4:  # checked BEFORE decoding: base64 is 4 characters per 3 bytes
        raise VoiceRefused(f"the recording is longer than {MAX_SECONDS:.0f} seconds, so it wasn't sent")
    try:
        raw = base64.b64decode(audio, validate=True)
    except (binascii.Error, ValueError):
        raise VoiceRefused("the recording isn't valid base64") from None
    if len(raw) % 2:
        raise VoiceRefused("the recording isn't 16-bit audio")
    if len(raw) > MAX_BYTES:
        raise VoiceRefused(f"the recording is longer than {MAX_SECONDS:.0f} seconds, so it wasn't sent")
    samples = array("h")
    samples.frombytes(raw)  # little-endian, as Windows on x86 stores them
    return samples


def loudest_100ms_dbfs(samples: array) -> float:
    """How loud the loudest 100 ms is (RMS, in dBFS), checked every 50 ms. Silence -> -inf."""
    if not samples:
        return -math.inf
    win = min(WINDOW, len(samples))
    energy = list(accumulate((s * s for s in samples), initial=0))  # running total of squared samples
    best = max(energy[i + win] - energy[i] for i in range(0, len(samples) - win + 1, WINDOW // 2))
    rms = math.sqrt(best / win) / FULL_SCALE
    return 20 * math.log10(rms) if rms > 0 else -math.inf


def wav_bytes(samples: array) -> bytes:
    """A WAV file, in memory: a 44-byte header that says 16 kHz mono 16-bit, then the samples."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(RATE)
        wav.writeframes(samples.tobytes())
    return buffer.getvalue()


def field(segment, name: str):
    return segment[name] if isinstance(segment, dict) else getattr(segment, name)


def kept_text(response) -> str:
    """The words Whisper heard, minus segments it judged silent. Punctuation alone counts as nothing."""
    segments = getattr(response, "segments", None)
    if segments:
        text = " ".join(str(field(s, "text")).strip() for s in segments
                        if not (field(s, "no_speech_prob") > 0.6 and field(s, "avg_logprob") < -1.0))
    else:
        text = str(getattr(response, "text", "") or "")
    text = text.strip()
    return text if any(char.isalnum() for char in text) else ""


async def transcribe(model: Model, audio: object) -> Heard:
    """One push-to-talk recording -> Heard. Raises VoiceRefused if it can't or mustn't be sent."""
    provider = model.provider
    if not provider.transcribe_model:
        raise VoiceRefused(f"voice input isn't available on {provider.name}: it has no speech model, "
                           "so your voice stays on this laptop")
    samples = pcm_from_base64(audio)
    seconds = round(len(samples) / RATE, 2)
    if loudest_100ms_dbfs(samples) < GATE_DBFS:
        return Heard("", "Didn't hear anything, so nothing was sent.", seconds, sent=False)
    try:
        response = await model.client.audio.transcriptions.create(
            model=provider.transcribe_model, file=("speech.wav", wav_bytes(samples), "audio/wav"),
            language="en", response_format="verbose_json", temperature=0)
    except openai.RateLimitError as error:
        wait = retry_after(error)
        raise VoiceRefused(f"{provider.name}'s speech limit was reached; try again in {wait:.0f} s") from None
    except openai.APIConnectionError:
        raise VoiceRefused(f"could not reach {provider.name} to transcribe the recording") from None
    except openai.APIStatusError as error:
        raise VoiceRefused(f"{provider.name} refused the recording ({error.status_code})") from None
    text = kept_text(response)
    return Heard(text, "" if text else "Heard no words, so the input box is unchanged.", seconds, sent=True)
