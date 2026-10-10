// M18: which provider answers, and whether your words leave this laptop. One button per provider
// in the allowlist (D16); the brain does the switching (chat.py) and says if it refused.
// M39: the choice is a list in Settings, each provider with its privacy note in plain sight.
// M40: the privacy strip under the question box is gone (D28); where each provider sends your words is here.

import { Check } from 'lucide-react';
import { cn } from './lib/cn';
import type { ActionBrain, Provider } from './protocol';

/** M40: where requests to click, type or tick go (D26), said in Settings now instead of under the question box.
 *  Shown only where they really go there: private mode never routes to Claude Code (chat.py). */
export function ActionBrainNote({ actionBrain, provider }: { actionBrain: ActionBrain | null; provider: Provider | undefined }) {
  if (!actionBrain || !provider?.leaves_laptop) return null;
  return (
    <div role="note" aria-label="Where action requests go" className="border-b border-bubble py-3.5">
      <div className="text-sm font-medium">Clicking, typing and ticking</div>
      <div className="mt-[3px] text-[12.5px] leading-normal text-muted">
        These requests go to {actionBrain.name} · {actionBrain.model}, after a billing check. {actionBrain.privacy}
      </div>
    </div>
  );
}

type Props = { providers: Provider[]; current: string; disabled: boolean; onSwitch: (id: string) => void };

export function where(provider: Provider): string {
  return provider.leaves_laptop ? 'Leaves this laptop' : 'Stays on this laptop';
}

export function ProviderBar({ providers, current, disabled, onSwitch }: Props) {
  return (
    <div role="group" aria-label="Provider" className="flex flex-col gap-1 border-b border-bubble py-3.5">
      <div className="mb-1 text-sm font-medium">Questions go to</div>
      {providers.filter((provider) => !provider.disabled).map((provider) => { // M41: a switched-off one can't be chosen
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
              <span className="mt-0.5 block text-xs leading-[1.45] text-muted">
                {provider.privacy}
                {provider.models.length > 1 && ` On a rate limit: ${provider.models.slice(1).join(', ')}, never another provider.`}
              </span>
            </span>
            {chosen && <Check aria-hidden="true" className="mt-0.5 size-4 shrink-0" strokeWidth={2} />}
          </button>
        );
      })}
    </div>
  );
}
