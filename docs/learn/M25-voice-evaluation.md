# M25: How Pseudo should listen and speak (evaluated)

## The concept in one paragraph

Voice is two separate jobs. **Speech to text** (STT) turns a recording of your voice into words; **text to speech** (TTS) turns Pseudo's answer into sound. Each can run in the cloud or on the laptop, and the privacy question is different from everything before: Pseudo redacts *text* before it leaves (D6), but **audio can't be redacted**. A recording of "call Sneha Reddy" contains the name, your voice, and whatever else the microphone heard. So M25 measured, with fake audio only, three ways to listen (two Groq Whisper models and Windows' old built-in recognizer) and two ways to speak (Windows' voices and Groq's Orpheus), against criteria fixed before anything ran. **Result: listen with Groq's `whisper-large-v3`, speak with Windows' own voices.** Your voice goes to Groq, the provider that already gets your typed questions; Pseudo's answers are spoken without leaving the laptop.

## Web-dev analogy

- **Groq's transcription endpoint** is a file-upload API: a `multipart/form-data` POST with a WAV file, returning JSON. Nothing streams; it's one request per push-to-talk.
- **Word error rate (WER)** is a word-level `git diff`: count the words you'd have to change, add or delete to turn the transcript into what was really said, and divide by the number of words really said. It can pass 100% when the transcript adds lots of junk words.
- **The silence gate** is client-side validation: don't submit an empty form. A clip too quiet to contain speech is never uploaded.
- **Whisper's "Thank you." on silence** is like autocomplete that always suggests *something*: the model was trained mostly on speech, so given clicks it produces its most common closing phrase.
- **Push-to-talk vs a wake word** is a submit button vs a page that records every keystroke in case you type the magic word.

## What was built (file by file)

- **`PRD.md`:** Phase 7 (Voice), with M25, M26 and M25's result.
- **`tests/voice_cases.py`** (committed before any audio existed): 26 fake sentences (8 Pseudo commands, 10 with fake Indian names, 8 with Indian English, numbers and codes), 4 non-speech clips and 6 fake answers. Names and numbers are *tagged* so they can be scored on their own.
- **`tests/test_voice_cases.py`:** 7 checks that the tags really appear in their sentences, so a typo can't fake a "wrong name".
- **Scratchpad only** (not committed, like M23): the clip generator, the three STT runners, the TTS runner, the scorer and the `redact()` check. M26 builds the winners properly, with tests.
- **On Windows:** the English (India) voice pack (Heera and Ravi, 79.2 MB), installed with your one admin click.

## Walkthrough of the key code

**1. Making fake audio with Windows voices.** Heera and Ravi installed as *OneCore* voices (Windows' newer voice list), not classic SAPI ones. SAPI can still use them if you point its token list at the OneCore registry key:
```python
cat = win32com.client.Dispatch("SAPI.SpObjectTokenCategory")
cat.SetId(r"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Speech_OneCore\Voices", False)
voice.Voice = token                          # e.g. MSTTS_V110_enIN_HeeraM
fmt.Type = 18                                # SAFT16kHz16BitMono: what Whisper and SAPI both like
```
Each sentence was spoken by Heera, Ravi (Indian English) and Zira (US English), then copied with background noise at **20 dB SNR** (signal-to-noise ratio: the speech is 10× stronger than the noise in amplitude). 156 speech clips, 2.8-7.4 s each.

**2. The Groq call.** The key comes from Pseudo's own config (`load_key`), never by opening `.env`:
```python
client.audio.transcriptions.with_raw_response.create(
    model=model, file=("clip.wav", audio, "audio/wav"), language="en",
    response_format="verbose_json", temperature=0)
```
`language="en"` stops Whisper guessing Hindi from the accent. There is deliberately **no `prompt`**: a prompt listing your contacts' names would improve spelling but send those names to Groq.

**3. The silence rule (fixed before measuring).** Two layers:
```python
return bool(loudest_100ms_dbfs(samples) >= GATE_DBFS)        # -45 dBFS: quieter clips never leave
... if not (s["no_speech_prob"] > 0.6 and s["avg_logprob"] < -1.0)   # Whisper's own defaults
```
**dBFS** means decibels relative to full scale: 0 is the loudest a file can hold, -45 is very quiet. `no_speech_prob` is Whisper's guess that a segment has no speech; `avg_logprob` is how confident it was in the words (closer to 0 = surer).

**4. Scoring.** Names and numbers are scored separately (exact spelling; digits compared without spaces, commas or dashes, so "98765-43210" counts). WER is computed on the *other* words, using an alignment (Levenshtein, the same algorithm as a diff) so a misheard name doesn't also count as two WER errors.

**5. Watching what leaves.** A background thread lists the process's open network connections every 100 ms and reports only counts: "groq" or "other".

## What happens when you run it (real output, annotated)

```
===== S1 (whisper-large-v3-turbo) =====
  WER %: {'en-IN clean': 1.2, 'en-IN noisy': 2.5, ...}
  A2: FAIL  51/92 (55.4%)                           <- names: the faster model hears them worse
  A4: FAIL  {'non_speech_sent': ["V4-clicks: 'Thank you.'"]}   <- a hallucination; no_speech_prob was 0
===== S2 (whisper-large-v3) =====
  WER %: {'en-IN clean': 1.2, 'en-IN noisy': 2.5, 'en-US clean': 1.2, 'en-US noisy': 1.2}
  A2: PASS  68/92 (73.9%)       A3: PASS  31/32     A4: PASS (clicks -> 'you', dropped at -1.04 vs -1.0)
  L1: PASS  {'median': 0.263, 'p90': 0.292}   R2: PASS 7.9 MB   P1: PASS {'remote_groq': 1, 'remote_other': 0}
===== S3 (sapi) =====
  WER %: {'en-IN clean': 62.7, 'en-IN noisy': 108.0, 'en-US clean': 17.3, ...}
  A2: FAIL  2/92 (2.2%)          <- "Keerthana Boddu" -> "the mind me to cordia to the board"
  P2: FAIL  Local/Speech 4 files -> 5 files (+6.3 MB)   <- it keeps recognizer files tuned to what it hears
```
S2's misses are telling: "Kirthana Baudu", "Sneha **ready**", and other spellings of the same name ("Mohammad", "Saurav"), which the exact rule counts wrong. It also never got "Groq" ("Groke", "grog"). The US voice did *worse* on names (63%) than the Indian ones, because a US voice mispronounces them.

```
windows heera A3: 277 chars, first audio 0.045 s     <- Windows voices start almost instantly
Q1 windows heera: 12/295 word errors (4.1%)          <- spoken answers, transcribed back
Orpheus access: refused, HTTP 400 ... 'code': 'model_terms_required'
redact(): sentences changed 12/26 | name words masked 23/23
  V2-03: [PERSON] the notes from today's class.       <- "Send S. Ramesh" lost the verb too
  V3-05: Pay 2500 rupees through [LOCATION] for the hostel fees.   <- "UPI" over-masked
```

**The privacy answer.** With S2, your recorded clip goes to Groq: no training (§4.2), kept only in troubleshooting or abuse logs for up to 30 days, or not at all with Zero Data Retention (a console setting). Redacting the *transcript* before the chat call would hide nothing from Groq (it heard the audio) and would break 12 of 26 commands, so the transcript is treated like typed text (L8) and shown in the input box first. Memory still redacts on save (D23).

## Try this

1. In a Python shell (`.venv\Scripts\python`): `import win32com.client; v = win32com.client.Dispatch("SAPI.SpVoice"); v.Speak("Remind me to call Keerthana Boddu")`. Then switch `v.Voice` to Heera's token (snippet 1 above) and say it again. Which pronunciation would you expect Whisper to spell right?
2. Work out the WER of "Focus the note pad window" against "Focus the Notepad window" by hand. Then explain how S3 reached 108% on noisy clips.
3. Generate "Switch to the Groq fallback model" with Heera into a WAV, and send it to Groq twice: without a prompt, then with `prompt="Groq, Pseudo"`. Why is a prompt of *Pseudo's own words* safe, when a prompt of your contacts' names is not?

## Check yourself

1. Why can't Pseudo redact audio the way it redacts window text?
2. S1 and S2 had the same word error rate. Why did S1 still fail?
3. Why wasn't the transcript run through `redact()` before reaching the model?
4. Windows' recognizer sent nothing over the network. Why did it still fail privacy?
5. Why push-to-talk first, and not a wake word?

<details>
<summary>Answers</summary>

1. Redaction works on text: find "Sneha Reddy", replace it with [PERSON]. Audio is a waveform; the name, your voice and the room are all mixed into it, and turning it into text *is* the transcription, which happens on Groq. So the protection is limiting *when* audio is recorded (push-to-talk, a 30 s cap, a silence gate) and *who* gets it (only a D16 provider).
2. Names and silence. S1 got 55% of name words (the bar was 70%), and it turned a clicks clip into "Thank you." with full confidence, which would have been sent as a message. WER on ordinary words hides both.
3. Groq already received the audio, so masking the transcript hides nothing from Groq; and `redact()` changed 12 of 26 commands ("call [PERSON]" can't be done). Like typed text (L8), you see the transcript in the input box before it's sent.
4. P2: it writes recognizer files tuned to the voices it hears into your profile (+6.3 MB in one run), data derived from your voice that stays on disk. Plus 62.7% WER on Indian English, +111 MB of RAM, and it's deprecated.
5. A wake word means the microphone is always on. Detecting the word locally needs a local model (D20 says no), and streaming everything to the cloud would send every conversation in the room. Push-to-talk records only while you hold the key.
</details>

## How this connects to Pseudo's final architecture

M26 builds what won, in the same layers as everything else (D11):
- **The face** gets a mic button and a hold-to-talk key. It opens the microphone only while recording, and its permission handler (today it denies everything) allows the microphone and nothing else.
- **`pseudo_brain`** sends the clip to `whisper-large-v3` through the D16 allowlist, so Groq stays the only company involved. It applies the silence gate first, and puts the transcript in the input box.
- **Windows voices** speak the answer through SAPI with pywin32 (already installed: no new dependency, no network).

Because T1 is a Windows option, D20 gains one clarifying line: Windows' own speech features are allowed, like the redactor, because they're part of the OS and stayed within the RAM budget.
