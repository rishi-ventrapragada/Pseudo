// M42: the Status panel at the bottom of the sidebar (from the mockup), open by default. Numbers only, for the open
// chat since it was opened here: tokens sent and received, Groq's budget this minute, the warm Claude Code session's
// memory, and how many items were masked before anything left the laptop (the brain counts the redactor's labels).

import { Activity } from 'lucide-react';
import { useEffect, useState } from 'react';
import type { Warm } from '../protocol';
import { budgetNow, type Totals } from '../sees';
import { Disclosure } from './ui/Disclosure';

const TICK_MS = 5000; // redraw now and then, so the budget turns full again a minute after the last answer

/** 6200 -> "6.2K", 8000 -> "8K", 950 -> "950". */
export function short(value: number): string {
  return value >= 1000 ? `${(value / 1000).toFixed(1).replace(/\.0$/, '')}K` : String(value);
}

export function warmText(warm: Warm | null): string {
  if (!warm?.on) return 'off';
  return warm.open ? `${warm.ram_mb ?? '?'} MB, open` : 'on, none open';
}

/** The time now, redrawn every few seconds; a test passes a fixed `now` instead. */
function useNow(fixed?: number): number {
  const [now, setNow] = useState(() => fixed ?? Date.now());
  useEffect(() => {
    if (fixed !== undefined) return;
    const timer = setInterval(() => setNow(Date.now()), TICK_MS);
    return () => clearInterval(timer);
  }, [fixed]);
  return fixed ?? now;
}

type Props = { totals: Totals; warm: Warm | null; now?: number };

export function StatusPanel({ totals, warm, now }: Props) {
  const budget = budgetNow(totals.budget, useNow(now));
  const row = 'grid grid-cols-[1fr_auto] items-center gap-x-3 gap-y-1.5';
  return (
    <Disclosure defaultOpen className="px-2.5 pt-2" triggerClassName="h-7 gap-1.5 px-1 text-xs font-medium text-muted"
                summary={<><Activity aria-hidden="true" className="size-3.5" />Status</>}>
      <dl className="mt-1 flex flex-col gap-1.5 rounded-[10px] bg-field p-3 text-[12.5px]">
        <div className={row}><dt className="text-muted">Tokens this chat</dt>
          <dd className="font-mono text-ink">{totals.tokens.toLocaleString('en-US')}</dd></div>
        <div className={row}><dt className="text-muted">Groq budget this minute</dt>
          <dd className="font-mono text-ink">{budget ? `${short(budget.left)} / ${short(budget.limit)}` : '–'}</dd>
          {budget && ( // the bar repeats the numbers, so screen readers skip it
            <dd className="col-span-2">
              <progress aria-hidden="true" value={budget.left} max={budget.limit}
                        className="block h-1 w-full appearance-none overflow-hidden rounded-full [&::-webkit-progress-bar]:bg-edge
                                   [&::-webkit-progress-value]:rounded-full [&::-webkit-progress-value]:bg-muted" />
            </dd>
          )}
        </div>
        <div className={row}><dt className="text-muted">Warm Claude Code</dt>
          <dd className="font-mono text-ink">{warmText(warm)}</dd></div>
        <div className={row}><dt className="text-muted">Masked before sending</dt>
          <dd className="font-mono text-ink">{totals.masked} {totals.masked === 1 ? 'item' : 'items'}</dd></div>
      </dl>
    </Disclosure>
  );
}
