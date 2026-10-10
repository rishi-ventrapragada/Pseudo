// M37: the two global shortcuts. Display only: they are registered by the main process (face/hotkeys.js),
// which reports for each whether Windows gave it to Pseudo. A shortcut another program already holds is off
// here, and this is where you find that out.
// M39: the Shortcuts section of Settings, one row per shortcut with its keys drawn as key caps (from the mockup).

import type { Hotkey } from './protocol';

const DOES: Record<string, string> = {
  toggle: 'shows or hides Pseudo from any app',
  talk: 'starts and stops talking',
};

/** What one shortcut does, or that it is off because another program holds it. */
function does(key: Hotkey): string {
  return key.ok ? DOES[key.id] ?? 'is a Pseudo shortcut' : 'is held by another program, so it is off here';
}

/** What each shortcut does, or that it is off because another program holds it. */
export function hotkeysLine(keys: Hotkey[]): string {
  return keys.map((key) => `${key.label} ${does(key)}`).join(' · ');
}

const capital = (text: string) => text.charAt(0).toUpperCase() + text.slice(1);

function Keys({ label }: { label: string }) {
  return (
    <span className="flex gap-1">
      {label.split('+').map((cap) => (
        <kbd key={cap} className="rounded-[5px] border border-control bg-bubble px-1.5 py-px font-mono text-[11.5px] text-ink">
          {cap}
        </kbd>
      ))}
    </span>
  );
}

export function HotkeysNote({ keys }: { keys: Hotkey[] | null }) {
  if (!keys || keys.length === 0) return null; // the main process hasn't said yet
  const off = keys.some((key) => !key.ok);
  return (
    <div role="note" aria-label="Shortcuts" data-off={off} className="py-3.5">
      <div className="text-sm font-medium">Shortcuts</div>
      <div className="mt-2 grid grid-cols-[minmax(0,1fr)_auto] gap-y-2 text-[13px] text-muted">
        {keys.map((key) => (
          <div key={key.id} className="contents">
            <span className={key.ok ? '' : 'text-ink-soft'}>{key.ok ? capital(does(key)) : 'Off here: another program holds it'}</span>
            <Keys label={key.label} />
          </div>
        ))}
        <span>Talk while held, in Pseudo</span>
        <Keys label="Ctrl+Space" />
      </div>
    </div>
  );
}
