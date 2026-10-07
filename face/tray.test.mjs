// M36: the tray icon of a hidden start (tray.js). Electron's Tray, Menu and nativeImage are fakes that
// record what they were given, so no real icon is ever put in the taskbar.
import { createRequire } from 'node:module';
import { describe, expect, it } from 'vitest';

const { PIXELS, createTray, iconBitmap, trayMenu } = createRequire(import.meta.url)('./tray.js');

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
  const nativeImage = { createFromBitmap: (bitmap, options) => { made.images.push({ bitmap, options }); return 'image'; } };
  return { Tray, Menu, nativeImage, made };
}

describe('the icon', () => {
  it('is a 16 x 16 map of three kinds of pixel', () => {
    expect(PIXELS).toHaveLength(16);
    for (const row of PIXELS) expect(row).toMatch(/^[.#P]{16}$/);
  });

  it('becomes B, G, R, A bytes: see-through corners, a blue square, a white letter', () => {
    const bitmap = iconBitmap();
    expect(bitmap).toHaveLength(16 * 16 * 4);
    const at = (x, y) => [...bitmap.subarray((y * 16 + x) * 4, (y * 16 + x) * 4 + 4)];
    expect(at(0, 0)).toEqual([0, 0, 0, 0]);
    expect(at(8, 1)).toEqual([0xd1, 0x56, 0x34, 0xff]);
    expect(at(4, 3)).toEqual([0xff, 0xff, 0xff, 0xff]);
  });

  it('at scale 2 every pixel is doubled', () => {
    const big = iconBitmap(2);
    expect(big).toHaveLength(32 * 32 * 4);
    const at = (x, y) => [...big.subarray((y * 32 + x) * 4, (y * 32 + x) * 4 + 4)];
    for (const [x, y] of [[8, 6], [9, 6], [8, 7], [9, 7]]) expect(at(x, y)).toEqual([0xff, 0xff, 0xff, 0xff]); // pixel (4, 3)
    expect(at(1, 1)).toEqual([0, 0, 0, 0]);
  });
});

describe('createTray', () => {
  it('makes one tray named Pseudo from the 32 x 32 icon', () => {
    const electron = fakeElectron();
    const tray = createTray(electron, () => {}, () => {});
    expect(electron.made.trays).toEqual([tray]);
    expect(tray.tip).toBe('Pseudo');
    expect(tray.image).toBe('image');
    expect(electron.made.images[0].options).toEqual({ width: 32, height: 32, scaleFactor: 2 });
    expect(electron.made.images[0].bitmap).toHaveLength(32 * 32 * 4);
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
