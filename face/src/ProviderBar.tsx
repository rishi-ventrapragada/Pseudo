// M18: which provider answers, and whether your words leave this laptop. One button per provider
// in the allowlist (D16); the brain does the switching (chat.py) and says if it refused.
// M39: the choice is a list in Settings, each provider with its privacy note in plain sight; the strip
// (PrivacyNote) is a quiet line under the question box until M40 moves it into the steps (D28).

import { Check } from 'lucide-react';
import { cn } from './lib/cn';
import type { ActionBrain, Provider } from './protocol';

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

/** Under the question box: the provider in use, its models, and its privacy note. */
type NoteProps = { provider: Provider | undefined; actionBrain?: ActionBrain | null };

export function PrivacyNote({ provider, actionBrain }: NoteProps) {
  if (!provider) return null;
  const fallback = provider.models.length > 1 ? ` (on a 429: ${provider.models.slice(1).join(', ')})` : '';
  return (
    <p className="text-center text-xs leading-normal text-faint">
      <strong className="font-medium text-muted">{where(provider)}.</strong> {provider.name} · {provider.models[0]}
      {fallback}. {provider.privacy}
      {/* M30: a second brain answers action requests, but never in private mode (chat.py) */}
      {actionBrain && provider.leaves_laptop && (
        <span className="block">
          <strong className="font-medium text-muted">Actions (click, type, tick, choose):</strong> {actionBrain.name} ·{' '}
          {actionBrain.model}, after a billing check. {actionBrain.privacy}
        </span>
      )}
    </p>
  );
}
