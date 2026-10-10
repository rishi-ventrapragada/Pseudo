// M18 (moved out of App.tsx in M39 and restyled): one question and what came of it.
// Your question sits in a bubble on the right; Pseudo's answer is plain text under it, with its steps one click away.
// M30: an answer still says which brain gave it; M40 moves that into the steps (D28).

import { brainOf } from '../events';
import { Markdown } from '../Markdown';
import type { Turn } from '../state';
import { Disclosure } from './ui/Disclosure';

function Steps({ steps }: { steps: string[] }) {
  return (
    <Disclosure summary={`${steps.length} step${steps.length === 1 ? '' : 's'}: what Pseudo did`}
                triggerClassName="h-[30px] px-2 -ml-2">
      <ol aria-label="What Pseudo did"
          className="mt-1 flex flex-col gap-2 rounded-xl border border-edge bg-field px-3.5 py-3 text-[13px] leading-normal">
        {steps.map((step, index) => (
          <li key={index} className="flex items-baseline gap-3">
            <span className="min-w-3.5 font-mono text-xs text-faint">{index + 1}</span>
            <span>{step}</span>
          </li>
        ))}
      </ol>
    </Disclosure>
  );
}

function Who({ label }: { label: string }) {
  const brain = brainOf(label);
  return (
    <p className="mb-2 flex flex-wrap items-center gap-2 text-xs text-faint">
      <span>{label}</span>
      <span data-brain={brain} className="rounded-full border border-edge px-2 py-px">
        {brain === 'action' ? 'Claude Code · your subscription' : 'Chat provider'}
      </span>
    </p>
  );
}

export function TurnView({ turn }: { turn: Turn }) {
  return (
    <section className="flex flex-col gap-3 py-4">
      <div className="flex justify-end">
        <p className="max-w-[560px] rounded-[18px] bg-bubble px-4 py-2.5 text-[15px] leading-[1.55] whitespace-pre-wrap">
          {turn.question}
        </p>
      </div>
      {turn.answer !== undefined && (
        <article className="answer text-[15px] leading-[1.68]" aria-label={`Answer from ${turn.label || 'Pseudo'}`}>
          {turn.label && <Who label={turn.label} />}
          <Markdown text={turn.answer} />
        </article>
      )}
      {turn.failed && <p className="text-sm text-ink-soft" role="alert">No answer: {turn.failed}</p>}
      {turn.steps.length > 0 && <Steps steps={turn.steps} />}
    </section>
  );
}
