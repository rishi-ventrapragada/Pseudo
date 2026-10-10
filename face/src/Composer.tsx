// M38 (moved out of App.tsx, behaviour unchanged): the question box and the Ask button.
// Display only: App owns the draft and decides what asking means; this only reports the keys and the click.
// M39: one rounded box with the mic inside it and Ask as a round icon button (from the mockup). In the compact
// bar it is one row instead. The keys are unchanged.

import { ArrowUp } from 'lucide-react';
import type { ReactNode, RefObject } from 'react';
import { cn } from './lib/cn';
import { Button } from './components/ui/Button';

type Props = {
  draft: string;
  setDraft(text: string): void;
  canAsk: boolean; // Pseudo is ready and not busy
  onAsk(): void;
  box: RefObject<HTMLTextAreaElement | null>; // App puts the cursor here when a transcript lands (M26)
  mic?: ReactNode; // the mic button (and Stop speaking), drawn inside the box
  chips?: ReactNode; // small lines above the text, e.g. "Listening"
  row?: boolean; // the compact bar: everything on one line
};

/** Enter asks; Shift+Enter is a new line. (M37) Not with Ctrl or Alt: Ctrl+Alt+Enter is the global
 *  show-or-hide shortcut, and if another program holds it, pressing it here must not send a draft. */
export function asksOnKey(event: { key: string; shiftKey: boolean; ctrlKey: boolean; altKey: boolean }): boolean {
  return event.key === 'Enter' && !event.shiftKey && !event.ctrlKey && !event.altKey;
}

export function Composer({ draft, setDraft, canAsk, onAsk, box, mic, chips, row = false }: Props) {
  const text = (
    <textarea
      ref={box}
      aria-label="Your question"
      rows={row ? 1 : 2}
      autoFocus
      value={draft}
      placeholder="Ask about the window you were on"
      onChange={(event) => setDraft(event.target.value)}
      onKeyDown={(event) => {
        if (asksOnKey(event)) {
          event.preventDefault();
          onAsk();
        }
      }}
      className={cn('block w-full resize-none bg-transparent text-ink outline-none placeholder:text-faint',
                    row ? 'h-9 min-w-0 flex-1 px-1 py-[7px] text-sm' : 'px-0.5 pt-2 pb-1 text-[15px] leading-normal')}
    />
  );
  const ask = (
    <Button type="submit" variant="primary" size="round" aria-label="Ask" disabled={!canAsk || !draft.trim()}>
      <ArrowUp aria-hidden="true" className="size-[17px]" strokeWidth={2} />
    </Button>
  );
  return (
    <form
      onSubmit={(event) => { event.preventDefault(); onAsk(); }}
      className={cn('border border-edge-strong bg-composer focus-within:border-muted',
                    row ? 'flex min-w-0 flex-1 items-center gap-1.5 rounded-2xl px-1.5 py-1' : 'rounded-[20px] px-3 pt-2.5 pb-2')}
    >
      {row ? <>{mic}{text}{ask}</> : (
        <>
          {chips && <div className="flex flex-wrap items-center gap-2">{chips}</div>}
          {text}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1">{mic}</div>
            {ask}
          </div>
        </>
      )}
    </form>
  );
}
