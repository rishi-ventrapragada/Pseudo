// M38: the compact bar. M39 draws it with the new parts instead of hiding pieces of the full page (compact.css).
// The bar:          [status line                                ]  (Windows' buttons, top right)
//                   [mic] [question box                   ] [Ask] [Full window]
// Grown, above it:  Hide answer, then the latest turn (question, answer, steps); the approval banner stays
// visible whenever a tool waits. The main process sizes the window and decides when it may be on top (D11).

import type { ReactNode } from 'react';
import { ApprovalBanner } from '../ApprovalBanner';
import { CompactToggle, HideAnswer } from '../CompactToggle';
import { cn } from '../lib/cn';
import type { Turn } from '../state';
import type { Compact } from '../useCompact';
import { StatusLine } from './BottomArea';
import { Stopped } from './Stopped';
import { TurnView } from './TurnView';

type Props = {
  compact: Compact;
  status: string;
  working: boolean;
  waiting: string | null;
  stopped: boolean;
  latest: Turn | undefined; // the bar shows the latest turn only
  onRestart(): void;
  composer: ReactNode; // the one-line question box, with the mic in it
};

export function CompactBar({ compact, status, working, waiting, stopped, latest, onRestart, composer }: Props) {
  return (
    <div className="flex h-full flex-col bg-ground text-ink">
      <div className="drag flex h-11 shrink-0 items-center pr-[var(--controls-width)] pl-3">
        <StatusLine status={status} working={working} />
      </div>
      {compact.grown && (
        <section aria-label="Conversation" className="min-h-0 flex-1 overflow-y-auto px-3">
          <div className="flex pt-1"><HideAnswer compact={compact} /></div>
          {latest && <TurnView turn={latest} />}
        </section>
      )}
      <div className={cn('flex flex-col gap-2 px-2.5 pb-2', compact.grown ? 'shrink-0' : 'flex-1 justify-center')}>
        <ApprovalBanner waiting={waiting} />
        <div className="flex items-center gap-1.5">
          {stopped ? <div className="min-w-0 flex-1"><Stopped onRestart={onRestart} /></div> : composer}
          <CompactToggle compact={compact} />
        </div>
      </div>
    </div>
  );
}
