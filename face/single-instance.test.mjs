// M34: one Pseudo at a time (single-instance.js). Electron's `app` and the window are fakes here:
// the app hands out the lock or refuses it, and the window records what was done to it.
import { createRequire } from 'node:module';
import { describe, expect, it } from 'vitest';

const { onlyOne } = createRequire(import.meta.url)('./single-instance.js');

function fakeApp(gotLock) {
  const listeners = {};
  return {
    requestSingleInstanceLock: () => gotLock,
    on: (event, listener) => { listeners[event] = listener; },
    listeners,
  };
}

function fakeWindow({ minimized = false, destroyed = false } = {}) {
  const done = [];
  return {
    isDestroyed: () => destroyed,
    isMinimized: () => minimized,
    restore: () => done.push('restore'),
    show: () => done.push('show'),
    focus: () => done.push('focus'),
    done,
  };
}

describe('onlyOne', () => {
  it('the first Pseudo gets the lock and listens for a second launch', () => {
    const app = fakeApp(true);
    expect(onlyOne(app, () => null)).toBe(true);
    expect(Object.keys(app.listeners)).toEqual(['second-instance']);
  });

  it('a second Pseudo is told to quit and listens for nothing', () => {
    const app = fakeApp(false);
    expect(onlyOne(app, () => null)).toBe(false);
    expect(app.listeners).toEqual({});
  });

  it('a second launch shows and focuses the first window', () => {
    const app = fakeApp(true);
    const win = fakeWindow();
    onlyOne(app, () => win);
    app.listeners['second-instance']();
    expect(win.done).toEqual(['show', 'focus']);
  });

  it('a minimized window is restored first', () => {
    const app = fakeApp(true);
    const win = fakeWindow({ minimized: true });
    onlyOne(app, () => win);
    app.listeners['second-instance']();
    expect(win.done).toEqual(['restore', 'show', 'focus']);
  });

  it('the window is looked up at the time of the second launch, not before', () => {
    const app = fakeApp(true);
    let win = null;
    onlyOne(app, () => win);
    app.listeners['second-instance'](); // no window yet: nothing happens, nothing throws
    win = fakeWindow();
    app.listeners['second-instance']();
    expect(win.done).toEqual(['show', 'focus']);
  });

  it('a window that is closing is left alone', () => {
    const app = fakeApp(true);
    const win = fakeWindow({ destroyed: true });
    onlyOne(app, () => win);
    app.listeners['second-instance']();
    expect(win.done).toEqual([]);
  });
});
