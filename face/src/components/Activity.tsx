// M40: what Pseudo is doing, said in the conversation (from the Phase 10 mockup).
// While it works: a playful word from Pseudo's own list, a timer, and "steps" to see what it has done so far.
// While a tool that can show the approval popup runs (the brain's `asks`): a plain amber line instead, never a
// playful word, because then it is waiting for YOU. Amber is used for nothing else (theme.css).
// Screen readers hear "Pseudo is working" once (a label) and the approval line once (role="status"); never the
// words or the ticking seconds. With "reduce motion" on in Windows the word stays put and nothing pulses.

import { ChevronDown, ShieldAlert } from 'lucide-react';
import { useEffect, useState } from 'react';
import { cn } from '../lib/cn';
import type { Turn, Waiting } from '../state';

export const WORDS = ['Squinting at your window', 'Redacting the names', 'Reading between the controls', 'Pondering',
                      'Tidying the outline', 'Checking twice', 'Mulling it over', 'Connecting the dots', 'Masking the numbers',
                      'Thinking quietly'];
export const APPROVAL = 'Waiting for your approval in the popup';
const WORD_SECONDS = 3;

function reducedMotion(): boolean {
  return typeof window !== 'undefined' && Boolean(window.matchMedia?.('(prefers-reduced-motion: reduce)').matches);
}

/** The word to show and the seconds so far; it re-renders once a second while the question runs. */
export function usePlayfulWord(askedAt: number | undefined): { word: string; seconds: number } {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  const seconds = Math.max(0, Math.floor((now - (askedAt ?? now)) / 1000));
  const word = reducedMotion() ? WORDS[0] : WORDS[Math.floor(seconds / WORD_SECONDS) % WORDS.length];
  return { word, seconds };
}

type Toggle = { open: boolean; onToggle(): void };

function Chevron({ open }: { open: boolean }) {
  return <ChevronDown aria-hidden="true" className={cn('size-3.5 transition-transform', open && 'rotate-180')} />;
}

export function WorkingLine({ askedAt, open, onToggle }: Toggle & { askedAt?: number }) {
  const { word, seconds } = usePlayfulWord(askedAt);
  return (
    <button type="button" onClick={onToggle} aria-expanded={open} aria-label="Pseudo is working. Show what it has done so far."
            className="inline-flex cursor-pointer items-center gap-2.5 self-start rounded-lg py-1.5 pr-1.5 text-ink">
      <span aria-hidden="true" className="size-[9px] rotate-45 rounded-[2px] bg-ink motion-safe:animate-pulse" />
      <span aria-hidden="true" className="text-[15px]">{word}…</span>
      <span aria-hidden="true" className="font-mono text-[12.5px] text-faint">{seconds}s</span>
      <span aria-hidden="true" className="inline-flex items-center gap-0.5 text-[12.5px] text-faint">steps <Chevron open={open} /></span>
    </button>
  );
}

export function ApprovalLine({ open, onToggle }: Toggle) {
  return (
    <div role="status" className="flex max-w-[560px] items-start gap-3 self-start rounded-xl border border-wait/35 bg-wait/[0.07] px-3.5 py-3">
      <ShieldAlert aria-hidden="true" className="mt-px size-[18px] shrink-0 text-wait" />
      <div>
        <p className="text-[15px] font-semibold text-wait">{APPROVAL}</p>
        <p className="mt-[3px] text-[13px] leading-normal text-muted">
          Pseudo asks before every action. Cancel, or no answer within 20 seconds, means no.
        </p>
        <button type="button" onClick={onToggle} aria-expanded={open}
                className="mt-1.5 cursor-pointer text-[12.5px] text-muted underline underline-offset-[3px] hover:text-ink">
          {open ? 'Hide steps' : 'Show steps'}
        </button>
      </div>
    </div>
  );
}

/** The compact bar's top row: the same three states in one line. */
export function BarActivity({ turn, waiting, notice }: { turn: Turn | undefined; waiting: Waiting | null; notice: string }) {
  const running = Boolean(turn?.running);
  const { word, seconds } = usePlayfulWord(turn?.askedAt);
  if (running && waiting?.asks) {
    return <p role="status" className="min-w-0 flex-auto truncate text-[12.5px] font-semibold text-wait">{APPROVAL}</p>;
  }
  if (running) {
    return (
      <p className="min-w-0 flex-auto truncate text-[12.5px] text-ink-soft" aria-label="Pseudo is working">
        <span aria-hidden="true">{word}… <span className="font-mono text-faint">{seconds}s</span></span>
      </p>
    );
  }
  return <p aria-live="polite" className="min-w-0 flex-auto truncate text-[12.5px] text-faint">{notice || 'Ready'}</p>;
}
