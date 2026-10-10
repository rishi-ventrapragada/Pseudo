// M18: which provider answers, and whether your words leave this laptop. One button per provider
// in the allowlist (D16); the brain does the switching (chat.py) and says if it refused.
// M39: the choice is a list in Settings, each provider with its privacy note in plain sight.
// M40: the privacy strip under the question box is gone (D28); where each provider sends your words is here.

import { Check } from 'lucide-react';
import { cn } from './lib/cn';
import type { Provider } from './protocol';

type Props = { providers: Provider[]; current: string; disabled: boolean; onSwitch: (id: string) => void };

export function where(provider: Provider): string {
  return provider.leaves_laptop ? 'Leaves this laptop' : 'Stays on this laptop';
}

export function ProviderBar({ providers, current, disabled, onSwitch }: Props) {
  return (
    <div role="group" aria-label="Provider" className="flex flex-col gap-1 border-b border-bubble py-3.5">
      <div className="mb-1 text-sm font-medium">Questions go to</div>
      {providers.map((provider) => {
        const chosen = provider.id === current;
        return (
          <button key={provider.id} type="button" aria-pressed={chosen} disabled={disabled || chosen}
                  onClick={() => onSwitch(provider.id)}
                  className={cn('flex w-full cursor-pointer items-start gap-2.5 rounded-lg px-2.5 py-2 text-left',
                                chosen ? 'bg-bubble' : 'hover:bg-popover disabled:cursor-default disabled:opacity-50')}>
            <span className="flex-1">
              <span className="block text-[13.5px] font-medium">
                {provider.name} · {provider.models[0]} <span className="font-normal text-faint">· {where(provider)}</span>
              </span>
              <span className="mt-0.5 block text-xs leading-[1.45] text-muted">{provider.privacy}</span>
            </span>
            {chosen && <Check aria-hidden="true" className="mt-0.5 size-4 shrink-0" strokeWidth={2} />}
          </button>
        );
      })}
    </div>
  );
}
