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
    expect(win.min).toEqual([360, 84]);
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
    const { win } = setup({ mode: 'compact', compact: { x: 5000, y: 3000, width: 480, height: 84 } });
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
    expect(win.min).toEqual([360, 160]);
    expect(win.top).toBe(true);
    mode.fromPage({ type: 'window_mode', grown: false });
    expect(win.getBounds()).toEqual(BAR);
    expect(win.min).toEqual([360, 84]);
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
    mode.top.fromBrain(tool('tool_call'));
    expect(win.top).toBe(false);
    mode.top.fromBrain(tool('tool_result'));
    expect(win.top).toBe(true);
    mode.top.fromBrain(tool('tool_call'));
    mode.top.fromBrain({ type: 'turn_done', ok: false }); // the turn ended without a result
    expect(win.top).toBe(true);
    mode.top.fromBrain(tool('tool_call'));
    mode.top.brainStopped();
    expect(win.top).toBe(true);
  });

  it('switching or growing while a tool waits does not bring always-on-top back', () => {
    const { mode, win } = setup();
    mode.top.fromBrain(tool('tool_call'));
    mode.setMode('compact');
    mode.setGrown(true);
    expect(win.top).toBe(false);
  });

  it('other messages change nothing, and the full window is never on top', () => {
    const { mode, win } = setup();
    for (const message of [tool('answer'), { type: 'ready' }, tool('tool_call'), tool('tool_result')]) mode.top.fromBrain(message);
    expect(win.tops.every((on) => on === false)).toBe(true);
  });

  it('step 0: a hidden bar is not on top (letGo before the hide), and is again once shown', () => {
    const { mode, win } = setup({ mode: 'compact' });
    mode.top.letGo();
    expect(win.top).toBe(false);
    win.visible = false;
    mode.top.fromBrain(tool('tool_result')); // something arrives while hidden: still not on top
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

describe('M43: the bar\'s own title bar, and a grown bar that fits what it shows', () => {
  it('the bar\'s buttons are as tall as its 30 px row and it cannot be maximized; full gets both back', () => {
    const { mode, win } = setup();
    expect([win.overlay.height, win.maximizable]).toEqual([44, true]);
    mode.setMode('compact');
    expect([win.overlay.height, win.maximizable]).toEqual([30, false]);
    expect(win.overlay).toMatchObject({ color: '#171719', symbolColor: '#c9c9d1' }); // only the height changes
    mode.setMode('full');
    expect([win.overlay.height, win.maximizable]).toEqual([44, true]);
    const opened = setup({ mode: 'compact' }).win; // opened as the bar: shaped at once
    expect([opened.overlay.height, opened.maximizable]).toEqual([30, false]);
  });

  it('grows to the height its content asks for, bottom edge kept, between the minimum and the cap', () => {
    const { mode, win } = setup({ mode: 'compact' });
    const grownTo = (height) => ({ x: BAR.x, y: BAR.y + BAR.height - height, width: 480, height });
    mode.fromPage({ type: 'window_mode', grown: true, height: 210.4 });
    expect(win.getBounds()).toEqual(grownTo(210));
    mode.fromPage({ type: 'window_mode', grown: true, height: 9000 });
    expect(win.getBounds()).toEqual(grownTo(440)); // the default cap
    mode.fromPage({ type: 'window_mode', grown: true, height: 50 });
    expect(win.getBounds()).toEqual(grownTo(160)); // the minimum
    mode.fromPage({ type: 'window_mode', grown: false });
    expect(win.getBounds()).toEqual(BAR);
  });

  it('the cap is the height you last gave the grown bar', () => {
    const { mode, win } = setup({ mode: 'compact', grownHeight: 300 });
    mode.setGrown(true, 350);
    expect(win.getBounds().height).toBe(300);
    mode.setGrown(true, 250);
    expect(win.getBounds().height).toBe(250);
  });

  it('a height that is not a real number is ignored, and the same height again changes nothing', () => {
    for (const bad of ['300', NaN, Infinity, null, {}]) {
      const { mode, win } = setup({ mode: 'compact' });
      mode.fromPage({ type: 'window_mode', grown: true, height: bad });
      expect(win.getBounds().height, String(bad)).toBe(440); // grown, to the cap, as before M43
    }
    const { mode, win } = setup({ mode: 'compact' });
    mode.setGrown(true, 200);
    const placed = win.tops.length; // every placing ends by setting always-on-top
    mode.setGrown(true, 200.2);
    expect(win.tops.length).toBe(placed);
  });

  it('fitting the bar while a tool waits keeps always-on-top off', () => {
    const { mode, win } = setup({ mode: 'compact' });
    mode.top.fromBrain(tool('tool_call'));
    mode.fromPage({ type: 'window_mode', grown: true, height: 230 });
    expect(win.getBounds().height).toBe(230);
    expect(win.top).toBe(false);
  });
});
