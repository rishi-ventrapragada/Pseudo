// M18: the saved sessions (%LOCALAPPDATA%\Pseudo\sessions). Opening one continues it on its
// OWN provider (M16): the brain reconnects if that's another provider, never moves the history.

import type { SessionItem } from './protocol';

type Props = { items: SessionItem[]; current: string; disabled: boolean; onOpen: (name: string) => void; onClose: () => void };

/** "20260930-231500-123" -> "2026-09-30 23:15" */
function when(name: string): string {
  const m = name.match(/^(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})/);
  return m ? `${m[1]}-${m[2]}-${m[3]} ${m[4]}:${m[5]}` : name;
}

export function Sessions({ items, current, disabled, onOpen, onClose }: Props) {
  return (
    <aside className="sessions" aria-label="Saved sessions">
      <header>
        <h2>Saved sessions</h2>
        <button type="button" onClick={onClose}>Close</button>
      </header>
      {items.length === 0 && <p className="empty">No saved sessions yet. Every question you ask is saved here.</p>}
      <ul>
        {items.map((item) => (
          <li key={item.name}>
            <button
              type="button"
              disabled={disabled || item.name === current}
              aria-current={item.name === current}
              onClick={() => onOpen(item.name)}
            >
              <span className="session-title">{item.title || '(no questions)'}</span>
              <span className="session-meta">
                {when(item.name)} · {item.provider} · {item.questions} question{item.questions === 1 ? '' : 's'}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </aside>
  );
}
