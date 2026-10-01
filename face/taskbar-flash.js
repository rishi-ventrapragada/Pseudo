/**
 * M18: flashing the face's taskbar button while a tool runs and you're in another window.
 *
 * While a tool waits for its result, pseudo_hands may have its approval popup open (D13).
 * If you're in another window, the face can't bring that popup forward for you (only the
 * window you're using may, foreground.js), so it flashes its taskbar button instead, with
 * Electron's flashFrame, until the tool's result arrives. If the face is the window you're
 * using, the banner inside it is enough and nothing flashes.
 *
 * Like the banner, this happens for every tool call: the face can't know which tools ask
 * for approval, because it decides nothing (D11).
 */

class TaskbarFlash {
  /**
   * @param {(on: boolean) => void} flash starts or stops flashing (win.flashFrame; a fake in tests)
   * @param {() => boolean} isFocused is the face the window you're using? (win.isFocused)
   */
  constructor(flash, isFocused) {
    this.flash = flash;
    this.isFocused = isFocused;
    this.flashing = false;
  }

  /** Every message from the brain passes here: a tool_call may start flashing; its result stops it. */
  fromBrain(message) {
    const kind = message.type === 'event' ? message.kind : null;
    if (kind === 'tool_call' && !this.isFocused()) this.set(true);
    else if (kind === 'tool_result' || message.type === 'turn_done') this.set(false);
  }

  /** The brain stopped: no tool is waiting any more. */
  brainStopped() {
    this.set(false);
  }

  set(on) {
    if (on === this.flashing) return; // never stop a flash we didn't start
    this.flashing = on;
    this.flash(on);
  }
}

module.exports = { TaskbarFlash };
