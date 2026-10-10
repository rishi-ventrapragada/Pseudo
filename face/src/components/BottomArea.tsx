// M39: everything under the conversation in the full window: the approval banner, the status line, the
// question box (or Restart, when the brain has stopped), and the privacy line under it (until M40, D28).

import type { ReactNode } from 'react';
import { ApprovalBanner } from '../ApprovalBanner';
import { cn } from '../lib/cn';
import { Stopped } from './Stopped';

type Props = {
  waiting: string | null; // a tool that is running (its approval popup may be open)
  status: string;
  working: boolean;
  stopped: boolean;
  onRestart(): void;
  composer: ReactNode;
  privacy: ReactNode;
};

/** The status line changes only when Pseudo's state does, so screen readers hear each change once. */
export function StatusLine({ status, working }: { status: string; working: boolean }) {
  return (
    <p aria-live="polite" title={status}
       className={cn('min-w-0 flex-auto truncate text-[12.5px]', working ? 'text-ink-soft' : 'text-faint')}>
      {status}
    </p>
  );
}

export function BottomArea({ waiting, status, working, stopped, onRestart, composer, privacy }: Props) {
  return (
    <div className="shrink-0 px-6 pb-3.5">
      <div className="mx-auto flex max-w-[720px] flex-col gap-2">
        <ApprovalBanner waiting={waiting} />
        <StatusLine status={status} working={working} />
        {stopped ? <Stopped onRestart={onRestart} /> : composer}
        {privacy}
      </div>
    </div>
  );
}
