/**
 * M38: the window's two modes, full and compact (a small always-on-top bar).
 *
 * What it demonstrates: one window, two shapes. Step 0 measured the simplest candidate (O1):
 * the SAME window made small and always on top, title bar kept. It passed, so nothing is
 * recreated on a switch: the page, its state and the brain's pipe all stay as they are.
 *
 * The rules that live here, in the main process, not in the page:
 *   - While a tool waits (its approval popup may be open), the bar gives up always-on-top and
 *     takes it back when the tool's result arrives. Decided from the brain's own messages.
 *   - A hidden window is never always-on-top. Measured in step 0: hiding a bar that still is
 *     hands the keyboard to the taskbar, 5 of 5; letting go first (letGo, called by reveal.js
 *     before every hide) gave it back to the window you came from, 5 of 5.
 *   - Sizes and places are remembered in a small file (window-store.js), and every one read back goes through
 *     fit() (window-bounds.js), so a place that is off-screen today is corrected.
 *   - Only YOUR resizing and moving is remembered, never what the window reports after we set
 *     it. On this laptop's 125% screen a window asked to be 982 wide reports 983, and a switch
 *     that re-read its own size grew by 1 to 2 pixels every time (step 0). So the size we asked
 *     for is kept, and setExact() asks once more with the difference taken off.
 *
 * The bar is an ordinary window: it takes clicks and the keyboard like any other. It is never
 * made click-through or unfocusable, and window-mode.test.mjs fails if that is ever added:
 * pseudo_hands tells user windows from overlays by exactly those properties (M12).
 */

const { GROWN, SIZES, barFrom, fit, grownFrom } = require('./window-bounds');

const DRIFT = 4; // pixels: a difference this small after setBounds is the screen's scaling, not you

class WindowMode {
  /**
   * @param {() => object | null} getWindow the face's window right now, or null before it exists
   * @param {{ getPrimaryDisplay: Function, getAllDisplays: Function }} screen Electron's screen (a fake in tests)
   * @param {{ read: () => object | null, write: (data: object) => void }} store window-store.js (a fake in tests)
   */
  constructor(getWindow, screen, store) {
    this.getWindow = getWindow;
    this.screen = screen;
    this.store = store;
    const saved = store.read() ?? {};
    this.mode = saved.mode === 'compact' ? 'compact' : 'full';
    this.full = saved.full; // checked by fit() every time it is used
    this.bar = saved.compact;
    this.grownHeight = saved.grownHeight;
    this.grown = false; // the bar is showing an answer
    this.waiting = false; // a tool is running: its approval popup may be open
    this.asked = null; // the bounds we last set, to tell our own changes from yours
  }

  /** Every screen's work area (the screen minus the taskbar), the main screen first. */
  areas() {
    const main = this.screen.getPrimaryDisplay();
    return [main.workArea, ...this.screen.getAllDisplays().filter((display) => display.id !== main.id).map((d) => d.workArea)];
  }

  /** Where the window should be right now, and its smallest size. */
  wanted() {
    const areas = this.areas();
    if (this.mode === 'full') return fit(this.full, 'full', areas);
    const bar = fit(this.bar, 'compact', areas);
    return this.grown ? grownFrom(bar, this.grownHeight, areas) : bar;
  }

  minimum() {
    const { minWidth, minHeight } = SIZES[this.mode];
    return [minWidth, this.mode === 'compact' && this.grown ? GROWN.minHeight : minHeight];
  }

  /** For `new BrowserWindow`: the remembered mode's size, place and minimum. */
  options() {
    const [minWidth, minHeight] = this.minimum();
    return { ...this.wanted(), minWidth, minHeight };
  }

  usable() {
    const win = this.getWindow();
    return win && !win.isDestroyed() ? win : null;
  }

  /** Called once, when the window exists. */
  attach(win) {
    win.on('resized', () => this.remember()); // Windows: once, when you let go of the edge
    win.on('moved', () => this.remember());
    win.on('show', () => this.applyTop()); // a hidden window is never on top; shown again, the bar is
    this.place();
  }

  /** Put the window where this mode wants it. */
  place() {
    const win = this.usable();
    if (!win) return;
    if (win.isMaximized()) win.unmaximize();
    const want = this.wanted();
    win.setMinimumSize(...this.minimum());
    this.setExact(win, want);
    this.asked = want;
    this.applyTop();
  }

  /** Ask for `want`; if the window comes out a few pixels off (screen scaling), ask again with that taken off. */
  setExact(win, want) {
    win.setBounds(want);
    const got = win.getBounds();
    const [wide, high] = [got.width - want.width, got.height - want.height];
    if ((wide || high) && Math.abs(wide) <= DRIFT && Math.abs(high) <= DRIFT) {
      win.setBounds({ ...want, width: want.width - wide, height: want.height - high });
    }
  }

  /** You resized or moved the window: remember it for this mode. Our own placing is not remembered. */
  remember() {
    const win = this.usable();
    if (!win || win.isMaximized() || win.isMinimized()) return;
    const got = win.getBounds();
    const ours = this.asked && got.x === this.asked.x && got.y === this.asked.y
      && Math.abs(got.width - this.asked.width) <= DRIFT && Math.abs(got.height - this.asked.height) <= DRIFT;
    if (ours) return;
    if (this.mode === 'full') this.full = got;
    else if (this.grown) { // the grown bar: its height is the answer area's; the bar itself keeps its bottom edge
      const areas = this.areas();
      this.grownHeight = got.height;
      this.bar = barFrom(got, fit(this.bar, 'compact', areas).height, areas);
    } else this.bar = got;
    this.asked = got;
    this.save();
  }

  save() {
    this.store.write({ mode: this.mode, full: this.full, compact: this.bar, grownHeight: this.grownHeight });
  }

  setMode(mode) {
    if (mode === this.mode) return;
    this.mode = mode;
    this.grown = false;
    this.place();
    this.save();
  }

  /** The page says whether the bar is showing an answer (display state); the size is decided here. */
  setGrown(on) {
    if (this.mode !== 'compact' || on === this.grown) return;
    this.grown = on;
    this.place();
  }

  /** The page's `window_mode` message: only real true/false values are acted on. Returns what the page shows. */
  fromPage(message) {
    if (typeof message.compact === 'boolean') this.setMode(message.compact ? 'compact' : 'full');
    if (typeof message.grown === 'boolean') this.setGrown(message.grown);
    return this.state();
  }

  /** Every message from the brain passes here: a running tool takes the bar out of always-on-top. */
  fromBrain(message) {
    if (message.type === 'event' && message.kind === 'tool_call') this.waiting = true;
    else if ((message.type === 'event' && message.kind === 'tool_result') || message.type === 'turn_done') this.waiting = false;
    else return;
    this.applyTop();
  }

  brainStopped() {
    this.waiting = false;
    this.applyTop();
  }

  /** Before the window is hidden: stop being always on top, or the keyboard goes to the taskbar (step 0). */
  letGo() {
    const win = this.usable();
    if (win) win.setAlwaysOnTop(false);
  }

  applyTop() {
    const win = this.usable();
    if (win) win.setAlwaysOnTop(this.mode === 'compact' && !this.waiting && win.isVisible());
  }

  state() {
    return { type: 'window_mode', compact: this.mode === 'compact' };
  }
}

module.exports = { DRIFT, WindowMode };
