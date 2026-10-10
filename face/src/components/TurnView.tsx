// M18 (moved out of App.tsx in M39): one question and what came of it.
// Your question sits in a bubble on the right; Pseudo's answer is plain text under it.
// M40: no "who answered" label on the answer (D28): that is in the steps, one click away. While the question runs,
// the working line (a playful word) or, while a popup may be waiting, the plain approval line (Activity.tsx).

import { ChevronDown } from 'lucide-react';
import { useState } from 'react';
import { Markdown } from '../Markdown';
import type { Turn, Waiting } from '../state';
import type { Step } from '../steps';
import { cn } from '../lib/cn';
import { ApprovalLine, WorkingLine } from './Activity';

export function StepsList({ steps }: { steps: Step[] }) {
  return (
    <ol aria-label="What Pseudo did" className="flex flex-col gap-2 rounded-xl border border-edge bg-field px-3.5 py-3 text-[13px] leading-normal">
      {steps.map((step, index) => (
        <li key={index} className="flex items-baseline gap-3">
          <span className="min-w-3.5 font-mono text-xs text-faint">{index + 1}</span>
          <span>{step.label}{step.detail && <span className="text-faint"> · {step.detail}</span>}</span>
        </li>
      ))}
    </ol>
  );
}

export function StepsToggle({ count, open, onToggle }: { count: number; open: boolean; onToggle(): void }) { // M43: the bar's too
  return (
    <button type="button" onClick={onToggle} aria-expanded={open}
            className="-ml-2 inline-flex h-[30px] cursor-pointer items-center gap-1 self-start rounded-lg px-2 text-[12.5px] text-faint hover:text-ink">
      {count} step{count === 1 ? '' : 's'}: what Pseudo did
      <ChevronDown aria-hidden="true" className={cn('size-3.5 transition-transform', open && 'rotate-180')} />
    </button>
  );
}

export function TurnView({ turn, waiting = null }: { turn: Turn; waiting?: Waiting | null }) {
  const [open, setOpen] = useState(false);
  const toggle = () => setOpen(!open);
  const approval = turn.running && Boolean(waiting?.asks); // only the running turn can be waiting for you
  const working = turn.running && !approval && turn.answer === undefined && !turn.failed;
  return (
    <section className="flex flex-col gap-3 py-4">
      <div className="flex justify-end">
        <p className="max-w-[560px] rounded-[18px] bg-bubble px-4 py-2.5 text-[15px] leading-[1.55] whitespace-pre-wrap">
          {turn.question}
        </p>
      </div>
      {working && <WorkingLine askedAt={turn.askedAt} open={open} onToggle={toggle} />}
      {turn.answer !== undefined && (
        <article className="answer text-[15px] leading-[1.68]" aria-label="Pseudo's answer">
          <Markdown text={turn.answer} />
        </article>
      )}
      {turn.failed && <p className="text-sm text-ink-soft" role="alert">No answer: {turn.failed}</p>}
      {approval && <ApprovalLine open={open} onToggle={toggle} />}
      {!working && !approval && turn.steps.length > 0 && <StepsToggle count={turn.steps.length} open={open} onToggle={toggle} />}
      {open && turn.steps.length > 0 && <StepsList steps={turn.steps} />}
    </section>
  );
}
