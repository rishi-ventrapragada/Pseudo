// M26: push-to-talk and spoken answers, for App. This opens the microphone and plays sound; the rules
// (the 30-second limit, the silence gate, which provider may hear you) are in the brain (bridge_voice.py, D24).
//   - Talking: the mic button toggles; holding Ctrl+Space talks while held. Starting stops any speech
//     first, so Pseudo never hears itself. Leaving the window while holding the key also stops.
//   - Speaking: each spoken answer from the brain is played unless Speak answers is off. The switch is
//     remembered by this window (localStorage) and told to the brain, so a muted answer isn't even made.

import { useEffect, useRef, useState } from 'react';
import { isTalkKey, startsTalking, stopsTalking } from './pushToTalk';
import { startRecording, type Recording } from './recorder';
import * as speaker from './speaker';

const SAVED = 'pseudo.speakAnswers';

function savedSpeakOn(): boolean {
  try {
    return localStorage.getItem(SAVED) !== 'off'; // on unless you turned it off (D24)
  } catch {
    return true; // storage blocked: the default
  }
}

export type Voice = {
  listening: boolean;
  seconds: number; // how long this recording has run
  speaking: boolean;
  speakOn: boolean;
  problem: string; // the last thing that went wrong here, in plain words ('' = none)
  toggle(): void;
  setSpeakOn(on: boolean): void;
  stopSpeaking(): void;
};

type Options = {
  canTalk: boolean; // idle, on a provider with a speech model
  ready: boolean; // the brain is running: tell it the Speak answers choice
  speech: { audio: string; n: number } | null;
  onRecorded(audio: string): void;
};

export function useVoice({ canTalk, ready, speech, onRecorded }: Options): Voice {
  const [listening, setListening] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [speaking, setSpeaking] = useState(false);
  const [speakOn, setSpeakOnState] = useState(savedSpeakOn);
  const [problem, setProblem] = useState('');
  const recording = useRef<Promise<Recording | null> | null>(null); // set while the mic is open (or opening)
  const byKey = useRef(false); // started with Ctrl+Space: letting go stops it
  const now = useRef({ canTalk, onRecorded, speakOn }); // the latest values, for the key handlers below
  now.current = { canTalk, onRecorded, speakOn };

  function stopSpeaking() {
    speaker.stop();
    setSpeaking(false);
  }

  function start(withKey: boolean) {
    if (recording.current || !now.current.canTalk) return;
    stopSpeaking();
    setProblem('');
    setListening(true);
    byKey.current = withKey;
    recording.current = startRecording(() => void stop()).catch((error: Error) => {
      setProblem(`Couldn't open the microphone: ${error.message}`);
      setListening(false);
      recording.current = null;
      return null;
    });
  }

  async function stop() {
    const opening = recording.current;
    if (!opening) return;
    recording.current = null;
    setListening(false);
    const opened = await opening; // if the mic was still opening, it's stopped as soon as it opens
    const audio = opened ? await opened.stop() : '';
    if (audio) now.current.onRecorded(audio);
    else if (opened) setProblem('Nothing was recorded.');
  }

  const handlers = useRef({ start, stop });
  handlers.current = { start, stop };

  useEffect(() => { // Ctrl+Space, anywhere in this window
    const down = (event: KeyboardEvent) => {
      if (!isTalkKey(event)) return;
      event.preventDefault(); // never type the space, not even the repeats
      if (startsTalking(event)) handlers.current.start(true);
    };
    const up = (event: KeyboardEvent) => {
      if (byKey.current && stopsTalking(event)) void handlers.current.stop();
    };
    const left = () => { // the key's release would happen in another window
      if (byKey.current) void handlers.current.stop();
    };
    window.addEventListener('keydown', down);
    window.addEventListener('keyup', up);
    window.addEventListener('blur', left);
    return () => {
      window.removeEventListener('keydown', down);
      window.removeEventListener('keyup', up);
      window.removeEventListener('blur', left);
      speaker.stop();
    };
  }, []);

  useEffect(() => { // the clock on the mic button
    if (!listening) return;
    const began = Date.now();
    setSeconds(0);
    const timer = window.setInterval(() => setSeconds((Date.now() - began) / 1000), 250);
    return () => window.clearInterval(timer);
  }, [listening]);

  useEffect(() => { // every (re)started brain hears the remembered choice
    if (ready) window.pseudo.send({ type: 'speak_answers', on: now.current.speakOn });
  }, [ready]);

  useEffect(() => { // a new spoken answer
    if (!speech || !now.current.speakOn || recording.current) return;
    setSpeaking(true);
    speaker.play(speech.audio, () => setSpeaking(false)).catch(() => {
      setSpeaking(false);
      setProblem("Couldn't play the spoken answer.");
    });
  }, [speech?.n]);

  function setSpeakOn(on: boolean) {
    setSpeakOnState(on);
    try {
      localStorage.setItem(SAVED, on ? 'on' : 'off');
    } catch {
      // storage blocked: the choice lasts until the window closes
    }
    window.pseudo.send({ type: 'speak_answers', on });
    if (!on) stopSpeaking();
  }

  return {
    listening, seconds, speaking, speakOn, problem, setSpeakOn, stopSpeaking,
    toggle: () => (recording.current ? void stop() : start(false)),
  };
}
