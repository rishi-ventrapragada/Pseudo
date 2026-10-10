// M39: everything under the conversation in the full window: a notice line and the question box (or Restart,
// when the brain has stopped).
// M40: nothing under the question box (D28; the owner's request, 2026-10-10): the privacy text is in Settings.
// The approval line moved into the conversation (Activity.tsx). The notice line says something only when there is
// something to say: a switch, a refusal, a voice problem, listening, or a side request in progress.

import type { ReactNode } from 'react';
import { Stopped } from './Stopped';

type Props = { notice: string; stopped: boolean; onRestart(): void; composer: ReactNode };

/** Always in the page, so a screen reader hears each new notice once; empty when there is nothing to say. */
export function NoticeLine({ notice }: { notice: string }) {
  return <p aria-live="polite" className="min-h-[18px] truncate text-[12.5px] text-faint" title={notice || undefined}>{notice}</p>;
}

export function BottomArea({ notice, stopped, onRestart, composer }: Props) {
  return (
    <div className="shrink-0 px-6 pb-4">
      <div className="mx-auto flex max-w-[720px] flex-col gap-2">
        <NoticeLine notice={notice} />
        {stopped ? <Stopped onRestart={onRestart} /> : composer}
      </div>
    </div>
  );
}
