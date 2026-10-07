/**
 * M36: the tray icon of a Pseudo that was started hidden.
 *
 * What it demonstrates: a tray icon is how a program with no visible window stays reachable.
 * Started with Windows, Pseudo opens no window, so without this icon there would be no sign
 * that it is running and no way to bring it up or stop it (until M37's hotkeys).
 *   - a click on the icon shows Pseudo (reveal.js, which also starts the brain the first time);
 *   - a right-click offers Show and Quit.
 * Opened by hand, Pseudo has a window, so it gets no tray icon. The close button still quits.
 *
 * The icon is drawn here from a 16 x 16 pixel map, so no image file is committed: each
 * character is one pixel. A tray wants raw pixels as B, G, R, A bytes; `scale` 2 doubles every
 * pixel, which gives Windows a sharp 32 x 32 icon on screens set above 100%.
 */

const SIZE = 16;
const PIXELS = [
  '..############..',
  '.##############.',
  '################',
  '####PPPPPP######',
  '####PPPPPPP#####',
  '####PP###PPP####',
  '####PP####PP####',
  '####PP###PPP####',
  '####PPPPPPP#####',
  '####PPPPPP######',
  '####PP##########',
  '####PP##########',
  '####PP##########',
  '################',
  '.##############.',
  '..############..',
];
const COLORS = {
  '.': [0, 0, 0, 0], // see-through: the rounded corners
  '#': [0xd1, 0x56, 0x34, 0xff], // the page's blue (#3456d1), as B, G, R, A
  P: [0xff, 0xff, 0xff, 0xff], // the letter, white
};

/** The icon's pixels as one buffer of B, G, R, A bytes, (16 * scale) pixels wide and high. */
function iconBitmap(scale = 1) {
  const side = SIZE * scale;
  const bitmap = Buffer.alloc(side * side * 4);
  for (let y = 0; y < side; y += 1) {
    for (let x = 0; x < side; x += 1) {
      const color = COLORS[PIXELS[Math.floor(y / scale)][Math.floor(x / scale)]];
      bitmap.set(color, (y * side + x) * 4);
    }
  }
  return bitmap;
}

/** The right-click menu. */
function trayMenu(onShow, onQuit) {
  return [{ label: 'Show', click: () => onShow() }, { label: 'Quit', click: () => onQuit() }];
}

/**
 * @param {{ Tray: Function, Menu: object, nativeImage: object }} electron the three Electron parts a tray needs
 * @param {() => void} onShow bring Pseudo's window up (Reveal.show)
 * @param {() => void} onQuit quit Pseudo (app.quit, which stops the brain first)
 * @returns {object} the tray; keep it, or it is garbage-collected and the icon disappears
 */
function createTray(electron, onShow, onQuit) {
  const image = electron.nativeImage.createFromBitmap(iconBitmap(2), { width: SIZE * 2, height: SIZE * 2, scaleFactor: 2 });
  const tray = new electron.Tray(image);
  tray.setToolTip('Pseudo');
  tray.setContextMenu(electron.Menu.buildFromTemplate(trayMenu(onShow, onQuit)));
  tray.on('click', () => onShow());
  return tray;
}

module.exports = { PIXELS, createTray, iconBitmap, trayMenu };
