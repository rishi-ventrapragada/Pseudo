// M38: the Compact / Full window button, Hide answer, and when the bar grows (CompactToggle.tsx, useCompact.ts).
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { CompactToggle, HideAnswer } from './CompactToggle';
import { barGrows, type Compact } from './useCompact';

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

describe('CompactToggle', () => {
  it('offers the other mode, and says which one is on', () => {
    const full = renderToStaticMarkup(<CompactToggle compact={mode({})} />);
    expect(full).toContain('aria-pressed="false"');
    expect(full).toContain('>Compact</button>');
    const bar = renderToStaticMarkup(<CompactToggle compact={mode({ on: true })} />);
    expect(bar).toContain('aria-pressed="true"');
    expect(bar).toContain('>Full window</button>');
  });
});

describe('HideAnswer', () => {
  it('is there only while the bar is grown', () => {
    expect(renderToStaticMarkup(<HideAnswer compact={mode({ on: true })} />)).toBe('');
    expect(renderToStaticMarkup(<HideAnswer compact={mode({ on: true, grown: true })} />)).toContain('>Hide answer</button>');
  });
});
