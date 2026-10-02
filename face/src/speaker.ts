// M26: plays Pseudo's spoken answers: WAV files the brain made with a Windows voice (voice_out.py).
// One at a time: a new answer, Stop speaking, the mute switch or starting a recording stops the last one.
// The sound is decoded in memory by Web Audio; nothing is saved and nothing is fetched.

import { fromBase64 } from './audio';

let context: AudioContext | null = null;
let current: AudioBufferSourceNode | null = null;
let generation = 0; // bumped by every play() and stop(), so a slow decode can't start an old answer late

/** Play one answer. onEnd is called when it finishes by itself (not when it's stopped). */
export async function play(wavBase64: string, onEnd: () => void): Promise<void> {
  stop();
  const mine = ++generation;
  context ??= new AudioContext();
  const bytes = fromBase64(wavBase64);
  const buffer = await context.decodeAudioData(bytes.buffer as ArrayBuffer);
  if (mine !== generation) return; // stopped (or replaced) while it was being decoded
  const source = context.createBufferSource();
  source.buffer = buffer;
  source.connect(context.destination);
  source.onended = () => {
    if (current === source) {
      current = null;
      onEnd();
    }
  };
  current = source;
  source.start();
}

/** Stop whatever is playing, now. */
export function stop(): void {
  generation++;
  const source = current;
  current = null;
  if (source) {
    source.onended = null;
    source.stop();
  }
}
