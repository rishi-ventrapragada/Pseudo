// M39: the conversation column, centred and at most 720 px wide (from the mockup).
// The greeting and suggestions come in M40; until then an empty chat says what Pseudo reads.

import type { RefObject } from 'react';
import type { Turn } from '../state';
import { TurnView } from './TurnView';

type Props = { phase: 'starting' | 'ready' | 'stopped'; turns: Turn[]; session: string; end: RefObject<HTMLDivElement | null> };

function Empty({ title, note }: { title: string; note: string }) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-2.5 pb-6 text-center">
      <h1 className="text-[26px] font-semibold tracking-tight">{title}</h1>
      <p className="text-[15px] text-muted">{note}</p>
    </div>
  );
}

export function Conversation({ phase, turns, session, end }: Props) {
  return (
    <section aria-label="Conversation" className="min-h-0 flex-1 overflow-y-auto px-6">
      <div className="mx-auto flex min-h-full max-w-[720px] flex-col">
        {phase === 'starting' && (
          <Empty title="Starting Pseudo" note="Loading its brain and pseudo_hands takes about ten seconds." />
        )}
        {phase === 'ready' && turns.length === 0 && (
          <Empty title="Ask about the window you were on." note="Go to that window, then switch back here and ask." />
        )}
        {turns.map((turn, index) => <TurnView key={`${session}-${index}`} turn={turn} />)}
        <div ref={end} />
      </div>
    </section>
  );
}
