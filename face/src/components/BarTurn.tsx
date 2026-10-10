// M43: the latest turn as the grown compact bar shows it (the mockup's): your question on one line with Hide answer
// beside it, then what Pseudo is doing (the playful word, or the amber approval box), or the answer with its steps.
// The full window's turn is TurnView.tsx; this one reuses its parts, so both say exactly the same things.
// Display only: the bar's height follows what this draws (useBarFit in useCompact.ts measures it).

import { useState } from 'react';
import { HideAnswer } from '../CompactToggle';
import { Markdown } from '../Markdown';
import type { Turn, Waiting } from '../state';
import type { Compact } from '../useCompact';
import { ApprovalLine, WorkingLine } from './Activity';
import { StepsList, StepsToggle } from './TurnView';

// While a popup waits, the bar is not always on top (window-top.js): the mockup's words for why.
export const BAR_APPROVAL_NOTE = 'The bar stepped down so the popup stays on top.';

export function BarTurn({ turn, waiting, compact }: { turn: Turn; waiting: Waiting | null; compact: Compact }) {
  const [open, setOpen] = useState(false); // the steps list
  const toggle = () => setOpen(!open);
  const approval = turn.running && Boolean(waiting?.asks); // only the running turn can be waiting for you
  const working = turn.running && !approval && turn.answer === undefined && !turn.failed;
  return (
    <>
      <div className="flex items-center gap-2">
        <p className="min-w-0 flex-1 truncate text-[13px] text-muted" title={turn.question}>{turn.question}</p>
        <HideAnswer compact={compact} />
      </div>
      {working && <WorkingLine askedAt={turn.askedAt} open={open} onToggle={toggle} />}
      {turn.answer !== undefined && (
        <article className="answer text-[14.5px] leading-[1.62]" aria-label="Pseudo's answer">
          <Markdown text={turn.answer} />
        </article>
      )}
      {turn.failed && <p className="text-sm text-ink-soft" role="alert">No answer: {turn.failed}</p>}
      {approval && <ApprovalLine open={open} onToggle={toggle} note={BAR_APPROVAL_NOTE} />}
      {!working && !approval && turn.steps.length > 0 && <StepsToggle count={turn.steps.length} open={open} onToggle={toggle} />}
      {open && turn.steps.length > 0 && <StepsList steps={turn.steps} />}
    </>
  );
}
