// M18 (from Sessions.tsx; M39 moved it into the sidebar): the saved sessions (%LOCALAPPDATA%\Pseudo\sessions).
// Opening one continues it on its OWN provider (M16): the brain reconnects if that's another provider, never
// moves the history. Grouping by date, search, rename and delete come in M41.

import type { SessionItem } from '../protocol';
import { cn } from '../lib/cn';

type Props = { items: SessionItem[] | null; current: string; disabled: boolean; onOpen: (name: string) => void };

/** "20260930-231500-123" -> "2026-09-30 23:15" */
export function when(name: string): string {
  const m = name.match(/^(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})/);
  return m ? `${m[1]}-${m[2]}-${m[3]} ${m[4]}:${m[5]}` : name;
}

/** The details a chat's line has no room for, shown when the mouse rests on it. */
export function details(item: SessionItem): string {
  return `${when(item.name)} · ${item.provider} · ${item.questions} question${item.questions === 1 ? '' : 's'}`;
}

export function SessionList({ items, current, disabled, onOpen }: Props) {
  if (items === null) return <div className="flex-1" />; // asked for when Pseudo is free (App)
  return (
    <div className="min-h-0 flex-1 overflow-y-auto px-2.5 pb-2">
      {items.length === 0 && (
        <p className="px-2.5 py-2 text-[13px] text-faint">No saved chats yet. Every question you ask is saved here.</p>
      )}
      <ul aria-label="Saved chats" className="flex flex-col gap-px">
        {items.map((item) => {
          const open = item.name === current;
          return (
            <li key={item.name}>
              <button type="button" disabled={disabled || open} aria-current={open} title={details(item)}
                      onClick={() => onOpen(item.name)}
                      className={cn('w-full cursor-pointer truncate rounded-lg px-2.5 py-[7px] text-left text-[13.5px]',
                                    open ? 'cursor-default bg-popover text-ink'
                                         : 'text-ink-soft hover:bg-raised hover:text-ink disabled:cursor-default disabled:opacity-50')}>
                {item.title || '(no questions)'}
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
