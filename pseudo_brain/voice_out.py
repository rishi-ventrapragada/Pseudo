"""M26: spoken answers. Pseudo's answer becomes speech, with a Windows voice, on this laptop (D24).

What it demonstrates: text to speech through SAPI, Windows' own speech API, called from Python
through pywin32's COM support (COM is how Windows lets programs use each other's objects).
Nothing leaves the laptop: the voice runs here, and the sound is made in memory.
  - The voice is Ravi, English (India). In M25 it had the fewest round-trip errors of the Indian
    voices (3.7%). Ravi and Heera come from an optional Windows voice pack. They are "OneCore"
    voices, Windows' newer list, which SAPI can still use when pointed at that list (M25).
  - spoken_text() turns an answer into something worth hearing: Markdown symbols go, a
    placeholder like [PERSON] is read as "a name", and only the first 1,500 characters are read.
  - synthesize() returns a WAV file in memory (SpMemoryStream), never on disk. pseudo_brain sends
    it to the face, which plays it. It runs in a worker thread, so COM is set up for that thread
    and released after.
  - The answer comes from a cloud model, so it is never read as SAPI voice commands (SVSFIsNotXML).
    With SAPI's default flag, an answer starting with <silence msec="20000"/> added 20 s of silence.
  - A missing voice is refused with a reason, never swapped for another one silently.
"""

import re
from array import array

import pythoncom
import pywintypes
import win32com.client

from pseudo_brain.voice_in import wav_bytes

VOICE = "MSTTS_V110_enIN_RaviM"  # or MSTTS_V110_enIN_HeeraM (English (India)), MSTTS_V110_enUS_ZiraM
ONECORE_VOICES = r"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Speech_OneCore\Voices"
SAFT_16K_16BIT_MONO = 18  # SAPI's code for the format Pseudo uses everywhere: 16 kHz, mono, 16-bit
SVSF_IS_NOT_XML = 16  # read the text as text, never as SAPI's XML voice commands
MAX_CHARS = 1500
REST = "The rest is on screen."
SPOKEN_LABELS = {  # the redactor's placeholders, as words; anything else is "a hidden detail"
    "PERSON": "a name", "LOCATION": "a place", "ORGANIZATION": "an organisation", "PRIVATE": "a private term",
    "PHONE_NUMBER": "a phone number", "IN_PHONE": "a phone number", "EMAIL_ADDRESS": "an email address",
    "DATE_TIME": "a date", "DATE": "a date", "AGE": "an age", "URL": "a link", "IN_UPI": "a UPI ID",
    "IN_AADHAAR": "an Aadhaar number", "IN_PAN": "a PAN number", "CREDIT_CARD": "a card number",
    "LONG_NUMBER": "a long number", "IN_VEHICLE_REGISTRATION": "a vehicle number",
}


class VoiceUnavailable(Exception):
    """Windows can't speak right now (the voice isn't installed, or SAPI failed). The message says why."""


def spoken_text(answer: str) -> str:
    """An answer as it should sound: plain sentences, placeholders as words, at most MAX_CHARS (+ REST)."""
    text = re.sub(r"```.*?```", " There's code on screen. ", answer, flags=re.S)  # code blocks aren't read out
    text = re.sub(r"`([^`]*)`", r"\1", text)  # `inline code` -> its text
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", text)  # [link text](url) -> link text
    text = re.sub(r"\[([A-Z_]+)\]", lambda m: SPOKEN_LABELS.get(m.group(1), "a hidden detail"), text)
    text = re.sub(r"^\s*(?:#{1,6}|[-*+]|\d+[.)]|>)\s+", "", text, flags=re.M)  # headings, list markers, quotes
    text = re.sub(r"[*_~|#]+", " ", text)  # bold, italics, strikethrough, table bars
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > MAX_CHARS:
        cut = text.rfind(". ", 0, MAX_CHARS)  # stop at the last full sentence that fits
        text = text[:cut + 1 if cut > 0 else MAX_CHARS].rstrip() + " " + REST
    return text


def find_voice(voice_id: str):
    """The SAPI token of an installed OneCore voice. VoiceUnavailable if it isn't installed."""
    category = win32com.client.Dispatch("SAPI.SpObjectTokenCategory")
    category.SetId(ONECORE_VOICES, False)
    tokens = category.EnumerateTokens()
    for index in range(tokens.Count):
        token = tokens.Item(index)
        if token.Id.endswith("\\" + voice_id):
            return token
    raise VoiceUnavailable(f"the Windows voice {voice_id} isn't installed "
                           "(Settings > Time & language > Speech > Add voices)")


def speak_to_memory(text: str, voice_id: str) -> bytes:
    """SAPI speaks into a memory stream instead of the speakers. Returns the raw 16-bit samples."""
    voice = win32com.client.Dispatch("SAPI.SpVoice")
    voice.Voice = find_voice(voice_id)
    audio_format = win32com.client.Dispatch("SAPI.SpAudioFormat")
    audio_format.Type = SAFT_16K_16BIT_MONO
    stream = win32com.client.Dispatch("SAPI.SpMemoryStream")
    stream.Format = audio_format
    voice.AudioOutputStream = stream
    voice.Speak(text, SVSF_IS_NOT_XML)  # synchronous: returns when the whole text is in the stream
    return bytes(stream.GetData())


def synthesize(text: str, voice_id: str = VOICE) -> bytes:
    """Text -> a WAV file in memory (16 kHz mono 16-bit). Meant for a worker thread (anyio.to_thread)."""
    pythoncom.CoInitialize()  # COM must be set up in every thread that uses it
    try:
        raw = speak_to_memory(text, voice_id)  # its COM objects are released when it returns, before the line below
    except pywintypes.com_error:
        raise VoiceUnavailable("Windows couldn't speak the answer (SAPI failed)") from None
    finally:
        pythoncom.CoUninitialize()
    samples = array("h")
    samples.frombytes(raw[:len(raw) // 2 * 2])
    return wav_bytes(samples)
