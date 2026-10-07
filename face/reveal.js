/**
 * M36: the one way Pseudo's window is shown, and the lazy brain start (M35's pick, D27).
 *
 * What it demonstrates: lazy start. Started with Windows, Pseudo opens hidden and starts only
 * the face: loading Python, spaCy and the names list at every sign-in cost 9.6 CPU-seconds in
 * M35, whether or not Pseudo was used that day. So the brain is started the first time the
 * window is shown, and then stays.
 *
 * Every way of showing Pseudo goes through show(): the tray icon (tray.js) and a second
 * launch of Pseudo.exe (single-instance.js). That is why the brain start lives here: no way
 * of showing the window can forget it.
 *
 * The brain is started ONCE. If it stops later, the page says so and offers Restart, as
 * before; showing the window again never restarts it behind your back.
 */

class Reveal {
  /**
   * @param {() => object | null} getWindow the face's window right now, or null before it exists
   * @param {() => void} startBrain starts the brain process (BrainProcess.start)
   */
  constructor(getWindow, startBrain) {
    this.getWindow = getWindow;
    this.start = startBrain;
    this.started = false;
  }

  /** Start the brain unless that was already done. Called at launch when Pseudo is opened by hand. */
  startBrain() {
    if (this.started) return;
    this.started = true;
    this.start();
  }

  /** Bring the window to you. False if there is no window to show (still starting, or closing). */
  show() {
    const win = this.getWindow();
    if (!win || win.isDestroyed()) return false;
    if (win.isMinimized()) win.restore();
    win.show();
    win.focus();
    this.startBrain();
    return true;
  }
}

module.exports = { Reveal };
