// M32: a message from the page passes THREE lists before it reaches the brain: the page's own types
// (src/protocol.ts, ToBrain), the preload's TYPES (preload.js) and the main process's TO_BRAIN (to-brain.js).
// In M32 `warm_sessions` was added to two of them. The preload dropped it without a word, so the
// switch did nothing, and only the live check noticed. These tests read the three files and check
// that the lists agree. (preload.js and main.js need Electron to run, so they are read as text.)
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

const read = (name) => readFileSync(new URL(name, import.meta.url), 'utf8');
const quoted = (text) => [...text.matchAll(/'([a-z_]+)'/g)].map((match) => match[1]).sort();

const preload = quoted(read('./preload.js').match(/const TYPES = \[([\s\S]*?)\];/)[1]);
const toBrain = quoted(read('./to-brain.js').match(/const TO_BRAIN = new Set\(\[([\s\S]*?)\]\);/)[1]); // M37: moved from main.js
const page = read('./src/protocol.ts').match(/export type ToBrain =([\s\S]*?)declare global/)[1];
const pageTypes = [...page.matchAll(/type: '([a-z_]+)'/g)].map((match) => match[1]).sort();

describe('the message types the page may send', () => {
  it('found the three lists', () => {
    expect(preload.length).toBeGreaterThan(5);
    expect(toBrain.length).toBeGreaterThan(5);
    expect(pageTypes.length).toBeGreaterThan(5);
  });

  it('the preload lets through exactly what the page can send', () => {
    expect(preload).toEqual(pageTypes);
  });

  it('the main process passes on exactly those, except restart, autostart (M36) and window_mode (M38), which it handles itself', () => {
    expect([...toBrain, 'restart', 'autostart', 'window_mode'].sort()).toEqual(preload);
    const main = read('./main.js');
    for (const own of ['restart', 'autostart', 'window_mode']) expect(main).toContain(`message.type === '${own}'`);
  });

  it('M32: the warm-session switch is on all three', () => {
    for (const list of [preload, toBrain, pageTypes]) expect(list).toContain('warm_sessions');
  });
});
