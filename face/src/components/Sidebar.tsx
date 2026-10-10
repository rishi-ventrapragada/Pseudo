// M39: the left sidebar (from the mockup): the name, New chat, your saved chats, and Settings at the bottom.
// It can be hidden (the panel button) and shown again from the top row. Display only: every click becomes a
// message to the brain, or opens Settings.

import { PanelLeft, SlidersHorizontal, SquarePen } from 'lucide-react';
import type { SessionItem } from '../protocol';
import { SessionList } from './SessionList';
import { Button } from './ui/Button';
import { Tip } from './ui/Tip';

type Props = {
  onHide(): void;
  onNewChat(): void;
  idle: boolean; // Pseudo is ready and not busy: chats can be started or opened
  sessions: SessionItem[] | null;
  current: string;
  onOpen(name: string): void;
  onSettings(): void;
};

export function Sidebar({ onHide, onNewChat, idle, sessions, current, onOpen, onSettings }: Props) {
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
      </div>
      <h2 className="px-5 pt-3 pb-1 text-xs font-medium text-faint">Chats</h2>
      <SessionList items={sessions} current={current} disabled={!idle} onOpen={onOpen} />
      <div className="border-t border-divider p-2.5">
        <Button variant="outline" className="w-full justify-start px-2.5 text-[13px]" onClick={onSettings}>
          <SlidersHorizontal aria-hidden="true" className="size-4 text-muted" /> Settings
        </Button>
      </div>
    </nav>
  );
}
