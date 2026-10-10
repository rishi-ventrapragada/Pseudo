/**
 * M38 (moved out of window-mode.js in M43, unchanged): when the compact bar is always on top, and when it gives
 * that up.
 *
 * What it demonstrates: a rule decided from messages, in the main process, not in the page (D11).
 *   - While a tool waits (its approval popup may be open), the bar gives up always-on-top and takes it back
 *     when the tool's result arrives. Decided from the brain's own messages, so an approval popup can never
 *     end up under the bar (D13, C2).
 *   - A hidden window is never always-on-top. Measured in M38's step 0: hiding a bar that still is hands the
 *     keyboard to the taskbar, 5 of 5; letting go first (letGo, called by reveal.js before every hide) gave it
 *     back to the window you came from, 5 of 5.
 * The full window is never on top.
 */

class OnTop {
  /**
   * @param {() => object | null} getWindow the face's window, or null when there is none to change
   * @param {() => boolean} isBar is the window the compact bar right now? (window-mode.js knows)
   */
  constructor(getWindow, isBar) {
    this.getWindow = getWindow;
    this.isBar = isBar;
    this.waiting = false; // a tool is running: its approval popup may be open
  }

  /** Every message from the brain passes here: a running tool takes the bar out of always-on-top. */
  fromBrain(message) {
    if (message.type === 'event' && message.kind === 'tool_call') this.waiting = true;
    else if ((message.type === 'event' && message.kind === 'tool_result') || message.type === 'turn_done') this.waiting = false;
    else return;
    this.apply();
  }

  brainStopped() {
    this.waiting = false;
    this.apply();
  }

  /** Before the window is hidden: stop being always on top, or the keyboard goes to the taskbar (step 0). */
  letGo() {
    const win = this.getWindow();
    if (win) win.setAlwaysOnTop(false);
  }

  /** On top only as the bar, with no tool waiting, and visible. Called after every change of any of those. */
  apply() {
    const win = this.getWindow();
    if (win) win.setAlwaysOnTop(this.isBar() && !this.waiting && win.isVisible());
  }
}

module.exports = { OnTop };
