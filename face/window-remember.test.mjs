// M38: what the window remembers (window-mode.js, window-store.js), and C3: the bar is an ordinary window.
import { readdirSync, readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { describe, expect, it } from 'vitest';
import { BAR, setup } from './window-fakes.mjs';

const { fileStore } = createRequire(import.meta.url)('./window-store.js');

describe('WindowMode: what is remembered', () => {
  it('C5: your size and place, per mode', () => {
    const { mode, win, written } = setup();
    win.byUser({ x: 40, y: 50, width: 1000, height: 700 });
    expect(written.at(-1).full).toEqual({ x: 40, y: 50, width: 1000, height: 700 });
    mode.setMode('compact');
    win.byUser({ x: 300, y: 600, width: 600, height: 150 });
    expect(written.at(-1).compact).toEqual({ x: 300, y: 600, width: 600, height: 150 });
    mode.setMode('full');
    expect(win.getBounds()).toEqual({ x: 40, y: 50, width: 1000, height: 700 });
    mode.setMode('compact');
    expect(win.getBounds()).toEqual({ x: 300, y: 600, width: 600, height: 150 });
  });

  it('our own placing is never remembered, even when the screen reports it a few pixels off', () => {
    const { mode, win, written } = setup();
    mode.setMode('compact'); // one write: the mode
    const before = written.length;
    win.bounds = { ...BAR, width: BAR.width + 2, height: BAR.height + 1 };
    win.handlers.resized();
    win.handlers.moved();
    expect(written.length).toBe(before);
  });

  it('resizing the grown bar remembers the answer height and keeps the bar at its bottom edge', () => {
    const { mode, win, written } = setup({ mode: 'compact' });
    mode.setGrown(true);
    win.byUser({ x: 900, y: 200, width: 520, height: 500 });
    expect(written.at(-1).grownHeight).toBe(500);
    expect(written.at(-1).compact).toEqual({ x: 900, y: 200 + 500 - 132, width: 520, height: 132 });
    mode.setGrown(false);
    expect(win.getBounds()).toEqual({ x: 900, y: 568, width: 520, height: 132 });
  });

  it('a maximized size is not remembered as the window\'s size', () => {
    const { win, written } = setup();
    win.maximized = true;
    win.byUser({ x: -8, y: -8, width: 1552, height: 832 });
    expect(written).toEqual([]);
  });
});

describe('fileStore', () => {
  const fs = (text, fail = false) => ({
    readFileSync: () => { if (text === null) throw new Error('ENOENT'); return text; },
    writeFileSync: (_file, data) => { if (fail) throw new Error('EACCES'); fs.wrote = data; },
  });

  it('reads the saved object; a missing or broken file is null', () => {
    expect(fileStore('x.json', fs('{"mode":"compact"}')).read()).toEqual({ mode: 'compact' });
    for (const bad of [null, 'not json', '7', 'null']) expect(fileStore('x.json', fs(bad)).read()).toBeNull();
  });

  it('a file that cannot be written is not an error', () => {
    expect(() => fileStore('x.json', fs('{}', true)).write({ mode: 'full' })).not.toThrow();
  });
});

describe('C3: the bar is an ordinary window', () => {
  const here = new URL('.', import.meta.url);
  // M39: every folder of the face's own code (src/components/ and its ui/ too), not only the top two.
  const NOT_OURS = /^(node_modules|dist|out)([\\/]|$)/;
  const sources = readdirSync(here, { recursive: true })
    .filter((name) => !NOT_OURS.test(name) && /\.(js|mjs|ts|tsx)$/.test(name) && !name.includes('.test.'))
    .map((name) => new URL(name.replaceAll('\\', '/'), here));
  // Click-through, unfocusable, see-through or off-the-taskbar windows. Comments are removed first: window-mode.js
  // explains in words why there are none.
  const OVERLAY = /setIgnoreMouseEvents|setFocusable|focusable\s*:|transparent\s*:|skipTaskbar|setSkipTaskbar|frame\s*:\s*false|WS_EX_/;
  const code = (url) => readFileSync(url, 'utf8').replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|\s)\/\/.*$/gm, '$1');

  it('found the files, in every folder', () => {
    expect(sources.length).toBeGreaterThan(40);
    expect(sources.some((url) => url.pathname.includes('/src/components/ui/'))).toBe(true);
  });

  it('no source file makes a window click-through, unfocusable, see-through, frameless or hidden from the taskbar', () => {
    for (const url of sources) expect(OVERLAY.test(code(url)), url.pathname).toBe(false);
  });

  it("M39: the title bar is blended only one way: 'hidden' with Electron's own buttons, set in window-look.js", () => {
    const setting = sources.filter((url) => /titleBarStyle|titleBarOverlay/.test(code(url)));
    expect(setting.map((url) => url.pathname.split('/').pop())).toEqual(['window-look.js']);
    const look = code(setting[0]);
    expect(look).toMatch(/titleBarStyle:\s*'hidden'/);
    expect(look).toMatch(/titleBarOverlay:\s*\{/); // the buttons Windows users expect, drawn by Electron
  });
});
