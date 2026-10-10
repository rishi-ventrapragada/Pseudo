// M39: the window's own colours (window-look.js) are the page's (src/theme.css), so nothing flashes or shows a seam:
// the background Electron paints before the page draws, and the strip behind the minimize, maximize and close buttons.
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { describe, expect, it } from 'vitest';

const { GROUND, SYMBOLS, WINDOW_LOOK } = createRequire(import.meta.url)('./window-look.js');
const theme = readFileSync(new URL('./src/theme.css', import.meta.url), 'utf8');
const token = (name) => theme.match(new RegExp(`--color-${name}:\\s*(#[0-9a-f]{6})`))?.[1];

describe('the window look', () => {
  it('uses the design tokens', () => {
    expect(GROUND).toBe(token('ground'));
    expect(SYMBOLS).toBe(token('ink-soft'));
  });

  it('is dark always, and the buttons sit on the same ground as the page', () => {
    expect(WINDOW_LOOK.backgroundColor).toBe(GROUND);
    expect(WINDOW_LOOK.titleBarOverlay).toEqual({ color: GROUND, symbolColor: SYMBOLS, height: 44 });
  });

  it("keeps the page's top-right corner free for the three buttons", () => {
    expect(theme).toContain('--controls-width: 138px'); // 3 x 46 px
  });
});
