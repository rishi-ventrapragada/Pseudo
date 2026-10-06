// M32: the warm Claude Code session: its switch, and what the brain says about it (D26).
// Display only. The rules are in the brain (pseudo_brain/warm_sessions.py); useWarm.ts remembers the switch.
// The memory figure is the session's whole process tree, Claude Code plus its pseudo_hands, measured
// by the brain every few seconds. It is shown only while a session is open.

import type { Warm } from './protocol';

type Props = { warm: Warm | null; warmOn: boolean; setWarmOn(on: boolean): void };

/** One line: what is running right now, and what your next action request will do. */
export function warmLine(warm: Warm | null, warmOn: boolean): string {
  if (!(warm ? warm.on : warmOn)) { // the brain's word once it has spoken; until then, the switch
    return 'Off: every action request starts Claude Code (about 20 s), and nothing is kept running.';
  }
  if (warm?.open) {
    const memory = warm.ram_mb === null ? 'measuring its memory' : `${Math.round(warm.ram_mb)} MB`;
    return `Open: ${memory} · ${warm.asked} of ${warm.of} requests · stopped after ${warm.idle_minutes} idle minutes.`;
  }
  const last = warm?.note ? ` (${warm.note})` : '';
  return `None open${last}. Your next action request starts Claude Code (about 20 s), then one stays open.`;
}

export function WarmControl({ warm, warmOn, setWarmOn }: Props) {
  return (
    <div className={warm?.open ? 'warm open' : 'warm'} role="group" aria-label="Warm Claude Code session">
      <label className="keep">
        <input type="checkbox" checked={warmOn} onChange={(event) => setWarmOn(event.target.checked)} />
        Keep Claude Code warm
      </label>
      <span className="warm-state">{warmLine(warm, warmOn)}</span>
    </div>
  );
}
