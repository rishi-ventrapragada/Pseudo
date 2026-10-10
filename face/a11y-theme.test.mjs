// M39: the accessibility baseline that lives in src/theme.css.
// Text is readable (WCAG AA): every text colour the page uses on every ground it uses it on has a contrast
// ratio of at least 4.5 to 1. The colours are read from theme.css, so changing a token re-checks it here.
// (Here, not in src/: the page's own tests have no file access.)
// Contrast, in short: each colour gets a "relative luminance" from 0 (black) to 1 (white); the ratio is
// (lighter + 0.05) / (darker + 0.05). 21:1 is black on white; 4.5:1 is the AA minimum for normal text.
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

const theme = readFileSync(new URL('./src/theme.css', import.meta.url), 'utf8');
const token = (name) => {
  const hex = theme.match(new RegExp(`--color-${name}:\\s*(#[0-9a-f]{6})`))?.[1];
  if (!hex) throw new Error(`no token ${name}`);
  return hex;
};

function luminance(hex) {
  const [r, g, b] = [1, 3, 5].map((at) => parseInt(hex.slice(at, at + 2), 16) / 255)
    .map((c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

export function ratio(a, b) {
  const [light, dark] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (light + 0.05) / (dark + 0.05);
}

const GROUNDS = ['sidebar', 'ground', 'field', 'raised', 'dialog', 'popover', 'composer'];
const PAIRS = [
  ...['ink', 'ink-soft', 'muted', 'faint'].flatMap((text) => GROUNDS.map((ground) => [text, ground])),
  ['ink', 'bubble'], ['ink-soft', 'bubble'], ['muted', 'bubble'], // your question, masks, the chosen provider
  ['danger', 'ground'], ['danger', 'composer'], ['danger', 'popover'], // Delete, recording
  ['wait', 'ground'], // the approval wait (M40)
  ['sidebar', 'ink'], // the white Ask and Done buttons
  ['white', 'danger-strong'], // the Delete button in a confirm
];

describe('contrast (WCAG AA, 4.5:1)', () => {
  it('known values: black on white is 21, a colour on itself is 1', () => {
    expect(ratio('#000000', '#ffffff')).toBeCloseTo(21, 5);
    expect(ratio('#777777', '#777777')).toBe(1);
  });

  it.each(PAIRS)('%s text on %s', (text, ground) => {
    expect(ratio(token(text), token(ground))).toBeGreaterThanOrEqual(4.5);
  });
});

describe("the rest of the theme's baseline", () => {
  it('whatever has the keyboard shows a visible ring', () => {
    expect(theme).toMatch(/:focus-visible\s*\{\s*outline:\s*2px solid var\(--color-ink-soft\)/);
  });

  it('with "reduce motion" on in Windows, nothing moves', () => {
    expect(theme).toMatch(/@media \(prefers-reduced-motion: reduce\)\s*\{[^}]*animation: none !important;[^}]*transition: none !important;/);
  });
});
