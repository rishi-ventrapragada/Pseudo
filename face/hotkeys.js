/**
 * M37: two global shortcuts, so Pseudo can be called from any app.
 *
 *   Ctrl+Alt+Enter   show Pseudo, or hide it if it is the window you are in (reveal.js)
 *   Ctrl+Alt+T       show Pseudo and start talking; press it again to stop (the page's mic button)
 *
 * What it demonstrates: a global shortcut is a reservation with Windows, not a listener.
 * Electron's globalShortcut calls Windows' RegisterHotKey: "when exactly this combination is
 * pressed, tell me". Windows then sends this process one message per press. Pseudo never sees
 * any other key you type, in any app.
 *
 * The other way to react to keys everywhere is a keyboard HOOK, which receives every key
 * pressed in every program: the shape of a keylogger. Pseudo is a privacy tool, so it has
 * none, and hotkeys.test.mjs fails if one is ever added. The price: a shortcut fires once,
 * when pressed. There is no "while held", so talking from another app is press to start,
 * press to stop, not hold-to-talk (ruled out in the PRD).
 *
 * A combination can be reserved by one program only. If another program got there first,
 * register() returns false: that shortcut stays off, the page says so, and the other one
 * still works. Both are given back when Pseudo quits.
 *
 * That is why the first key is Enter and not Space, as first planned: on this laptop the Claude
 * desktop app already holds Ctrl+Alt+Space (found before M37's live check).
 */

const SHORTCUTS = [
  { id: 'toggle', keys: 'Control+Alt+Enter', label: 'Ctrl+Alt+Enter' },
  { id: 'talk', keys: 'Control+Alt+T', label: 'Ctrl+Alt+T' },
];

class Hotkeys {
  /**
   * @param {{ register: Function, unregister: Function }} globalShortcut Electron's globalShortcut (a fake in tests)
   * @param {{ toggle: () => void, talk: () => void }} actions what each shortcut does
   */
  constructor(globalShortcut, actions) {
    this.shortcuts = globalShortcut;
    this.actions = actions;
    this.results = SHORTCUTS.map(({ id, label }) => ({ id, label, ok: false })); // nothing registered yet
  }

  /** Reserve both. A refusal (or an error) leaves that one off; it never stops the other. */
  register() {
    this.results = SHORTCUTS.map(({ id, keys, label }) => {
      let ok = false;
      try {
        ok = this.shortcuts.register(keys, () => this.actions[id]()) === true;
      } catch {
        ok = false;
      }
      return { id, label, ok };
    });
    return this.state();
  }

  /** What the page shows: each shortcut, and whether Windows gave it to us. */
  state() {
    return { type: 'hotkeys', keys: this.results.map((result) => ({ ...result })) };
  }

  /** Give back the ones we hold (at quit). Only ours: never unregisterAll. */
  release() {
    for (const { id, keys } of SHORTCUTS) {
      const mine = this.results.find((result) => result.id === id);
      if (mine.ok) this.shortcuts.unregister(keys);
      mine.ok = false;
    }
  }
}

module.exports = { Hotkeys, SHORTCUTS };
