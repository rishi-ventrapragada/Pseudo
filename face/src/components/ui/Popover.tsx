// M41: a small panel that opens from a button (Radix Popover), for the sidebar's provider picker.
// Step 0 (M39, S2) checked it under the page's security policy with modal={false}: no injected <style>.
// Esc or a click outside closes it. Drawn in place, not in a portal, for the reason in Menu.tsx.
import * as RadixPopover from '@radix-ui/react-popover';
import type { ReactElement, ReactNode } from 'react';

type Props = {
  open: boolean;
  onOpenChange(open: boolean): void;
  label: string; // what a screen reader calls the panel
  trigger: ReactElement; // the button that opens it
  children: ReactNode;
};

export function Popover({ open, onOpenChange, label, trigger, children }: Props) {
  return (
    <RadixPopover.Root open={open} onOpenChange={onOpenChange} modal={false}>
      <RadixPopover.Trigger asChild>{trigger}</RadixPopover.Trigger>
      <RadixPopover.Content aria-label={label} side="top" align="start" sideOffset={6}
                            className="z-50 w-[340px] rounded-xl border border-edge-strong bg-popover px-3 pt-1 pb-1 text-ink outline-none
                                       shadow-[0_12px_32px_rgba(0,0,0,0.5)] [&>*:last-child]:border-b-0">
        {children}
      </RadixPopover.Content>
    </RadixPopover.Root>
  );
}
