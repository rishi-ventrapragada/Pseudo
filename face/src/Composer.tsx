// M38 (moved out of App.tsx, behaviour unchanged): the question box and the Ask button.
// Display only: App owns the draft and decides what asking means; this only reports the keys and the click.

import type { RefObject } from 'react';

type Props = {
  draft: string;
  setDraft(text: string): void;
  canAsk: boolean; // Pseudo is ready and not busy
  onAsk(): void;
  box: RefObject<HTMLTextAreaElement | null>; // App puts the cursor here when a transcript lands (M26)
};

/** Enter asks; Shift+Enter is a new line. (M37) Not with Ctrl or Alt: Ctrl+Alt+Enter is the global
 *  show-or-hide shortcut, and if another program holds it, pressing it here must not send a draft. */
export function asksOnKey(event: { key: string; shiftKey: boolean; ctrlKey: boolean; altKey: boolean }): boolean {
  return event.key === 'Enter' && !event.shiftKey && !event.ctrlKey && !event.altKey;
}

export function Composer({ draft, setDraft, canAsk, onAsk, box }: Props) {
  return (
    <form onSubmit={(event) => { event.preventDefault(); onAsk(); }}>
      <textarea
        ref={box}
        aria-label="Your question"
        rows={2}
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
      />
      <button type="submit" disabled={!canAsk || !draft.trim()}>Ask</button>
    </form>
  );
}
