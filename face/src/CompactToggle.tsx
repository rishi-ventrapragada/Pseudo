// M38: the button that switches between the full window and the compact bar, and the bar's Hide answer button.
// Display only: useCompact.ts sends the request, and face/window-mode.js (the main process) resizes the window.
import './compact.css';
import type { Compact } from './useCompact';

export const TOGGLE_HELP = {
  toBar: 'A small bar that stays on top of your other windows',
  toFull: 'Back to the full window: sessions, providers and settings',
};

export function CompactToggle({ compact }: { compact: Compact }) {
  return (
    <button type="button" className="mode-toggle" aria-pressed={compact.on}
            title={compact.on ? TOGGLE_HELP.toFull : TOGGLE_HELP.toBar} onClick={() => compact.setOn(!compact.on)}>
      {compact.on ? 'Full window' : 'Compact'}
    </button>
  );
}

/** Only while the bar is grown: shrink it back to the bar. The answer stays in the session. */
export function HideAnswer({ compact }: { compact: Compact }) {
  if (!compact.grown) return null;
  return <button type="button" className="hide-answer" onClick={compact.close}>Hide answer</button>;
}
