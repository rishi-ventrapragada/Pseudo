// M38: the compact bar. M39 draws it with the new parts instead of hiding pieces of the full page (compact.css).
// M40: the top row says what the full window's conversation says: the amber approval line while a popup may be
// waiting, the playful word while Pseudo works, or the notice.
// M43: the approved mockup's bar (Compact.dc.html):
//   [Pseudo                       the note][Full window] (Windows' minimize, maximize off, close)   30 px, drags
//   grown, above:  the question · Hide answer, then the working word, the approval box, or the answer and its steps
//   [mic] [Brave] [Ask about this window                                            ] [Ask]
// Grown, the bar is as tall as what it shows: useBarFit measures the three parts and the main process sizes the
// window, growing upward (D11). The floating look is Windows 11's own: rounded corners and a shadow on an ordinary
// window (a see-through one, which the mockup's card would need, is not allowed: C3).

import type { ReactNode } from 'react';
import { CompactToggle } from '../CompactToggle';
import { cn } from '../lib/cn';
import type { Turn, Waiting } from '../state';
import { type Compact, useBarFit } from '../useCompact';
import { BarNote } from './Activity';
import { BarTurn } from './BarTurn';
import { Stopped } from './Stopped';

type Props = {
  compact: Compact;
  notice: string;
  waiting: Waiting | null;
  stopped: boolean;
  latest: Turn | undefined; // the bar shows the latest turn only
  onRestart(): void;
  composer: ReactNode; // the one-row question box: the mic, the look-at chip, the box and Ask
};

export function CompactBar({ compact, notice, waiting, stopped, latest, onRestart, composer }: Props) {
  const fit = useBarFit(compact.grown);
  return (
    <div className="flex h-full flex-col bg-ground text-ink">
      <div ref={fit.top} className="drag flex h-[30px] shrink-0 items-center gap-2 pr-[var(--controls-width)] pl-3">
        <span className="shrink-0 text-xs font-semibold text-muted">Pseudo</span>
        <BarNote turn={latest} waiting={waiting} notice={notice} grown={compact.grown} />
        <CompactToggle compact={compact} />
      </div>
      {compact.grown && (
        <section aria-label="Conversation" className="min-h-0 flex-1 overflow-y-auto">
          <div ref={fit.content} className="flex flex-col gap-2.5 px-3.5 pt-1 pb-2.5">
            {latest && <BarTurn key={latest.question} turn={latest} waiting={waiting} compact={compact} />}
          </div>
        </section>
      )}
      <div ref={fit.bottom} className={cn('flex px-2 pb-2', compact.grown ? 'shrink-0' : 'mt-auto')}>
        {stopped ? <div className="min-w-0 flex-1"><Stopped onRestart={onRestart} /></div> : composer}
      </div>
    </div>
  );
}
