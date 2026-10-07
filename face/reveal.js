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
 *
 * (M37) hide() and toggle(), for the show-or-hide shortcut (hotkeys.js). Hiding takes TWO
 * steps: give up the keyboard (blur), then hide. Measured in the live check: hide() alone
 * leaves the invisible window as Windows' front window, 10 of 10 times, so what you typed
 * next would have gone into a Pseudo you can't see. With blur() first, the window you came
 * from had the keyboard back 10 of 10.
 * Before the window disappears, `beforeHide` runs: main.js uses it to make sure a tray icon
 * exists, so a hidden Pseudo can always be reached, even if a shortcut couldn't be registered.
 * (M38) It also makes the compact bar stop being always-on-top first (window-mode.js, letGo): from an
 * always-on-top window, blur() hands the keyboard to the taskbar instead of the window underneath
 * (step 0: 5 of 5). The bar is on top again as soon as it is shown.
 */

class Reveal {
  /**
   * @param {() => object | null} getWindow the face's window right now, or null before it exists
   * @param {() => void} startBrain starts the brain process (BrainProcess.start)
   * @param {() => void} beforeHide runs right before the window is hidden (M37: make the tray icon)
   */
  constructor(getWindow, startBrain, beforeHide = () => {}) {
    this.getWindow = getWindow;
    this.start = startBrain;
    this.beforeHide = beforeHide;
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

  /** (M37) Hide the window. The brain keeps running (D27). False if there is no window to hide. */
  hide() {
    const win = this.getWindow();
    if (!win || win.isDestroyed()) return false;
    this.beforeHide();
    win.blur(); // first let go of the keyboard: Windows hands it to the window underneath
    win.hide();
    return true;
  }

  /** (M37) The shortcut: hide Pseudo if it is the window you are in; otherwise bring it to you. */
  toggle() {
    const win = this.getWindow();
    const inFront = Boolean(win) && !win.isDestroyed() && win.isVisible() && win.isFocused();
    return inFront ? this.hide() : this.show();
  }
}

module.exports = { Reveal };
