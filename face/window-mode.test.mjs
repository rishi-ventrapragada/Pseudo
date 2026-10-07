// M38: the window's two modes (window-mode.js): switching, growing, and always on top. The fakes are in window-fakes.mjs.
import { describe, expect, it } from 'vitest';
import { AREA, BAR, FULL, setup, tool } from './window-fakes.mjs';

describe('WindowMode: full and compact on the same window', () => {
  it('starts full, at the size from before M38, and not on top', () => {
    const { mode, win } = setup();
    expect(mode.options()).toEqual({ ...FULL, minWidth: 520, minHeight: 420 });
    expect(win.getBounds()).toEqual(FULL); // exact, although the fake screen adds a pixel (setExact)
    expect(win.top).toBe(false);
    expect(mode.state()).toEqual({ type: 'window_mode', compact: false });
  });

  it('compact: the bar, its own minimum, always on top, and the mode is remembered', () => {
    const { mode, win, written } = setup();
    expect(mode.fromPage({ type: 'window_mode', compact: true })).toEqual({ type: 'window_mode', compact: true });
    expect(win.getBounds()).toEqual(BAR);
    expect(win.min).toEqual([360, 120]);
    expect(win.top).toBe(true);
    expect(written.at(-1).mode).toBe('compact');
  });

  it('step 0: five switches there and back never change the full size by a pixel', () => {
    const { mode, win } = setup();
    for (let n = 0; n < 5; n += 1) {
      mode.setMode('compact');
      mode.setMode('full');
      expect(win.getBounds()).toEqual(FULL);
      expect(win.min).toEqual([520, 420]);
      expect(win.top).toBe(false);
    }
  });

  it('opens in the mode it was closed in; a file that makes no sense means full', () => {
    expect(setup({ mode: 'compact' }).win.getBounds()).toEqual(BAR);
    for (const bad of [null, [], { mode: 'tiny' }, { mode: 7, full: 'big' }]) expect(setup(bad).win.getBounds()).toEqual(FULL);
  });

  it('C5: a saved place that is off-screen today is corrected', () => {
    const { win } = setup({ mode: 'compact', compact: { x: 5000, y: 3000, width: 480, height: 132 } });
    const { x, y, width, height } = win.getBounds();
    expect(x >= 0 && y >= 0 && x + width <= AREA.width && y + height <= AREA.height).toBe(true);
  });

  it('a maximized window is taken out of maximize before it becomes the bar', () => {
    const { mode, win } = setup();
    win.maximized = true;
    mode.setMode('compact');
    expect(win.maximized).toBe(false);
    expect(win.getBounds()).toEqual(BAR);
  });

  it('the page can only send real true/false values', () => {
    const { mode, win } = setup();
    for (const bad of [{ compact: 'yes' }, { compact: 1 }, { grown: 'true' }, {}]) mode.fromPage({ type: 'window_mode', ...bad });
    expect(win.getBounds()).toEqual(FULL);
  });
});

describe('WindowMode: the bar grows to show an answer', () => {
  it('grows upward with the bottom edge kept, gets a taller minimum, and shrinks back exactly', () => {
    const { mode, win } = setup({ mode: 'compact' });
    mode.fromPage({ type: 'window_mode', grown: true });
    expect(win.getBounds()).toEqual({ x: BAR.x, y: BAR.y + BAR.height - 440, width: 480, height: 440 });
    expect(win.min).toEqual([360, 260]);
    expect(win.top).toBe(true);
    mode.fromPage({ type: 'window_mode', grown: false });
    expect(win.getBounds()).toEqual(BAR);
    expect(win.min).toEqual([360, 120]);
  });

  it('the full window never grows, and leaving compact forgets the growth', () => {
    const { mode, win } = setup();
    mode.setGrown(true);
    expect(win.getBounds()).toEqual(FULL);
    mode.setMode('compact');
    mode.setGrown(true);
    mode.setMode('full');
    mode.setMode('compact');
    expect(win.getBounds()).toEqual(BAR);
  });
});

describe('WindowMode: always on top, and when it is given up', () => {
  it('C2: while a tool waits the bar is not on top; it is again when the result arrives', () => {
    const { mode, win } = setup({ mode: 'compact' });
    mode.fromBrain(tool('tool_call'));
    expect(win.top).toBe(false);
    mode.fromBrain(tool('tool_result'));
    expect(win.top).toBe(true);
    mode.fromBrain(tool('tool_call'));
    mode.fromBrain({ type: 'turn_done', ok: false }); // the turn ended without a result
    expect(win.top).toBe(true);
    mode.fromBrain(tool('tool_call'));
    mode.brainStopped();
    expect(win.top).toBe(true);
  });

  it('switching or growing while a tool waits does not bring always-on-top back', () => {
    const { mode, win } = setup();
    mode.fromBrain(tool('tool_call'));
    mode.setMode('compact');
    mode.setGrown(true);
    expect(win.top).toBe(false);
  });

  it('other messages change nothing, and the full window is never on top', () => {
    const { mode, win } = setup();
    for (const message of [tool('answer'), { type: 'ready' }, tool('tool_call'), tool('tool_result')]) mode.fromBrain(message);
    expect(win.tops.every((on) => on === false)).toBe(true);
  });

  it('step 0: a hidden bar is not on top (letGo before the hide), and is again once shown', () => {
    const { mode, win } = setup({ mode: 'compact' });
    mode.letGo();
    expect(win.top).toBe(false);
    win.visible = false;
    mode.fromBrain(tool('tool_result')); // something arrives while hidden: still not on top
    expect(win.top).toBe(false);
    win.visible = true;
    win.handlers.show();
    expect(win.top).toBe(true);
  });

  it('a window that starts hidden (Start with Windows) is not on top until it is shown', () => {
    const { win } = setup({ mode: 'compact' }, { visible: false });
    expect(win.top).toBe(false);
  });
});
