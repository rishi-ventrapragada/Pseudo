// M32: the warm-session switch, for App. The window REMEMBERS it (localStorage, like Speak answers in
// useVoice.ts) and tells every brain it starts: a brain keeps warm sessions off until it is told on.
// When a session opens, restarts and stops is decided in the brain (pseudo_brain/warm_sessions.py).

import { useEffect, useRef, useState } from 'react';

const SAVED = 'pseudo.warmSessions';

/** The remembered choice: on unless you turned it off. */
export function savedWarmOn(): boolean {
  try {
    return localStorage.getItem(SAVED) !== 'off';
  } catch {
    return true; // storage blocked: the default
  }
}

export function saveWarmOn(on: boolean): void {
  try {
    localStorage.setItem(SAVED, on ? 'on' : 'off');
  } catch {
    // storage blocked: the choice lasts until the window closes
  }
}

/** `ready`: the brain is running, so it can be told. */
export function useWarm(ready: boolean): { warmOn: boolean; setWarmOn(on: boolean): void } {
  const [warmOn, setWarmOnState] = useState(savedWarmOn);
  const now = useRef(warmOn); // the latest value, for the effect below
  now.current = warmOn;

  useEffect(() => { // every (re)started brain hears the remembered choice
    if (ready) window.pseudo.send({ type: 'warm_sessions', on: now.current });
  }, [ready]);

  function setWarmOn(on: boolean) {
    setWarmOnState(on);
    saveWarmOn(on);
    window.pseudo.send({ type: 'warm_sessions', on }); // off stops the open session, which frees its memory
  }

  return { warmOn, setWarmOn };
}
