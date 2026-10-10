// M39: the conversation column, centred and at most 720 px wide (from the mockup).
// M40: an empty chat greets you and offers the brain's suggestions; a click asks one at once, like pressing Enter.

import { BookOpen, Eye, FileText, LayoutGrid, type LucideIcon } from 'lucide-react';
import type { RefObject } from 'react';
import type { Turn, Waiting } from '../state';
import { TurnView } from './TurnView';

type Props = {
  phase: 'starting' | 'ready' | 'stopped';
  turns: Turn[];
  session: string;
  end: RefObject<HTMLDivElement | null>;
  waiting: Waiting | null;
  suggestions: string[];
  canAsk: boolean; // Pseudo is ready and not busy
  onAsk(text: string): void;
};

const ICONS: LucideIcon[] = [Eye, FileText, LayoutGrid, BookOpen]; // decoration only, one per suggestion

function Greeting({ suggestions, canAsk, onAsk }: Pick<Props, 'suggestions' | 'canAsk' | 'onAsk'>) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-[26px] pb-6">
      <div className="text-center">
        <h1 className="text-[30px] font-semibold tracking-tight">What can I help with?</h1>
        <p className="mt-2.5 text-[15px] text-muted">I read the window you were on before this one.</p>
      </div>
      {suggestions.length > 0 && (
        <div className="grid w-full max-w-[600px] grid-cols-2 gap-2.5">
          {suggestions.map((text, index) => {
            const Icon = ICONS[index % ICONS.length];
            return (
              <button key={text} type="button" disabled={!canAsk} onClick={() => onAsk(text)}
                      className="flex min-h-[52px] cursor-pointer items-center gap-2.5 rounded-[14px] border border-edge px-3.5 py-2.5
                                 text-left text-sm leading-snug hover:bg-raised disabled:cursor-default disabled:opacity-50">
                <Icon aria-hidden="true" className="size-[17px] shrink-0 text-muted" />
                {text}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

export function Conversation({ phase, turns, session, end, waiting, suggestions, canAsk, onAsk }: Props) {
  return (
    <section aria-label="Conversation" className="min-h-0 flex-1 overflow-y-auto px-6">
      <div className="mx-auto flex min-h-full max-w-[720px] flex-col">
        {phase === 'starting' && (
          <div className="flex flex-1 flex-col items-center justify-center gap-2.5 pb-6 text-center">
            <h1 className="text-[26px] font-semibold tracking-tight">Starting Pseudo</h1>
            <p className="text-[15px] text-muted">Loading its brain and pseudo_hands takes about ten seconds.</p>
          </div>
        )}
        {phase === 'ready' && turns.length === 0 && <Greeting suggestions={suggestions} canAsk={canAsk} onAsk={onAsk} />}
        {turns.map((turn, index) => (
          <TurnView key={`${session}-${index}`} turn={turn} waiting={index === turns.length - 1 ? waiting : null} />
        ))}
        <div ref={end} />
      </div>
    </section>
  );
}
