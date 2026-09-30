// M18: which provider answers, and whether your words leave this laptop. One button per provider
// in the allowlist (D16); the brain does the switching (chat.py) and says if it refused.

import type { Provider } from './protocol';

type Props = { providers: Provider[]; current: string; disabled: boolean; onSwitch: (id: string) => void };

export function where(provider: Provider): string {
  return provider.leaves_laptop ? 'Leaves this laptop' : 'Stays on this laptop';
}

export function ProviderBar({ providers, current, disabled, onSwitch }: Props) {
  return (
    <div className="providers" role="group" aria-label="Provider">
      {providers.map((provider) => (
        <button
          key={provider.id}
          type="button"
          className={`provider ${provider.leaves_laptop ? 'cloud' : 'local'}`}
          aria-pressed={provider.id === current}
          disabled={disabled || provider.id === current}
          title={provider.privacy}
          onClick={() => onSwitch(provider.id)}
        >
          <span className="provider-id">{provider.id}</span>
          <span className="provider-where">{where(provider)}</span>
        </button>
      ))}
    </div>
  );
}

/** The strip under the header: the provider in use, its models, and its privacy note. */
export function PrivacyNote({ provider }: { provider: Provider | undefined }) {
  if (!provider) return null;
  const fallback = provider.models.length > 1 ? ` (on a 429: ${provider.models.slice(1).join(', ')})` : '';
  return (
    <p className={`privacy ${provider.leaves_laptop ? 'cloud' : 'local'}`}>
      <strong>{where(provider)}.</strong> {provider.name} · {provider.models[0]}
      {fallback}. {provider.privacy}
    </p>
  );
}
