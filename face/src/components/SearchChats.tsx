// M41: "Search chats" (from the mockup). Only the box: the brain does the searching, in the titles and your
// messages, never the answers (session_files.py). The browser's own search box clears itself on Esc.

import { Search } from 'lucide-react';

export const SEARCH_CHARS = 200; // the brain reads at most this much (session_files.py)

export function SearchChats({ text, onChange }: { text: string; onChange(text: string): void }) {
  return (
    <label className="mt-2 flex h-[34px] items-center gap-2 rounded-[10px] border border-edge bg-field px-2.5
                      focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-ink-soft">
      <Search aria-hidden="true" className="size-4 shrink-0 text-faint" />
      <input type="search" aria-label="Search chats" placeholder="Search chats" value={text} maxLength={SEARCH_CHARS}
             onChange={(event) => onChange(event.target.value)}
             className="min-w-0 flex-1 bg-transparent text-[13.5px] text-ink outline-none placeholder:text-faint" />
    </label>
  );
}
