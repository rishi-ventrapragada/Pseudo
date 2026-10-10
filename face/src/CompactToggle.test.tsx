// M38: the Compact / Full window button, Hide answer, and when the bar grows (CompactToggle.tsx, useCompact.ts).
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { CompactToggle, HideAnswer } from './CompactToggle';
import { barGrows, barHeight, type Compact } from './useCompact';

const mode = (over: Partial<Compact>): Compact => ({ on: false, grown: false, setOn: () => {}, open: () => {}, close: () => {}, ...over });

describe('barGrows', () => {
  it('the full window never grows', () => {
    expect(barGrows(false, true, 3, 'ready')).toBe(false);
    expect(barGrows(false, true, 3, 'stopped')).toBe(false);
  });

  it('the bar grows while the latest turn is open, and only if there is a turn', () => {
    expect(barGrows(true, true, 1, 'ready')).toBe(true);
    expect(barGrows(true, false, 1, 'ready')).toBe(false); // Hide answer was pressed, or nothing was asked yet
    expect(barGrows(true, true, 0, 'ready')).toBe(false);
  });

  it('a stopped brain needs room for Restart and its explanation', () => {
    expect(barGrows(true, false, 0, 'stopped')).toBe(true);
    expect(barGrows(true, false, 0, 'starting')).toBe(false);
  });
});

describe('barHeight (M43)', () => {
  it("is the top row, everything the grown area holds and the question row, rounded up", () => {
    expect(barHeight(30, 120, 54)).toBe(204);
    expect(barHeight(30, 120.2, 54)).toBe(205); // never a fraction short: the last line would be cut
    expect(barHeight(30, 0, 54)).toBe(84); // nothing to show yet: the main process still keeps GROWN.minHeight
  });
});

describe('CompactToggle', () => {
  it('offers the other mode, and says which one is on', () => { // M39: an icon button, named by its label
    const full = renderToStaticMarkup(<CompactToggle compact={mode({})} />);
    expect(full).toContain('aria-pressed="false"');
    expect(full).toContain('aria-label="Compact bar"');
    const bar = renderToStaticMarkup(<CompactToggle compact={mode({ on: true })} />);
    expect(bar).toContain('aria-pressed="true"');
    expect(bar).toContain('aria-label="Full window"');
  });
});

describe('HideAnswer', () => {
  it('is there only while the bar is grown', () => {
    expect(renderToStaticMarkup(<HideAnswer compact={mode({ on: true })} />)).toBe('');
    expect(renderToStaticMarkup(<HideAnswer compact={mode({ on: true, grown: true })} />)).toContain('>Hide answer</button>');
  });
});
