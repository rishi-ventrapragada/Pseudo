// M32: the warm-session line and switch (WarmControl.tsx), and the remembered choice (useWarm.ts).
// All states are fake. renderToStaticMarkup turns React output into an HTML string, so no browser is needed.
import { renderToStaticMarkup } from 'react-dom/server';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { Warm } from './protocol';
import { saveWarmOn, savedWarmOn } from './useWarm';
import { WarmControl, warmLine } from './WarmControl';

const NONE: Warm = { on: true, open: false, ram_mb: null, asked: 0, of: 6, idle_minutes: 10, note: '' };
const OPEN: Warm = { ...NONE, open: true, ram_mb: 356.4, asked: 2 };

describe('warmLine', () => {
  it('shows the memory and the count only while a session is open', () => {
    expect(warmLine(OPEN, true)).toBe('Open: 356 MB · 2 of 6 requests · stopped after 10 idle minutes.');
    expect(warmLine({ ...OPEN, ram_mb: null }, true)).toContain('Open: measuring its memory · 2 of 6 requests');
    expect(warmLine(NONE, true)).not.toMatch(/MB|of 6/);
  });

  it('says what the next action request will do when none is open, and why the last one stopped', () => {
    expect(warmLine(NONE, true))
      .toBe('None open. Your next action request starts Claude Code (about 20 s), then one stays open.');
    expect(warmLine({ ...NONE, note: 'stopped: idle for 10 minutes' }, true))
      .toContain('None open (stopped: idle for 10 minutes). Your next action request starts Claude Code');
  });

  it('when off, says nothing is kept running', () => {
    const off = 'Off: every action request starts Claude Code (about 20 s), and nothing is kept running.';
    expect(warmLine({ ...NONE, on: false, note: 'stopped: warm sessions were turned off' }, false)).toBe(off);
    expect(warmLine(null, false)).toBe(off); // the brain hasn't spoken yet: the switch decides
  });

  it("believes the brain over the switch once the brain has spoken", () => {
    expect(warmLine({ ...NONE, on: false }, true)).toMatch(/^Off:/); // told on, but the brain says off
    expect(warmLine(null, true)).toMatch(/^None open\./);
  });
});

describe('WarmControl', () => {
  it('shows the switch as you left it, and marks an open session', () => {
    // M39: a switch in a Settings row now; the checks are the same.
    const open = renderToStaticMarkup(<WarmControl warm={OPEN} warmOn={true} setWarmOn={() => {}} />);
    expect(open).toContain('data-open="true"');
    expect(open).toContain('aria-checked="true"');
    expect(open).toContain('Keep Claude Code warm');
    expect(open).toContain('356 MB');
    const off = renderToStaticMarkup(<WarmControl warm={{ ...NONE, on: false }} warmOn={false} setWarmOn={() => {}} />);
    expect(off).toContain('data-open="false"');
    expect(off).toContain('aria-checked="false"');
    expect(off).not.toContain(' MB');
  });
});

describe('the remembered switch', () => {
  afterEach(() => vi.unstubAllGlobals());

  function fakeStorage(start: Record<string, string> = {}) {
    const kept = { ...start };
    vi.stubGlobal('localStorage', {
      getItem: (key: string) => kept[key] ?? null,
      setItem: (key: string, value: string) => { kept[key] = value; },
    });
    return kept;
  }

  it('is on unless you turned it off, and survives a restart of the window', () => {
    const kept = fakeStorage();
    expect(savedWarmOn()).toBe(true); // never set: on
    saveWarmOn(false);
    expect(kept).toEqual({ 'pseudo.warmSessions': 'off' });
    expect(savedWarmOn()).toBe(false); // a new window reads the same storage
    saveWarmOn(true);
    expect(savedWarmOn()).toBe(true);
  });

  it('falls back to on when storage is blocked, and saving does not throw', () => {
    vi.stubGlobal('localStorage', {
      getItem: () => { throw new Error('blocked'); },
      setItem: () => { throw new Error('blocked'); },
    });
    expect(savedWarmOn()).toBe(true);
    expect(() => saveWarmOn(false)).not.toThrow();
  });
});
