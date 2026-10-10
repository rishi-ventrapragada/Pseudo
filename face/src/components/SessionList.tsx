// M18 (from Sessions.tsx; M39 moved it into the sidebar): the saved chats (%LOCALAPPDATA%\Pseudo\sessions).
// Opening one continues it on its OWN provider (M16): the brain reconnects if that's another provider, never
// moves the history. M41: grouped under Today, Yesterday, Previous 7 days and Older (groups.ts); this list
// says which one row is renaming and which one menu is open, so there's never more than one of each.

import { useState } from 'react';
import { grouped } from '../groups';
import type { SessionItem } from '../protocol';
import { ChatRow } from './ChatRow';

type Props = {
  items: SessionItem[] | null; // null: not listed yet (asked for when Pseudo is free, App)
  current: string;
  disabled: boolean;
  noMatch: boolean; // a search found nothing
  onOpen(name: string): void;
  onRename(name: string, title: string): void;
  onAskDelete(item: SessionItem): void;
  now?: Date; // what "Today" means; the tests fix it
};

export function SessionList({ items, current, disabled, noMatch, onOpen, onRename, onAskDelete, now = new Date() }: Props) {
  const [menuFor, setMenuFor] = useState<string | null>(null);
  const [renaming, setRenaming] = useState<string | null>(null);
  if (items === null) return <div className="flex-1" />;
  return (
    <div role="group" aria-label="Saved chats" className="min-h-0 flex-1 overflow-y-auto px-2.5 pb-2">
      {noMatch && <p className="px-2.5 py-2 text-[13px] text-faint">No chats match your search.</p>}
      {items.length === 0 && !noMatch && (
        <p className="px-2.5 py-2 text-[13px] text-faint">No saved chats yet. Every question you ask is saved here.</p>
      )}
      {grouped(items, now).map((group) => (
        <section key={group.label} aria-label={group.label}>
          <h3 className="px-2.5 pt-3 pb-1 text-xs font-medium text-faint">{group.label}</h3>
          <ul className="flex flex-col gap-px">
            {group.items.map((item) => (
              <li key={item.name}>
                <ChatRow item={item} open={item.name === current} disabled={disabled}
                         menuOpen={menuFor === item.name} renaming={renaming === item.name}
                         onOpen={() => onOpen(item.name)}
                         onMenu={(open) => setMenuFor(open ? item.name : null)}
                         onStartRename={() => { setMenuFor(null); setRenaming(item.name); }}
                         onRename={(title) => { setRenaming(null); if (title) onRename(item.name, title); }}
                         onAskDelete={() => { setMenuFor(null); onAskDelete(item); }} />
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
