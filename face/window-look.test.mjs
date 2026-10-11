// M39: the window's own colours (window-look.js) are the page's (src/theme.css), so nothing flashes or shows a seam:
// the background Electron paints before the page draws, and the strip behind the minimize, maximize and close buttons.
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { describe, expect, it } from 'vitest';

const { GROUND, SYMBOLS, TOP_ROW, WINDOW_LOOK, lookFor, overlayFor } = createRequire(import.meta.url)('./window-look.js');
const theme = readFileSync(new URL('./src/theme.css', import.meta.url), 'utf8');
const token = (name) => theme.match(new RegExp(`--color-${name}:\\s*(#[0-9a-f]{6})`))?.[1];

describe('the window look', () => {
  it('uses the design tokens', () => {
    expect(GROUND).toBe(token('ground'));
    expect(SYMBOLS).toBe(token('ink-soft'));
  });

  it("M44: gives the window (and so its taskbar button) Pseudo's own icon", () => {
    expect(WINDOW_LOOK.icon).toMatch(/[\\/]pseudo\.ico$/);
    expect(lookFor('full').icon).toBe(WINDOW_LOOK.icon);
    expect(lookFor('compact').icon).toBe(WINDOW_LOOK.icon);
  });

  it('is dark always, and the buttons sit on the same ground as the page', () => {
    expect(WINDOW_LOOK.backgroundColor).toBe(GROUND);
    expect(WINDOW_LOOK.titleBarOverlay).toEqual({ color: GROUND, symbolColor: SYMBOLS, height: 44 });
  });

  it("M43: the buttons are as tall as each mode's top row: 44 px in the full window, 30 px in the bar", () => {
    expect(TOP_ROW).toEqual({ full: 44, compact: 30 });
    expect(overlayFor('compact')).toEqual({ color: GROUND, symbolColor: SYMBOLS, height: 30 });
    expect(overlayFor('full')).toEqual(WINDOW_LOOK.titleBarOverlay);
    expect(overlayFor('anything else').height).toBe(44);
    expect(lookFor('compact')).toEqual({ ...WINDOW_LOOK, titleBarOverlay: overlayFor('compact') });
    const page = (file) => readFileSync(new URL(file, import.meta.url), 'utf8');
    expect(page('./src/components/TopBar.tsx')).toContain('h-11'); // 44 px
    expect(page('./src/components/CompactBar.tsx')).toContain('h-[30px]');
  });

  it("keeps the page's top-right corner free for the three buttons", () => {
    expect(theme).toContain('--controls-width: 138px'); // 3 x 46 px
  });

  it('keeps room for two buttons in the compact bar, which shows no maximize button (M43, seen live)', () => {
    expect(theme).toContain('--bar-controls-width: 92px'); // 2 x 46 px: minimize and close
    const bar = readFileSync(new URL('./src/components/CompactBar.tsx', import.meta.url), 'utf8');
    expect(bar).toContain('pr-[var(--bar-controls-width)]');
  });

  it('drag rows let go while a dialog is open, so its buttons always get the click', () => {
    expect(theme).toContain('body:has(dialog[open]) .drag { -webkit-app-region: no-drag; }');
  });
});
