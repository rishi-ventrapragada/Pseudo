# M26: Talk to Pseudo, and hear it answer

## The concept in one paragraph

M25 decided *what* Pseudo uses for voice: Groq's `whisper-large-v3` listens, and Windows' own voices speak (D24). M26 builds it across the same layers as everything else (D11).
- **The face is the device layer.** It opens the **microphone**, the hardware that records your voice, only while you hold Ctrl+Space or after you click the mic button. It plays the answers through the speakers.
- **`pseudo_brain` holds the rules.** It refuses anything longer than 30 seconds and never sends silence. Only a provider with a speech model hears you, and the recording is never written to disk.
- **The transcript isn't a question.** The words come back into the input box, and you still press Enter, exactly as if you had typed them (L8).

Verifying all this without ever opening the real microphone took a trick: Chromium's **fake microphone**, which plays a WAV file as if it were a mic.

## Web-dev analogy

- **`getUserMedia` + `MediaRecorder`** is exactly what a web app's "record a voice note" button uses. The page is still the same React page; it now has a mic.
- **`permissions.js`** is the browser's "Allow microphone?" prompt, answered by code. In Electron *we* are the browser, so we decide which pages may ask. Here that's only `app://pseudo`, and only for audio.
- **Base64 audio in a JSON line** is like uploading a file as a data URL in a JSON body. Binary bytes become text so they can travel down a text pipe.
- **`OfflineAudioContext`** resamples audio off-screen, like drawing an image onto a hidden canvas to resize it. 48,000 samples a second go in; 16,000 come out.
- **The transcript in the input box** works like autofill: it fills the field, and you still click Submit.

## What was built (file by file)

- **`pseudo_brain/providers.toml` + `providers.py`:** Groq gets `transcribe_model = "whisper-large-v3"`. A private provider can never have one (D20), so private mode has no voice input. `model.py`'s startup check also confirms Groq still lists the speech model.
- **`pseudo_brain/voice_in.py`:** recording in, words out. It handles base64 → 16-bit samples, the 30 s cap, the −45 dBFS silence gate, the WAV built in memory, and the Groq call with Whisper's own silence rule.
- **`pseudo_brain/voice_out.py`:** answer in, speech out. It strips Markdown, reads `[PERSON]` as "a name", stops after 1,500 characters, and has Windows' Ravi voice speak into a memory stream.
- **`pseudo_brain/bridge_voice.py`:** the new pipe messages. `transcribe {audio}` is a job, like `ask`. `speak_answers {on}` is the mute switch. `transcript` and `speech` go back to the face.
- **`face/permissions.js`:** the one permission the page can get.
- **`face/src/recorder.ts`, `speaker.ts`, `audio.ts`, `pushToTalk.ts`, `useVoice.ts`, `VoiceControls.tsx`:** record, play, convert, the Ctrl+Space key, the wiring, and the buttons.
- **Tests:** 30 new pytest and 11 new vitest tests. They run silently, except for one SAPI test that speaks into memory.

## Walkthrough of the key code

**1. The only permission** (`face/permissions.js`):
```js
return permission === 'media' && Array.isArray(types) && types.length > 0
  && types.every((type) => type === 'audio') && isOurPage(details.requestingUrl);
```
`every` matters. A request for microphone *and* camera is refused whole, rather than half-granted.

**2. The mic is released the moment you stop** (`recorder.ts`):
```ts
stream.getTracks().forEach((track) => track.stop()); // the microphone is released HERE
```
Until this line runs, Windows shows its "microphone in use" icon. After it, the mic is closed. The recording then becomes 16 kHz mono PCM through an `OfflineAudioContext`, and goes over the pipe as base64.

**3. Silence never leaves the laptop** (`voice_in.py`):
```python
if loudest_100ms_dbfs(samples) < GATE_DBFS:
    return Heard("", "Didn't hear anything, so nothing was sent.", seconds, sent=False)
```
- **dBFS** is "decibels below full scale": 0 is as loud as a file can be, and −45 is a quiet room.
- **The loudness is checked with a running total** of squared samples (`itertools.accumulate`). That makes any 100 ms window one subtraction instead of 1,600 additions, so a full 30 s clip takes 68 ms in pure Python.
- **There's no `audioop`:** that standard module was removed in Python 3.13.

**4. The Groq call** (`voice_in.py`):
```python
await model.client.audio.transcriptions.create(
    model=provider.transcribe_model, file=("speech.wav", wav_bytes(samples), "audio/wav"),
    language="en", response_format="verbose_json", temperature=0)
```
It reuses the chat's own client (the same key, the same company). There is no `prompt`: a test fails if one is ever added.

**5. An answer is text, never voice commands** (`voice_out.py`):
```python
voice.Speak(text, SVSF_IS_NOT_XML)
```
SAPI's default treats text that *starts* with `<` as XML commands. An answer starting with `<silence msec="20000"/>` produced 21.2 s of audio with the default flag, and 5.0 s with this one, where it's read as text. The answer comes from a cloud model, so it must never control the voice. The first version of the test put the tag in the middle, and it passed with *both* flags. A test has to fail when the protection is removed, or it proves nothing.

