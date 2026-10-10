// M38: compact mode, for App. The window itself is resized by the main process (face/window-mode.js);
// the page only does two things: it asks for a mode, and it says whether the bar is showing an answer.
//
// "Showing an answer" is display state, like an open <details>: it starts when you ask a question and ends
// when you press Hide answer. The main process turns it into a size (the bar grows upward) and decides
// by itself when the bar may be always on top; nothing about approval popups is decided here (D11).
//
// M43: the grown bar is as tall as what it shows (the mockup's). useBarFit measures the bar's three parts and
// sends that height with `grown: true`; the main process keeps it under your cap and on the screen.

import { useEffect, useRef, useState } from 'react';

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

  useEffect(() => { // the main process sizes the window. Growing is said by useBarFit, WITH the height, so the
    if (compact && !grown) window.pseudo.send({ type: 'window_mode', grown: false }); // bar never jumps to its cap first
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

/** M43: the height the grown bar wants: its top row, everything the grown area holds (its natural height, not the
 *  room it has now), and the question row. Rounded up, so nothing is cut off by a fraction of a pixel. */
export function barHeight(top: number, content: number, bottom: number): number {
  return Math.ceil(top + content + bottom);
}

const STEP = 2; // pixels: a smaller change isn't worth resizing the window for

/** M43: while the bar is grown, measure it whenever what it shows changes, and tell the main process. */
export function useBarFit(grown: boolean) {
  const top = useRef<HTMLDivElement>(null);
  const content = useRef<HTMLDivElement>(null);
  const bottom = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!grown) return;
    let sent = 0;
    const measure = () => {
      const [t, c, b] = [top, content, bottom].map((part) => part.current?.getBoundingClientRect().height ?? 0);
      const height = barHeight(t, c, b);
      if (Math.abs(height - sent) < STEP) return;
      sent = height;
      window.pseudo.send({ type: 'window_mode', grown: true, height });
    };
    const watch = new ResizeObserver(measure); // fires once at the start, then on every change of size
    for (const part of [content, bottom]) if (part.current) watch.observe(part.current);
    return () => watch.disconnect();
  }, [grown]);
  return { top, content, bottom };
}
