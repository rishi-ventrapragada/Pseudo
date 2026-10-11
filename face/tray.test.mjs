// M36: the tray icon of a hidden start (tray.js). Electron's Tray, Menu and nativeImage are fakes that
// record what they were given, so no real icon is ever put in the taskbar.
// M44: the icon is pseudo.ico, the same file as the window's; M36's drawn "P" and its pixel tests are gone.
import { existsSync } from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { describe, expect, it } from 'vitest';

const require = createRequire(import.meta.url);
const { createTray, trayMenu } = require('./tray.js');
const { ICON, WINDOW_LOOK } = require('./window-look.js');

function fakeElectron() {
  const made = { trays: [], images: [] };
  class Tray {
    constructor(image) {
      this.image = image;
      this.listeners = {};
      made.trays.push(this);
    }
    setToolTip(text) { this.tip = text; }
    setContextMenu(menu) { this.menu = menu; }
    on(event, listener) { this.listeners[event] = listener; }
  }
  const Menu = { buildFromTemplate: (template) => template };
  const nativeImage = { createFromPath: (file) => { made.images.push(file); return 'image'; } };
  return { Tray, Menu, nativeImage, made };
}

describe('the icon', () => {
  it("M44: is pseudo.ico, beside the main-process files, and the window uses the very same file", () => {
    expect(path.basename(ICON)).toBe('pseudo.ico');
    expect(path.dirname(ICON)).toBe(path.dirname(require.resolve('./tray.js')));
    expect(existsSync(ICON)).toBe(true);
    expect(WINDOW_LOOK.icon).toBe(ICON);
  });
});

describe('createTray', () => {
  it('makes one tray named Pseudo from pseudo.ico', () => {
    const electron = fakeElectron();
    const tray = createTray(electron, () => {}, () => {});
    expect(electron.made.trays).toEqual([tray]);
    expect(tray.tip).toBe('Pseudo');
    expect(tray.image).toBe('image');
    expect(electron.made.images).toEqual([ICON]);
  });

  it('a click shows Pseudo', () => {
    const electron = fakeElectron();
    let shown = 0;
    const tray = createTray(electron, () => { shown += 1; }, () => {});
    tray.listeners.click({ some: 'event' });
    expect(shown).toBe(1);
  });

  it('the right-click menu is Show and Quit, each doing only its own thing', () => {
    const electron = fakeElectron();
    const done = [];
    const tray = createTray(electron, () => done.push('show'), () => done.push('quit'));
    expect(tray.menu.map((item) => item.label)).toEqual(['Show', 'Quit']);
    tray.menu[0].click();
    expect(done).toEqual(['show']);
    tray.menu[1].click();
    expect(done).toEqual(['show', 'quit']);
  });

  it('trayMenu passes none of Electron\'s click arguments on', () => {
    const got = [];
    trayMenu((...args) => got.push(args), () => {})[0].click({ menuItem: true }, { window: true });
    expect(got).toEqual([[]]);
  });
});
