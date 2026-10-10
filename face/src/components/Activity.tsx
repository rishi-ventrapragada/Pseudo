// M40: what Pseudo is doing, said in the conversation (from the Phase 10 mockup).
// While it works: a playful word from Pseudo's own list, a timer, and "steps" to see what it has done so far.
// While a tool that can show the approval popup runs (the brain's `asks`): a plain amber line instead, never a
// playful word, because then it is waiting for YOU. Amber is used for nothing else (theme.css).
// Screen readers hear "Pseudo is working" once (a label) and the approval line once (role="status"); never the
// words or the ticking seconds. With "reduce motion" on in Windows the word stays put and nothing pulses.
// M43: BarNote, the compact bar's top-row note (it was BarActivity), and the approval line's note for the bar.

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

/** `note` (M43): the compact bar says why it is no longer on top instead of the full window's line. */
export function ApprovalLine({ open, onToggle, note }: Toggle & { note?: string }) {
  return (
    <div role="status" className="flex max-w-[560px] items-start gap-3 self-start rounded-xl border border-wait/35 bg-wait/[0.07] px-3.5 py-3">
      <ShieldAlert aria-hidden="true" className="mt-px size-[18px] shrink-0 text-wait" />
      <div>
        <p className="text-[15px] font-semibold text-wait">{APPROVAL}</p>
        <p className="mt-[3px] text-[13px] leading-normal text-muted">
          {note ?? 'Pseudo asks before every action. Cancel, or no answer within 20 seconds, means no.'}
        </p>
        <button type="button" onClick={onToggle} aria-expanded={open}
                className="mt-1.5 cursor-pointer text-[12.5px] text-muted underline underline-offset-[3px] hover:text-ink">
          {open ? 'Hide steps' : 'Show steps'}
        </button>
      </div>
    </div>
  );
}

export const BAR_NOTE = { onTop: 'Stays on top', steppedDown: 'Not on top while the popup waits' };
const NOTE_LINE = 'min-w-0 flex-1 truncate text-right text-xs';

/**
 * M43 (was M40's BarActivity): the note in the compact bar's top row, strongest first. Each is true when it shows:
 *   a popup may be waiting  the amber approval line, or (grown, where the amber box is below) why the bar stepped down;
 *   Pseudo is working       the playful word (when grown, the word is in the turn below instead);
 *   otherwise               the notice, or that the bar stays on top (it is, whenever no tool is running).
 */
export function BarNote({ turn, waiting, notice, grown }: { turn: Turn | undefined; waiting: Waiting | null; notice: string; grown: boolean }) {
  const running = Boolean(turn?.running);
  const { word, seconds } = usePlayfulWord(turn?.askedAt);
  if (running && waiting?.asks) {
    return grown ? <p className={cn(NOTE_LINE, 'text-faint')}>{BAR_NOTE.steppedDown}</p>
                 : <p role="status" className={cn(NOTE_LINE, 'font-semibold text-wait')}>{APPROVAL}</p>;
  }
  if (running && !grown) {
    return (
      <p className={cn(NOTE_LINE, 'text-ink-soft')} aria-label="Pseudo is working">
        <span aria-hidden="true">{word}… <span className="font-mono text-faint">{seconds}s</span></span>
      </p>
    );
  }
  return <p aria-live="polite" className={cn(NOTE_LINE, 'text-faint')} title={notice || undefined}>{running ? notice : notice || BAR_NOTE.onTop}</p>;
}
