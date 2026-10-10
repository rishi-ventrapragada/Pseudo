// M38: the window's sizes and places (window-bounds.js). Plain arithmetic on fake screens; C5 is checked here.
import { createRequire } from 'node:module';
import { describe, expect, it } from 'vitest';

const { GROWN, MARGIN, SIZES, barFrom, defaultBounds, fit, fittedHeight, grownFrom } = createRequire(import.meta.url)('./window-bounds.js');

const MAIN = { x: 0, y: 0, width: 1536, height: 816 }; // a 1536 x 864 screen minus its taskbar
const SECOND = { x: 1536, y: 0, width: 1536, height: 816 }; // a second screen to its right
const inside = (rect, area) => rect.x >= area.x && rect.y >= area.y
  && rect.x + rect.width <= area.x + area.width && rect.y + rect.height <= area.y + area.height;

describe('defaultBounds', () => {
  it('full opens in the middle of the screen, at the size it had before M38', () => {
    expect(defaultBounds('full', MAIN)).toEqual({ x: 278, y: 38, width: 980, height: 740 });
  });

  it('the bar opens at the bottom right, a margin away from the corner', () => {
    const bar = defaultBounds('compact', MAIN);
    expect(bar).toEqual({ x: 1536 - 480 - MARGIN, y: 816 - 84 - MARGIN, width: 480, height: 84 });
    expect(inside(bar, MAIN)).toBe(true);
  });
});

describe('fit', () => {
  it('a saved place on a screen is kept as it is', () => {
    const saved = { x: 100, y: 80, width: 900, height: 600 };
    expect(fit(saved, 'full', [MAIN])).toEqual(saved);
    expect(fit({ x: 1700, y: 80, width: 900, height: 600 }, 'full', [MAIN, SECOND])).toEqual({ x: 1700, y: 80, width: 900, height: 600 });
  });

  it('C5: a saved place that is off-screen is corrected (the second screen was unplugged)', () => {
    const lost = { x: 1700, y: 80, width: 900, height: 600 };
    const found = fit(lost, 'full', [MAIN]);
    expect(inside(found, MAIN)).toBe(true);
    expect([found.width, found.height]).toEqual([900, 600]); // the size is kept; only the place changes
    for (const far of [{ x: -5000, y: -5000, width: 480, height: 132 }, { x: 90000, y: 40, width: 480, height: 132 }]) {
      expect(inside(fit(far, 'compact', [MAIN, SECOND]), MAIN), JSON.stringify(far)).toBe(true);
    }
  });

  it('a window hanging over an edge is pushed fully onto the screen it is mostly on', () => {
    expect(fit({ x: 1400, y: 700, width: 480, height: 132 }, 'compact', [MAIN])).toEqual({ x: 1056, y: 684, width: 480, height: 132 });
    const mostlySecond = fit({ x: 1400, y: 10, width: 600, height: 500 }, 'full', [MAIN, SECOND]);
    expect(inside(mostlySecond, SECOND)).toBe(true);
  });

  it('C5: there is a minimum size, and a window is never bigger than its screen', () => {
    expect(fit({ x: 10, y: 10, width: 5, height: 5 }, 'full', [MAIN])).toMatchObject({ width: 520, height: 420 });
    expect(fit({ x: 10, y: 10, width: 5, height: 5 }, 'compact', [MAIN])).toMatchObject({ width: 360, height: 84 });
    expect(fit({ x: 0, y: 0, width: 9000, height: 9000 }, 'full', [MAIN])).toEqual(MAIN);
  });

  it('anything that is not four real numbers becomes the default', () => {
    for (const bad of [null, undefined, 'big', 7, [], {}, { x: 1, y: 2, width: 3 }, { x: '1', y: 2, width: 600, height: 500 },
                       { x: NaN, y: 0, width: 600, height: 500 }, { x: 0, y: 0, width: Infinity, height: 500 }]) {
      expect(fit(bad, 'full', [MAIN]), JSON.stringify(bad)).toEqual(defaultBounds('full', MAIN));
      expect(fit(bad, 'compact', [MAIN]), JSON.stringify(bad)).toEqual(defaultBounds('compact', MAIN));
    }
  });

  it('fractions from a scaled screen are rounded', () => {
    expect(fit({ x: 100.4, y: 80.6, width: 900.5, height: 600.2 }, 'full', [MAIN])).toEqual({ x: 100, y: 81, width: 901, height: 600 });
  });
});

describe('the bar growing and shrinking', () => {
  const bar = defaultBounds('compact', MAIN);

  it('grows upward: same place and width, the bottom edge stays put', () => {
    const grown = grownFrom(bar, GROWN.height, [MAIN]);
    expect(grown).toEqual({ x: bar.x, y: bar.y + bar.height - 440, width: 480, height: 440 });
    expect(grown.y + grown.height).toBe(bar.y + bar.height);
  });

  it('shrinks back to exactly the bar it grew from', () => {
    expect(barFrom(grownFrom(bar, 440, [MAIN]), bar.height, [MAIN])).toEqual(bar);
  });

  it('a bar at the top of the screen has no room above, so it stays on screen and grows downward', () => {
    const top = { x: 500, y: 0, width: 480, height: 132 };
    const grown = grownFrom(top, 440, [MAIN]);
    expect(grown).toEqual({ x: 500, y: 0, width: 480, height: 440 });
    expect(inside(grown, MAIN)).toBe(true);
  });

  it('a remembered height that is missing or too small still gives a usable answer area', () => {
    expect(grownFrom(bar, undefined, [MAIN]).height).toBe(440);
    expect(grownFrom(bar, 50, [MAIN]).height).toBe(GROWN.minHeight);
    expect(grownFrom(bar, 9000, [MAIN]).height).toBe(MAIN.height);
  });

  it('the sizes the plan fixed', () => {
    expect(SIZES).toEqual({ full: { width: 980, height: 740, minWidth: 520, minHeight: 420 },
                            compact: { width: 480, height: 84, minWidth: 360, minHeight: 84 } }); // M43: the mockup's bar
    expect(GROWN).toEqual({ height: 440, minHeight: 160 });
  });

  it('M43: the grown bar is as tall as its content asks, never more than the cap', () => {
    expect(fittedHeight(210, undefined)).toBe(210);
    expect(fittedHeight(600, undefined)).toBe(GROWN.height); // no height of yours yet: the default cap
    expect(fittedHeight(600, 380)).toBe(380); // the height you last gave the grown bar
    expect(fittedHeight(null, 380)).toBe(380); // nothing measured: the cap, as before M43
    for (const bad of ['300', NaN, Infinity, {}]) expect(fittedHeight(bad, 'tall'), String(bad)).toBe(GROWN.height);
    expect(grownFrom(bar, fittedHeight(50, undefined), [MAIN]).height).toBe(GROWN.minHeight); // grownFrom holds the minimum
  });
});
