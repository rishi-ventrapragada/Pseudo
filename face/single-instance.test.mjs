// M34: one Pseudo at a time (single-instance.js). Electron's `app` is a fake here: it hands out the lock
// or refuses it. (M36) What "show the window" does is reveal.js's job, tested in reveal.test.mjs.
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

describe('onlyOne', () => {
  it('the first Pseudo gets the lock and listens for a second launch', () => {
    const app = fakeApp(true);
    expect(onlyOne(app, () => {})).toBe(true);
    expect(Object.keys(app.listeners)).toEqual(['second-instance']);
  });

  it('a second Pseudo is told to quit and listens for nothing', () => {
    const app = fakeApp(false);
    expect(onlyOne(app, () => {})).toBe(false);
    expect(app.listeners).toEqual({});
  });

  it('every second launch shows the first Pseudo, and nothing is shown before one', () => {
    const app = fakeApp(true);
    let shown = 0;
    onlyOne(app, () => { shown += 1; });
    expect(shown).toBe(0);
    app.listeners['second-instance']();
    app.listeners['second-instance']();
    expect(shown).toBe(2);
  });

  it("Electron's own arguments to the event are not passed on", () => {
    const app = fakeApp(true);
    const got = [];
    onlyOne(app, (...args) => got.push(args));
    app.listeners['second-instance']({}, ['Pseudo.exe', '--anything'], 'C:\\somewhere');
    expect(got).toEqual([[]]);
  });
});
