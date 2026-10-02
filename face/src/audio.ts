// M26: converting audio between the forms the browser, the pipe and Whisper use. Pure functions, tested.
//   Web Audio gives samples as floats from -1 to 1. Whisper and SAPI use PCM16: whole numbers from
//   -32768 to 32767, 16,000 of them a second. The pipe carries JSON text, so bytes travel as base64.

export const RATE = 16000; // samples a second, as the brain expects (voice_in.py)
export const MAX_SECONDS = 30; // push-to-talk stops by itself here (D24)

/** Float samples (-1..1) -> 16-bit PCM. Anything louder than full scale is clipped, not wrapped around. */
export function toPcm16(samples: Float32Array): Int16Array {
  const pcm = new Int16Array(samples.length);
  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    pcm[i] = Math.round(s < 0 ? s * 32768 : s * 32767);
  }
  return pcm;
}

/** Bytes -> base64 text. Built in chunks: one String.fromCharCode call with a million arguments overflows the stack. */
export function toBase64(bytes: Uint8Array): string {
  let binary = '';
  for (let i = 0; i < bytes.length; i += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  }
  return btoa(binary);
}

/** Base64 text -> bytes (a spoken answer's WAV file, from the brain). */
export function fromBase64(text: string): Uint8Array {
  const binary = atob(text);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

/** 3.4 -> "0:03": the recording clock on the mic button. */
export function clock(seconds: number): string {
  const whole = Math.max(0, Math.floor(seconds));
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, '0')}`;
}
