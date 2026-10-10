// M39: the row across the top of the conversation (from the mockup): show the sidebar (when hidden), the chat's
// name, and the Compact bar button. With the blended title bar it is also where you drag the window.

import { PanelLeft } from 'lucide-react';
import { CompactToggle } from '../CompactToggle';
import type { Compact } from '../useCompact';
import { Button } from './ui/Button';
import { Tip } from './ui/Tip';

type Props = { sidebarOpen: boolean; onShowSidebar(): void; title: string; compact: Compact };

export function TopBar({ sidebarOpen, onShowSidebar, title, compact }: Props) {
  return (
    <div className="drag flex h-11 shrink-0 items-center pl-2 pr-[var(--controls-width)]">
      {!sidebarOpen && (
        <Tip label="Show the sidebar" side="bottom">
          <Button size="icon" aria-label="Show the sidebar" onClick={onShowSidebar}>
            <PanelLeft aria-hidden="true" className="size-[18px]" />
          </Button>
        </Tip>
      )}
      <p className="min-w-0 flex-1 truncate px-3 text-center text-[13px] text-muted">{title}</p>
      <CompactToggle compact={compact} />
    </div>
  );
}
