// M42: the chip in the question box (from the mockup): which app a question would read now, by its own name.
// A blocked app is "a private app": Pseudo won't read it, and doesn't name it either. Nothing to show: no chip.
// Display only (D11): the brain picks the window exactly as read_active_window does (pseudo_hands' looking_at.py).
// M43: a short form for the compact bar's one row (the mockup's): the eye and the name only. "Looking at" is still
// there for screen readers (sr-only), so they hear the same words as in the full window.

import { Eye } from 'lucide-react';
import { cn } from '../lib/cn';
import type { LookingAt } from '../sees';

export const CHIP_HELP = 'The window Pseudo will read when you ask';

export function LookingAtChip({ looking, short = false }: { looking: LookingAt | null; short?: boolean }) {
  if (!looking) return null;
  const name = looking.private ? 'a private app' : looking.app;
  const help = short ? `Looking at ${name}: the window Pseudo will read when you ask` : CHIP_HELP; // a long name is cut short
  return (
    <span title={help}
          className={cn('inline-flex items-center rounded-full bg-bubble text-muted',
                        short ? 'h-[22px] max-w-[132px] shrink-0 gap-1 pr-2 pl-1.5 text-[11.5px]' : 'h-6 max-w-full gap-1.5 pr-2.5 pl-2 text-xs')}>
      <Eye aria-hidden="true" className={cn('shrink-0', short ? 'size-3' : 'size-3.5')} />
      {short ? (
        <span className="truncate"><span className="sr-only">Looking at </span><span className="text-ink">{name}</span></span>
      ) : (
        <span className="truncate">Looking at <span className="font-medium text-ink">{name}</span></span>
      )}
    </span>
  );
}
