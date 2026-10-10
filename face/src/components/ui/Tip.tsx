// M39: a small label that appears when a control gets the mouse or the keyboard focus (Radix Tooltip).
// Step 0 checked it under the page's security policy: it injects no <style> tag (S2).
// Each Tip brings its own Provider, so a component that uses one works on its own (and in a test).
import * as Tooltip from '@radix-ui/react-tooltip';
import type { ReactElement, ReactNode } from 'react';

type Props = { label: ReactNode; children: ReactElement; side?: 'top' | 'bottom' | 'left' | 'right' };

export function Tip({ label, children, side = 'top' }: Props) {
  return (
    <Tooltip.Provider delayDuration={300}>
      <Tooltip.Root>
        <Tooltip.Trigger asChild>{children}</Tooltip.Trigger>
        <Tooltip.Portal>
          <Tooltip.Content side={side} sideOffset={6}
                           className="z-50 max-w-72 rounded-md border border-edge-strong bg-popover px-2 py-1 text-xs text-ink shadow-lg">
            {label}
          </Tooltip.Content>
        </Tooltip.Portal>
      </Tooltip.Root>
    </Tooltip.Provider>
  );
}
