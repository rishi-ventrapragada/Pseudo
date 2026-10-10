// M39: the left sidebar (from the mockup): the name, New chat, your saved chats, and Settings at the bottom.
// It can be hidden (the panel button) and shown again from the top row. Display only: every click becomes a
// message to the brain, or opens Settings.
// M41: Search chats; the chats grouped by day, each with Rename and Delete (a delete always asks first); and, at
// the bottom, the provider picker beside the Settings button (ProviderPicker.tsx, which App builds).
// M42: Chats or Memory under the search (PanelSwitch.tsx), and the Status panel above the picker (App builds it).

import { PanelLeft, SquarePen } from 'lucide-react';
import { useEffect, useState, type ReactNode } from 'react';
import type { SessionItem } from '../protocol';
import { DeleteChat } from './DeleteChat';
import { type Panel, PanelSwitch } from './PanelSwitch';
import { SearchChats } from './SearchChats';
import { SessionList } from './SessionList';
import { Button } from './ui/Button';
import { Tip } from './ui/Tip';

const SEARCH_PAUSE_MS = 250; // ask the brain once typing pauses, not for every key

type Found = { text: string; items: SessionItem[] } | null; // the last search's reply (state.ts)

/** What the list shows: every chat with no search; else the last search's reply (until the newest arrives, the one
 *  before it). "No match" only once the reply for exactly these words is empty. */
export function whatToList(search: string, sessions: SessionItem[] | null, found: Found) {
  if (!search.trim()) return { items: sessions, noMatch: false };
  return { items: found ? found.items : null, noMatch: found?.text === search && found.items.length === 0 };
}

type Props = {
  onHide(): void;
  onNewChat(): void;
  idle: boolean; // Pseudo is ready and not busy: chats can be started, opened, renamed or deleted
  sessions: SessionItem[] | null;
  found: Found;
  current: string;
  onOpen(name: string): void;
  onSearch(text: string): void;
  onRename(name: string, title: string): void;
  onDelete(name: string): void;
  picker: ReactNode; // the bottom row: the provider picker and Settings
  panel: Panel; // M42: what the main area shows: the chat, or your memory
  onPanel(panel: Panel): void;
  memoryCount: number | null; // M42: how many memories you saved; null = not listed yet
  status: ReactNode; // M42: the Status panel, above the picker
};

export function Sidebar(props: Props) {
  const { onHide, onNewChat, idle, sessions, found, current, onOpen, onSearch, onRename, onDelete, picker } = props;
  const { panel, onPanel, memoryCount, status } = props;
  const [search, setSearch] = useState('');
  const [confirm, setConfirm] = useState<SessionItem | null>(null);
  useEffect(() => { // after a pause in typing; and again when the chats change, so a rename or delete shows
    if (!search.trim()) return;
    const timer = setTimeout(() => onSearch(search), SEARCH_PAUSE_MS);
    return () => clearTimeout(timer);
  }, [search, sessions]);

  const { items, noMatch } = whatToList(search, sessions, found);
  return (
    <nav aria-label="Chats and settings" className="flex w-[264px] shrink-0 flex-col border-r border-divider bg-sidebar">
      <div className="drag flex h-11 shrink-0 items-center gap-1.5 px-2">
        <Tip label="Hide the sidebar" side="bottom">
          <Button size="icon" aria-label="Hide the sidebar" onClick={onHide}>
            <PanelLeft aria-hidden="true" className="size-[18px]" />
          </Button>
        </Tip>
        <span className="text-[15px] font-semibold tracking-tight">Pseudo</span>
      </div>
      <div className="px-2.5 pt-1 pb-2">
        <Button variant="outline" className="w-full justify-start bg-raised px-2.5" disabled={!idle} onClick={onNewChat}>
          <SquarePen aria-hidden="true" className="size-4" /> New chat
        </Button>
        <SearchChats text={search} onChange={setSearch} />
        <PanelSwitch panel={panel} count={memoryCount} onChange={onPanel} />
      </div>
      <SessionList items={items} current={current} disabled={!idle} noMatch={noMatch} onOpen={onOpen}
                   onRename={onRename} onAskDelete={setConfirm} />
      <div className="border-t border-divider">{status}{picker}</div>
      <DeleteChat item={confirm} onCancel={() => setConfirm(null)}
                  onDelete={(name) => { setConfirm(null); onDelete(name); }} />
    </nav>
  );
}
