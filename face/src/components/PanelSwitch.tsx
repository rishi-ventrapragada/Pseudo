// M42: Chats or Memory (from the mockup): two buttons under Search chats. Memory shows how many notes you saved.
// The chats stay listed under it either way; Memory changes what the main area shows (MemoryView.tsx).

import { BookOpen, MessageSquare } from 'lucide-react';
import type { ReactNode } from 'react';
import { cn } from '../lib/cn';

export type Panel = 'chats' | 'memory';

type Props = { panel: Panel; count: number | null; onChange(panel: Panel): void }; // count: null = not listed yet

export function PanelSwitch({ panel, count, onChange }: Props) {
  const choice = (value: Panel, label: string, icon: ReactNode, extra?: ReactNode) => (
    <button type="button" aria-pressed={panel === value} onClick={() => onChange(value)}
            className={cn('flex h-[34px] w-full cursor-pointer items-center gap-2.5 rounded-lg px-2.5 text-[13.5px]',
                          panel === value ? 'bg-popover text-ink' : 'text-ink-soft hover:bg-raised hover:text-ink')}>
      {icon}
      {label}
      {extra}
    </button>
  );
  return (
    <div className="mt-2 flex flex-col gap-0.5">
      {choice('chats', 'Chats', <MessageSquare aria-hidden="true" className="size-4" />)}
      {choice('memory', 'Memory', <BookOpen aria-hidden="true" className="size-4" />,
              count !== null && <span className="ml-auto font-mono text-[11.5px] text-faint">{count}</span>)}
    </div>
  );
}
