// M26: audio conversions (audio.ts) and the push-to-talk key (pushToTalk.ts). All data is fake.
import { describe, expect, it } from 'vitest';
import { clock, fromBase64, toBase64, toPcm16 } from './audio';
import { isTalkKey, startsTalking, stopsTalking } from './pushToTalk';

describe('toPcm16', () => {
  it('scales floats to 16-bit whole numbers and clips anything too loud', () => {
    expect(Array.from(toPcm16(new Float32Array([0, 1, -1, 0.5, 2, -3])))).toEqual([0, 32767, -32768, 16384, 32767, -32768]);
  });
});

describe('base64', () => {
  it('round-trips bytes, including more than one 32 KB chunk', () => {
    const bytes = new Uint8Array(100000).map((_, i) => (i * 7) % 256);
    expect(fromBase64(toBase64(bytes))).toEqual(bytes);
    expect(toBase64(new Uint8Array([72, 105, 33]))).toBe('SGkh'); // "Hi!", as Python's base64 writes it
  });
});

describe('clock', () => {
  it('shows minutes and seconds', () => {
    expect([clock(0), clock(3.9), clock(30), clock(-1)]).toEqual(['0:00', '0:03', '0:30', '0:00']);
  });
});

const key = (code: string, key: string, ctrlKey: boolean, repeat = false) => ({ code, key, ctrlKey, repeat });

describe('push-to-talk key', () => {
  it('starts on the first Ctrl+Space only', () => {
    expect(startsTalking(key('Space', ' ', true))).toBe(true);
    expect(startsTalking(key('Space', ' ', true, true))).toBe(false); // a repeat while held
    expect(isTalkKey(key('Space', ' ', true, true))).toBe(true); // ...but it still mustn't type a space
    expect(startsTalking(key('Space', ' ', false))).toBe(false); // a plain space types a space
    expect(startsTalking(key('KeyS', 's', true))).toBe(false);
  });

  it('stops when Space or Ctrl is let go', () => {
    expect(stopsTalking(key('Space', ' ', true))).toBe(true);
    expect(stopsTalking(key('ControlLeft', 'Control', false))).toBe(true);
    expect(stopsTalking(key('KeyA', 'a', false))).toBe(false);
  });
});
