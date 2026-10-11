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
 * (M44) The icon is Pseudo's own, pseudo.ico: the same file as the window's and the taskbar's
 * (window-look.js), so there is one icon. It replaces M36's "P", which was drawn here from a pixel map.
 * An .ico holds a picture per size, and Windows picks the right one for the tray at each scaling:
 * 16 px at 100%, 20 at 125%, 24 at 150%, 32 at 200%.
 */

const { ICON } = require('./window-look');

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
  const tray = new electron.Tray(electron.nativeImage.createFromPath(ICON));
  tray.setToolTip('Pseudo');
  tray.setContextMenu(electron.Menu.buildFromTemplate(trayMenu(onShow, onQuit)));
  tray.on('click', () => onShow());
  return tray;
}

module.exports = { createTray, trayMenu };
