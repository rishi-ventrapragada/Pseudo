// M41: one saved chat in the sidebar (from the mockup): its title opens it, and "…" opens Rename and Delete.
// Renaming swaps the title for a box: Enter or ✓ saves, Esc or clicking away keeps the old name. Display only
// (D11): the brain checks the new name and refuses a bad one. Which row is renaming, and which menu is open,
// is the list's to say (SessionList.tsx), so one menu is open at a time and a test can draw each state.

import { Check, Ellipsis, Pencil, Trash2 } from 'lucide-react';
import { useEffect, useRef } from 'react';
import { cn } from '../lib/cn';
import type { SessionItem } from '../protocol';
import { Button } from './ui/Button';
import { Menu } from './ui/Menu';

/** "20260930-231500-123" -> "2026-09-30 23:15" */
export function when(name: string): string {
  const m = name.match(/^(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})/);
  return m ? `${m[1]}-${m[2]}-${m[3]} ${m[4]}:${m[5]}` : name;
}

/** The details a chat's line has no room for, shown when the mouse rests on it. */
export function details(item: SessionItem): string {
  return `${when(item.name)} · ${item.provider} · ${item.questions} question${item.questions === 1 ? '' : 's'}`;
}

type Props = {
  item: SessionItem;
  open: boolean; // this is the chat on screen
  disabled: boolean; // Pseudo is busy: nothing can be opened, renamed or deleted
  menuOpen: boolean;
  renaming: boolean;
  onOpen(): void;
  onMenu(open: boolean): void;
  onStartRename(): void;
  onRename(title: string | null): void; // null = keep the old name
  onAskDelete(): void;
};

const TITLE_CHARS = 60; // the brain's limit too (session.py)

function RenameBox({ title, onDone }: { title: string; onDone(title: string | null): void }) {
  const box = useRef<HTMLInputElement>(null);
  useEffect(() => { box.current?.focus(); box.current?.select(); }, []);
  const save = () => {
    const typed = box.current?.value.trim() ?? '';
    onDone(typed && typed !== title ? typed : null); // empty or unchanged: nothing to send
  };
  return (
    <div className="flex items-center gap-1 px-1 py-0.5">
      <input ref={box} aria-label="New name for this chat" defaultValue={title} maxLength={TITLE_CHARS}
             onKeyDown={(event) => {
               if (event.key === 'Enter') save();
               if (event.key === 'Escape') onDone(null);
             }}
             onBlur={() => onDone(null)}
             className="h-[30px] min-w-0 flex-1 rounded-lg border border-edge-strong bg-field px-2 text-[13.5px] text-ink" />
      <Button size="icon" aria-label="Save the new name" onMouseDown={(event) => event.preventDefault()} onClick={save}>
        <Check aria-hidden="true" className="size-4" />
      </Button>
    </div>
  );
}

export function ChatRow({ item, open, disabled, menuOpen, renaming, onOpen, onMenu, onStartRename, onRename, onAskDelete }: Props) {
  const toRename = useRef(false); // Rename was picked: the box takes the focus, not the "…" button
  const title = item.title || '(no questions)';
  if (renaming) return <RenameBox title={item.title} onDone={onRename} />;
  return (
    <div className={cn('group flex items-center rounded-lg', open ? 'bg-popover' : 'hover:bg-raised')}>
      <button type="button" disabled={disabled || open} aria-current={open} title={details(item)} onClick={onOpen}
              className={cn('min-w-0 flex-1 cursor-pointer truncate py-[7px] pl-2.5 text-left text-[13.5px]',
                            open ? 'cursor-default text-ink' : 'text-ink-soft hover:text-ink disabled:cursor-default disabled:opacity-50')}>
        {title}
      </button>
      <Menu open={menuOpen} label="Chat options" keepFocus={() => toRename.current}
            onOpenChange={(next) => { if (next) toRename.current = false; onMenu(next); }}
            trigger={
              <Button size="icon" aria-label={`Options for “${title}”`} disabled={disabled}
                      className={cn('size-7', menuOpen || open ? 'opacity-100' : 'opacity-60 group-hover:opacity-100')}>
                <Ellipsis aria-hidden="true" className="size-4" />
              </Button>
            }
            items={[
              { label: 'Rename', icon: <Pencil aria-hidden="true" className="size-3.5" />,
                onSelect: () => { toRename.current = true; onStartRename(); } },
              { label: 'Delete', icon: <Trash2 aria-hidden="true" className="size-3.5" />, onSelect: onAskDelete, danger: true },
            ]} />
    </div>
  );
}
