// M26: push-to-talk recording. The microphone is open only between startRecording() and stop(), at most
// 30 seconds; stop() releases it and hands back 16 kHz mono PCM16 as base64, for the brain (bridge_voice.py).
// Nothing is saved: the recording lives in this page's memory until it is sent, then it's gone.
//
// Two browser APIs do the work:
//   MediaRecorder records the microphone, compressed (WebM/Opus), in memory.
//   Web Audio decodes that recording and RESAMPLES it: an OfflineAudioContext renders it as fast as it can
//   at 16,000 samples a second, one channel, which is the format Whisper hears best (M25).

import { MAX_SECONDS, RATE, toBase64, toPcm16 } from './audio';

export type Recording = {
  /** Stop recording and release the microphone. Resolves to base64 PCM ('' if nothing was captured). */
  stop(): Promise<string>;
};

/** Open the microphone and start recording. onCap is called if 30 seconds pass first. */
export async function startRecording(onCap: () => void): Promise<Recording> {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
    video: false, // never the camera (and permissions.js would refuse it)
  });
  const recorder = new MediaRecorder(stream);
  const chunks: Blob[] = [];
  recorder.ondataavailable = (event) => {
    if (event.data.size > 0) chunks.push(event.data);
  };
  const stopped = new Promise<void>((resolve) => {
    recorder.onstop = () => resolve();
  });
  recorder.start();
  const cap = window.setTimeout(onCap, MAX_SECONDS * 1000);
  let result: Promise<string> | null = null;

  return {
    stop() {
      result ??= (async () => {
        window.clearTimeout(cap);
        if (recorder.state !== 'inactive') recorder.stop();
        await stopped;
        stream.getTracks().forEach((track) => track.stop()); // the microphone is released HERE
        return chunks.length ? toPcmBase64(new Blob(chunks, { type: recorder.mimeType })) : '';
      })();
      return result;
    },
  };
}

/** The compressed recording -> 16 kHz mono PCM16, base64. Never longer than MAX_SECONDS. */
async function toPcmBase64(recording: Blob): Promise<string> {
  const context = new AudioContext();
  try {
    const decoded = await context.decodeAudioData(await recording.arrayBuffer());
    const seconds = Math.min(decoded.duration, MAX_SECONDS);
    const offline = new OfflineAudioContext(1, Math.max(1, Math.ceil(seconds * RATE)), RATE);
    const source = offline.createBufferSource();
    source.buffer = decoded; // two channels would be mixed down to the one channel here
    source.connect(offline.destination);
    source.start();
    const rendered = await offline.startRendering();
    return toBase64(new Uint8Array(toPcm16(rendered.getChannelData(0)).buffer));
  } finally {
    await context.close();
  }
}
