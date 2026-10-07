// M38: compact mode, for App. The window itself is resized by the main process (face/window-mode.js);
// the page only does two things: it asks for a mode, and it says whether the bar is showing an answer.
//
// "Showing an answer" is display state, like an open <details>: it starts when you ask a question and ends
// when you press Hide answer. The main process turns it into a size (the bar grows upward) and decides
// by itself when the bar may be always on top; nothing about approval popups is decided here (D11).

import { useEffect, useState } from 'react';

/** Does the bar need its taller size? Yes while the latest turn is open, and whenever the brain has stopped
 *  (the Restart button and its explanation don't fit in the bar). */
export function barGrows(compact: boolean, open: boolean, turns: number, phase: string): boolean {
  return compact && ((open && turns > 0) || phase === 'stopped');
}

export type Compact = {
  on: boolean; // the window is the bar
  grown: boolean; // the bar is showing the latest turn
  setOn(on: boolean): void; // the Compact / Full window button
  open(): void; // a question was asked: show its steps and answer
  close(): void; // Hide answer
};

export function useCompact(compact: boolean, turns: number, phase: string): Compact {
  const [open, setOpen] = useState(false); // a bar starts small, even if the session already has answers
  const grown = barGrows(compact, open, turns, phase);

  useEffect(() => { // the main process sizes the window; in full mode there is nothing to say
    if (compact) window.pseudo.send({ type: 'window_mode', grown });
  }, [compact, grown]);

  return {
    on: compact,
    grown,
    setOn(on) {
      setOpen(false);
      window.pseudo.send({ type: 'window_mode', compact: on }); // the answer (`window_mode`) updates state.compact
    },
    open: () => setOpen(true),
    close: () => setOpen(false),
  };
}
