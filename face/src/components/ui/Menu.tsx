// M41: a small menu that opens from a button (Radix DropdownMenu), for a chat's Rename and Delete.
// Step 0 (M39, S2) checked it under the page's security policy with modal={false}: no injected <style>.
// Radix gives it the keyboard: arrows move between items, Enter picks, Esc closes and returns to the button.
// Drawn in place, not in a portal: `position: fixed` already lifts it above the sidebar, and then a test's
// render (on the server, with no browser) can see the items too.
import * as RadixMenu from '@radix-ui/react-dropdown-menu';
import type { ReactElement, ReactNode } from 'react';
import { cn } from '../../lib/cn';

export type MenuItem = { label: string; icon: ReactNode; onSelect(): void; danger?: boolean };

type Props = {
  open: boolean;
  onOpenChange(open: boolean): void;
  label: string; // what a screen reader calls the menu
  trigger: ReactElement; // the button that opens it
  items: MenuItem[];
  keepFocus?(): boolean; // true: don't move the focus back to the button on closing (an item put it somewhere)
};

export function Menu({ open, onOpenChange, label, trigger, items, keepFocus }: Props) {
  return (
    <RadixMenu.Root open={open} onOpenChange={onOpenChange} modal={false}>
      <RadixMenu.Trigger asChild>{trigger}</RadixMenu.Trigger>
      <RadixMenu.Content aria-label={label} align="start" sideOffset={4}
                         onCloseAutoFocus={(event) => { if (keepFocus?.()) event.preventDefault(); }}
                         className="z-50 min-w-40 rounded-xl border border-edge-strong bg-popover p-1 shadow-[0_12px_32px_rgba(0,0,0,0.5)]">
        {items.map((item) => (
          <RadixMenu.Item key={item.label} onSelect={item.onSelect}
                          className={cn('flex h-8 cursor-pointer items-center gap-2.5 rounded-lg px-2.5 text-[13px] outline-none',
                                        'data-[highlighted]:bg-bubble', item.danger ? 'text-danger' : 'text-ink')}>
            {item.icon}
            {item.label}
          </RadixMenu.Item>
        ))}
      </RadixMenu.Content>
    </RadixMenu.Root>
  );
}
