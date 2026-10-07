// M36: the "Start with Windows" entry (autostart.js). Electron's `app` is a fake that keeps its login
// items in a list, shaped as the M36 probe saw the real one answer. The registry is never touched.
import { createRequire } from 'node:module';
import { describe, expect, it } from 'vitest';

const { HIDDEN_ARG, NAME, autostartState, setAutostart, startedHidden } = createRequire(import.meta.url)('./autostart.js');

const EXE = 'C:\\dev\\Pseudo\\face\\out\\Pseudo\\Pseudo.exe';

function fakeApp({ packaged = true, items = [] } = {}) {
  const app = {
    isPackaged: packaged,
    items: [...items],
    calls: [],
    // As measured: openAtLogin stays false when a name and arguments are given; the entry is in launchItems.
    getLoginItemSettings: () => ({ openAtLogin: false, launchItems: app.items }),
    setLoginItemSettings(settings) {
      app.calls.push(settings);
      app.items = app.items.filter((item) => item.name !== settings.name);
      if (settings.openAtLogin) app.items.push({ name: settings.name, path: EXE, args: [], scope: 'user', enabled: true });
    },
  };
  return app;
}

const entry = (changes = {}) => ({ name: NAME, path: EXE, args: [], scope: 'user', enabled: true, ...changes });

describe('autostartState', () => {
  it('no entry: off, and the switch can be used', () => {
    expect(autostartState(fakeApp(), EXE)).toEqual({ type: 'autostart', available: true, on: false, note: '' });
  });

  it('our entry: on', () => {
    expect(autostartState(fakeApp({ items: [entry()] }), EXE)).toEqual({ type: 'autostart', available: true, on: true, note: '' });
  });

  it('the path is compared without caring about upper and lower case', () => {
    expect(autostartState(fakeApp({ items: [entry({ path: EXE.toUpperCase() })] }), EXE).on).toBe(true);
  });

  it('switched off in Task Manager: shown as off, with the reason', () => {
    const state = autostartState(fakeApp({ items: [entry({ enabled: false })] }), EXE);
    expect(state.on).toBe(false);
    expect(state.note).toContain('Task Manager');
  });

  it('an entry for another Pseudo.exe is not ours: off, and it says so', () => {
    const state = autostartState(fakeApp({ items: [entry({ path: 'D:\\old\\Pseudo.exe' })] }), EXE);
    expect(state.on).toBe(false);
    expect(state.note).toContain('another Pseudo.exe');
  });

  it("another program's entry is ignored", () => {
    expect(autostartState(fakeApp({ items: [entry({ name: 'SomethingElse' })] }), EXE).on).toBe(false);
  });

  it('npm start: unavailable, with the reason, whatever Windows holds', () => {
    const state = autostartState(fakeApp({ packaged: false, items: [entry()] }), EXE);
    expect(state).toEqual({ type: 'autostart', available: false, on: false,
                            note: 'Start with Windows works from Pseudo.exe, not from npm start.' });
  });
});

describe('setAutostart', () => {
  it('on writes one entry named Pseudo that starts hidden, and reports what Windows then says', () => {
    const app = fakeApp();
    expect(setAutostart(app, true, EXE).on).toBe(true);
    expect(app.calls).toEqual([{ openAtLogin: true, name: 'Pseudo', args: [HIDDEN_ARG], enabled: true }]);
    expect(app.items.map((item) => item.name)).toEqual(['Pseudo']);
  });

  it("off removes it and leaves other programs' entries alone", () => {
    const app = fakeApp({ items: [entry({ name: 'SomethingElse' }), entry()] });
    expect(setAutostart(app, false, EXE).on).toBe(false);
    expect(app.items.map((item) => item.name)).toEqual(['SomethingElse']);
  });

  it('npm start: nothing is written', () => {
    const app = fakeApp({ packaged: false });
    expect(setAutostart(app, true, EXE).available).toBe(false);
    expect(app.calls).toEqual([]);
  });
});

describe('startedHidden', () => {
  it('only the packaged app listens to --start-hidden', () => {
    expect(startedHidden({ isPackaged: true }, [EXE, HIDDEN_ARG])).toBe(true);
    expect(startedHidden({ isPackaged: true }, [EXE])).toBe(false);
    expect(startedHidden({ isPackaged: false }, ['electron.exe', '.', HIDDEN_ARG])).toBe(false);
  });
});
