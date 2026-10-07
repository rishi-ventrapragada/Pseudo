// M37: one line about the two global shortcuts. Display only: they are registered by the main process
// (face/hotkeys.js), which reports for each whether Windows gave it to Pseudo. A shortcut another program
// already holds is off here, and this line is where you find that out.

import type { Hotkey } from './protocol';

const DOES: Record<string, string> = {
  toggle: 'shows or hides Pseudo from any app',
  talk: 'starts and stops talking',
};

/** What each shortcut does, or that it is off because another program holds it. */
export function hotkeysLine(keys: Hotkey[]): string {
  return keys
    .map((key) => (key.ok ? `${key.label} ${DOES[key.id] ?? 'is a Pseudo shortcut'}`
                          : `${key.label} is held by another program, so it is off here`))
    .join(' · ');
}

export function HotkeysNote({ keys }: { keys: Hotkey[] | null }) {
  if (!keys || keys.length === 0) return null; // the main process hasn't said yet
  const off = keys.some((key) => !key.ok);
  return <p className={off ? 'hint hotkeys off' : 'hint hotkeys'} role="note" aria-label="Shortcuts">{hotkeysLine(keys)}</p>;
}
