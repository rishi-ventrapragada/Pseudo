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
 *
 * (M36) How the window is shown moved to reveal.js, which also starts the brain if this
 * Pseudo was started hidden: double-clicking Pseudo.exe is one of the ways to wake it.
 */

/**
 * @param {{ requestSingleInstanceLock: () => boolean, on: (event: string, listener: () => void) => void }} app Electron's app
 * @param {() => void} show brings the first Pseudo's window to you (Reveal.show)
 * @returns {boolean} true if this is the first Pseudo; false means: quit, another one is running
 */
function onlyOne(app, show) {
  if (!app.requestSingleInstanceLock()) return false;
  app.on('second-instance', () => show());
  return true;
}

module.exports = { onlyOne };