**6. Speak without waiting for the popup** (`bridge_voice.py`):
```python
if bridge.speak_answers and bridge.tasks is not None and isinstance(text, str) and text.strip():
    bridge.tasks.start_soon(speak, bridge, text)
```
After an answer, M24's memory popup can wait up to 20 s. Speaking in the background, as soon as the `answer` event arrives, means you hear the answer at once.

## What happens when you run it (real output, annotated)

Run on the real face with real Groq. Chromium's fake mic played a fake WAV of Heera saying the question.
```
V1 button:     {'heard': 'Say hello to me in one short sentence.', 'words_matched': '100%'}
V3 not sent by itself: {'turns': 0, 'box still holds it': True}       <- L8: you press Enter, not the mic
V2 Ctrl+Space: {'heard': 'Say hello to me in one short sentence.', 'words_matched': '100%', 'no_stray_space': True}
V4 answered and spoken: {'answer': '... Hello!', 'speaking shown': True, 'spoke lines +': 1}
V5 muted:      {'switch off': True, 'brain told': True, 'speaking shown': False, 'spoke lines +': 0}
V6 silence:    {'face says nothing was sent': True, 'log': ['3.1 s recording, not sent (too quiet), 0 characters heard']}
V7 30 s cap:   {'recording started': True, 'stopped by itself': True, 'log': ['30.0 s recording, not sent (too quiet), ...']}
V9 outside connections: {'python.exe -m pseudo_brain.bridge': {'groq': 2, ..., 'other': 0}}   <- the face: none
V8 audio files (changed, audio): (131, 0)       V10 real mic record unchanged: True
V11 RAM MB: {'before': {'renderer': 80.4, 'bridge': 96.3}, 'after': {'renderer': 98.7, 'bridge': 108.9}}
```
Three surprises along the way, all in the *test*, not in Pseudo:
- **Ctrl+Space did nothing at first.** The script sent keys without **scan codes** (the key's physical position), and Chromium's `event.code` ("Space") comes from the scan code. Real keyboards always send one.
- **The first V7 "passed" falsely.** It read the mic button's old name before the screen updated. Now it waits for "Stop talking" first, and also needs the "30.0 s" log line.
- **V9 showed 3 "other" addresses.** `api.groq.com` rotates between several addresses, so the check now resolves it every 2 s.

**One real bug, not caused by M26.** The memory popup opened *behind* the face. The same thing happened with speech off and with a real Enter key. A snapshot of the code from before M26 behaved identically, so it predates voice. It's safe, because an unseen popup times out as no, but it needs its own fix.

## Try this

1. In `voice_in.py`, set `GATE_DBFS = -5.0` and run `pytest tests/test_voice_in.py`. Which tests fail, and why does a loud tone (−9 dBFS) now count as silence? Put it back.
2. In `face/permissions.js`, change `every` to `some` and run `npm test` in `face`. Which test catches the camera getting in?
3. In `voice_out.py`, set `VOICE = "MSTTS_V110_enUS_ZiraM"`, start the face, and ask something. Compare Ravi's and Zira's readings of an Indian name, then put it back.

## Check yourself

1. Why does the face send raw PCM instead of the WebM file `MediaRecorder` makes?
2. The face stops at 30 s. Why does `voice_in.py` check the length again?
3. Why does the transcript go into the input box instead of straight to the model?
4. Why is the answer spoken with `SVSF_IS_NOT_XML`, and how do you know the test proves it?
5. How was it shown that the memory popup opening behind the face wasn't caused by M26?

<details>
<summary>Answers</summary>

1. The brain has to measure loudness (the silence gate) before anything is sent. Python has no Opus decoder built in, and adding one would be a new dependency. PCM is just numbers, so `array` reads it directly, and 16 kHz mono is what Whisper hears best.
2. Safety lives next to the tool, not in the interface (D11). A different face, a bug, or a crafted message could skip the face's timer; the brain's check can't be skipped. `main.js` drops oversized audio too.
3. Speech recognition makes mistakes ("Groq" became "Groke"), and a wrong name could start the wrong task. In the box you see exactly what will be sent, fix it, and press Enter, just as with typed text (L8).
4. The answer comes from a cloud model. With SAPI's default flag, text starting with an XML tag is obeyed as voice commands. The test puts `<silence msec="20000"/>` first: with the default flag it produced 21.2 s of audio, with ours 5.0 s. Remove the flag and the test fails.
5. It happened with speech off and with a real Enter, so voice wasn't involved. The code from before M26, exported with `git archive` into a temp folder, did exactly the same.
</details>

## How this connects to Pseudo's final architecture

- **The pattern is now complete.** The face handles devices (screen, keyboard, mic, speakers), `pseudo_brain` holds the rules and the provider calls, and `pseudo_hands` holds the tools, redaction and approval. Swapping the face or the speech model touches one layer.
- **Voice reaches the cloud only through the D16 allowlist.** Spoken answers never leave the laptop.
- **Next on the roadmap is click-and-type control (step 8).** There, the approval popup has to be seen, so the "popup behind the face" bug matters before then.
