// M39: a button that shows or hides what is under it, with a chevron (Radix Collapsible).
// Used for an answer's steps now, and for the Status panel later (M42).
import * as Collapsible from '@radix-ui/react-collapsible';
import { ChevronDown } from 'lucide-react';
import { useState, type ReactNode } from 'react';
import { cn } from '../../lib/cn';

type Props = { summary: ReactNode; children: ReactNode; defaultOpen?: boolean; className?: string; triggerClassName?: string };

export function Disclosure({ summary, children, defaultOpen = false, className, triggerClassName }: Props) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <Collapsible.Root open={open} onOpenChange={setOpen} className={className}>
      <Collapsible.Trigger
        className={cn('inline-flex cursor-pointer items-center gap-1 rounded-lg text-[12.5px] text-faint hover:text-ink',
                      triggerClassName)}
      >
        {summary}
        <ChevronDown aria-hidden="true" className={cn('size-3.5 transition-transform', open && 'rotate-180')} />
      </Collapsible.Trigger>
      <Collapsible.Content>{children}</Collapsible.Content>
    </Collapsible.Root>
  );
}
