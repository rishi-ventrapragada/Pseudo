"""M26: voice over the bridge. Push-to-talk recordings come in; spoken answers go out (D24).

What it demonstrates: keeping a growing protocol readable. bridge.py stays the router; the voice
messages are handled here; the rules live in voice_in.py and voice_out.py (D11).

Face -> brain:  transcribe {audio}       one push-to-talk recording (base64 PCM: 16 kHz, mono, 16-bit).
                                         A JOB, like ask: refused while a question is running.
                speak_answers {on}       spoken answers on (true) or off (false); the face remembers it
Brain -> face:  transcript {text, note, seconds}   the words go into the input box; NEVER sent by themselves (L8)
                speech {audio, reason}   an answer as a WAV file (base64) for the face to play;
                                         or no audio, and the reason Windows couldn't speak it

Rules:
  - Recordings and speech exist only in memory: never written to disk, never kept in sessions or memory.
  - The log (stderr) gets counts only: seconds, characters, sent or not. Never the words, never the audio.
  - An answer is spoken as soon as its `answer` event arrives, in the background, so it isn't held
    up by the memory popup that follows it (M24).
  - A failure to speak never fails the question: the answer is already on screen.
"""

import base64
import sys

import anyio

from pseudo_brain.voice_in import VoiceRefused, transcribe
from pseudo_brain.voice_out import VoiceUnavailable, spoken_text, synthesize

VOICE_REFUSALS = (VoiceRefused,)  # the job's handler reports these as `refused`, like the chat's REFUSALS
WAV_HEADER_BYTES = 44
BYTES_PER_SECOND = 16000 * 2  # 16 kHz, 16-bit, mono


def log(line: str) -> None:
    print(f"voice: {line}", file=sys.stderr, flush=True)


async def transcribe_job(bridge, message: dict) -> None:
    """The `transcribe` job: one recording -> one `transcript` message. Raises VoiceRefused."""
    heard = await transcribe(bridge.chat.model, message.get("audio"))
    where = f"sent to {bridge.chat.provider.name}" if heard.sent else "not sent (too quiet)"
    log(f"{heard.seconds:.1f} s recording, {where}, {len(heard.text)} characters heard")
    bridge.send("transcript", text=heard.text, note=heard.note, seconds=heard.seconds)


def set_speaking(bridge, message: dict) -> None:
    """`speak_answers {on}`: anything but a real true/false is ignored."""
    if isinstance(message.get("on"), bool):
        bridge.speak_answers = message["on"]
        log(f"spoken answers {'on' if bridge.speak_answers else 'off'}")


def on_answer(bridge, data: dict) -> None:
    """Called for every `answer` event: if speaking is on, speak it in the background."""
    text = data.get("text")
    if bridge.speak_answers and bridge.tasks is not None and isinstance(text, str) and text.strip():
        bridge.tasks.start_soon(speak, bridge, text)


async def speak(bridge, answer: str) -> None:
    """Make the answer's speech in a worker thread (SAPI), then send it to the face to play."""
    text = spoken_text(answer)
    try:
        wav = await anyio.to_thread.run_sync(synthesize, text)
    except VoiceUnavailable as missing:
        log("could not speak an answer")
        bridge.send("speech", audio="", reason=str(missing))
        return
    log(f"spoke 1 answer: {len(text)} characters, {(len(wav) - WAV_HEADER_BYTES) / BYTES_PER_SECOND:.1f} s of audio")
    bridge.send("speech", audio=base64.b64encode(wav).decode("ascii"), reason="")
