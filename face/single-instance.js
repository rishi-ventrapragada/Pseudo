/**
 * M34: one Pseudo at a time.
 *
 * What it demonstrates: Electron's single-instance lock. The first Pseudo to start takes a
 * lock (one per profile folder). A second launch asks for the same lock, doesn't get it,
 * and must quit before it opens a window or starts a second brain. Electron then tells the
 * FIRST one about it with a `second-instance` event, and we answer by showing our window:
 * double-clicking Pseudo.exe again just brings Pseudo back.
 *
 * Why it matters here: two Pseudos would mean two brains and two pseudo_hands, each with
 * its own approval popups, for one person at one keyboard.
 *
 * `npm start` and Pseudo.exe keep separate profile folders, so one of each can still run.
 */

/**
 * @param {{ requestSingleInstanceLock: () => boolean, on: (event: string, listener: () => void) => void }} app Electron's app
 * @param {() => object | null} getWindow the face's window right now, or null before it exists
 * @returns {boolean} true if this is the first Pseudo; false means: quit, another one is running
 */
function onlyOne(app, getWindow) {
  if (!app.requestSingleInstanceLock()) return false;
  app.on('second-instance', () => {
    const win = getWindow();
    if (!win || win.isDestroyed()) return; // still starting, or closing: nothing to show
    if (win.isMinimized()) win.restore();
    win.show();
    win.focus();
  });
  return true;
}

module.exports = { onlyOne };
