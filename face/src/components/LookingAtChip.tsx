// M42: the chip in the question box (from the mockup): which app a question would read now, by its own name.
// A blocked app is "a private app": Pseudo won't read it, and doesn't name it either. Nothing to show: no chip.
// Display only (D11): the brain picks the window exactly as read_active_window does (pseudo_hands' looking_at.py).

import { Eye } from 'lucide-react';
import type { LookingAt } from '../sees';

export function LookingAtChip({ looking }: { looking: LookingAt | null }) {
  if (!looking) return null;
  return (
    <span title="The window Pseudo will read when you ask"
          className="inline-flex h-6 max-w-full items-center gap-1.5 rounded-full bg-bubble pr-2.5 pl-2 text-xs text-muted">
      <Eye aria-hidden="true" className="size-3.5 shrink-0" />
      <span className="truncate">
        Looking at <span className="font-medium text-ink">{looking.private ? 'a private app' : looking.app}</span>
      </span>
    </span>
  );
}
