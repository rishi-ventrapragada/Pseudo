// M38: the button that switches between the full window and the compact bar, and the bar's Hide answer button.
// Display only: useCompact.ts sends the request, and face/window-mode.js (the main process) resizes the window.
// M39: an icon button with a tooltip, from the mockup; its name says what it does.
// M43: in the bar it sits in the 30 px top row, so it is smaller there (the mockup's 30 x 26), as is Hide answer.
import { Maximize2, PictureInPicture2 } from 'lucide-react';
import { Button } from './components/ui/Button';
import { Tip } from './components/ui/Tip';
import type { Compact } from './useCompact';

export const TOGGLE_HELP = {
  toBar: 'A small bar that stays on top of your other windows',
  toFull: 'Back to the full window: sessions, providers and settings',
};

export function CompactToggle({ compact }: { compact: Compact }) {
  const Icon = compact.on ? Maximize2 : PictureInPicture2;
  return (
    <Tip label={compact.on ? TOGGLE_HELP.toFull : TOGGLE_HELP.toBar} side="bottom">
      <Button size={compact.on ? 'bar' : 'icon'} aria-pressed={compact.on} aria-label={compact.on ? 'Full window' : 'Compact bar'}
              onClick={() => compact.setOn(!compact.on)}>
        <Icon aria-hidden="true" className={compact.on ? 'size-3.5' : 'size-[17px]'} />
      </Button>
    </Tip>
  );
}

/** Only while the bar is grown: shrink it back to the bar. The answer stays in the session. */
export function HideAnswer({ compact }: { compact: Compact }) {
  if (!compact.grown) return null;
  return (
    <Button size="xs" variant="outline" onClick={compact.close}>
      Hide answer
    </Button>
  );
}
