// M37: the two global shortcuts (hotkeys.js). Electron's globalShortcut is a fake that can refuse a
// combination, as Windows does when another program holds it. No real shortcut is ever registered.
import { readdirSync, readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { describe, expect, it } from 'vitest';

const { Hotkeys, SHORTCUTS } = createRequire(import.meta.url)('./hotkeys.js');

function fakeShortcuts({ taken = [], broken = [] } = {}) {
  const held = new Map();
  return {
    register(keys, pressed) {
      if (broken.includes(keys)) throw new Error('bad accelerator');
      if (taken.includes(keys)) return false;
      held.set(keys, pressed);
      return true;
    },
    unregister(keys) { held.delete(keys); },
    press(keys) { held.get(keys)?.(); },
    held,
  };
}

function setup(options) {
  const shortcuts = fakeShortcuts(options);
  const done = [];
  const hotkeys = new Hotkeys(shortcuts, { toggle: () => done.push('toggle'), talk: () => done.push('talk') });
  return { shortcuts, done, hotkeys };
}

describe('Hotkeys', () => {
  it('the two shortcuts are Ctrl+Alt+Enter and Ctrl+Alt+T', () => {
    expect(SHORTCUTS.map(({ keys, label }) => [keys, label]))
      .toEqual([['Control+Alt+Enter', 'Ctrl+Alt+Enter'], ['Control+Alt+T', 'Ctrl+Alt+T']]);
  });

  it('before register, nothing is held and the page is told so', () => {
    const { hotkeys, shortcuts } = setup();
    expect(shortcuts.held.size).toBe(0);
    expect(hotkeys.state().keys.map((key) => key.ok)).toEqual([false, false]);
  });

  it('registers both, and each press does only its own thing', () => {
    const { hotkeys, shortcuts, done } = setup();
    expect(hotkeys.register()).toEqual({ type: 'hotkeys', keys: [
      { id: 'toggle', label: 'Ctrl+Alt+Enter', ok: true }, { id: 'talk', label: 'Ctrl+Alt+T', ok: true }] });
    shortcuts.press('Control+Alt+Enter');
    expect(done).toEqual(['toggle']);
    shortcuts.press('Control+Alt+T');
    expect(done).toEqual(['toggle', 'talk']);
  });

  it('a shortcut another program holds is reported and left off; the other still works', () => {
    const { hotkeys, shortcuts, done } = setup({ taken: ['Control+Alt+T'] });
    expect(hotkeys.register().keys.map((key) => [key.id, key.ok])).toEqual([['toggle', true], ['talk', false]]);
    expect([...shortcuts.held.keys()]).toEqual(['Control+Alt+Enter']);
    shortcuts.press('Control+Alt+T'); // goes to the other program: nothing happens here
    shortcuts.press('Control+Alt+Enter');
    expect(done).toEqual(['toggle']);
  });

  it('an error while registering one is a refusal, not a crash', () => {
    const { hotkeys } = setup({ broken: ['Control+Alt+Enter'] });
    expect(hotkeys.register().keys.map((key) => key.ok)).toEqual([false, true]);
  });

  it('release gives back exactly the ones we hold', () => {
    const { hotkeys, shortcuts } = setup({ taken: ['Control+Alt+T'] });
    const unregistered = [];
    const real = shortcuts.unregister;
    shortcuts.unregister = (keys) => { unregistered.push(keys); real(keys); };
    hotkeys.register();
    hotkeys.release();
    expect(unregistered).toEqual(['Control+Alt+Enter']); // never the one another program holds
    expect(shortcuts.held.size).toBe(0);
    expect(hotkeys.state().keys.map((key) => key.ok)).toEqual([false, false]);
  });

  it('the state handed to the page is a copy', () => {
    const { hotkeys } = setup();
    hotkeys.register();
    hotkeys.state().keys[0].ok = false;
    expect(hotkeys.state().keys[0].ok).toBe(true);
  });
});

describe('H6: no keyboard hook anywhere in the face', () => {
  const here = new URL('.', import.meta.url);
  const sources = [
    // package.mjs is the build script: it runs on your terminal, never inside Pseudo, and only copies koffi's files.
    ...readdirSync(here).filter((name) => /\.(js|mjs)$/.test(name) && !name.includes('.test.') && name !== 'package.mjs')
      .map((name) => new URL(name, here)),
    ...readdirSync(new URL('./src/', here)).filter((name) => /\.tsx?$/.test(name) && !name.includes('.test.'))
      .map((name) => new URL(`./src/${name}`, here)),
  ];
  // Hook APIs and the usual packages built on them. Comments are removed first: hotkeys.js explains hooks in words.
  const HOOKS = /SetWindowsHookEx|WH_KEYBOARD|LowLevelKeyboardProc|GetAsyncKeyState|RegisterRawInputDevices|iohook|uiohook|node-global-key-listener|keylogger/i;
  const code = (url) => readFileSync(url, 'utf8').replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|\s)\/\/.*$/gm, '$1');

  it('found the files', () => {
    expect(sources.length).toBeGreaterThan(20);
  });

  it('no source file names a hook API or a hook package', () => {
    for (const url of sources) expect(HOOKS.test(code(url)), url.pathname).toBe(false);
  });

  it('no hook package is installed as a dependency', () => {
    const pkg = JSON.parse(readFileSync(new URL('./package.json', here), 'utf8'));
    for (const name of Object.keys({ ...pkg.dependencies, ...pkg.devDependencies })) expect(HOOKS.test(name), name).toBe(false);
  });

  it('the only Windows function the face calls directly is the popup grant (foreground.js)', () => {
    const native = sources.filter((url) => /koffi/.test(code(url))).map((url) => url.pathname.split('/').pop());
    expect(native).toEqual(['foreground.js']);
    expect(code(new URL('./foreground.js', here))).toContain('AllowSetForegroundWindow');
  });

  it('shortcuts are registered in one place only: main.js hands globalShortcut to hotkeys.js and never calls it', () => {
    const users = sources.filter((url) => /globalShortcut/.test(code(url))).map((url) => url.pathname.split('/').pop()).sort();
    expect(users).toEqual(['hotkeys.js', 'main.js']);
    const main = code(new URL('./main.js', here));
    expect(main).toContain('new Hotkeys(globalShortcut,');
    expect(main).not.toMatch(/globalShortcut\s*\./);
  });
});
