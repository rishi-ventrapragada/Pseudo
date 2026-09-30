// M18: the window. It shows what the brain says and sends what you ask; it decides nothing (D11).
// Every message from the brain goes through reduce() (state.ts); every click becomes one
// message to the brain (protocol.ts), through window.pseudo (preload.js).

import { useEffect, useReducer, useRef, useState } from 'react';
import { Markdown } from './Markdown';
import type { ToBrain } from './protocol';
import { PrivacyNote, ProviderBar } from './ProviderBar';
import { Sessions } from './Sessions';
import { initial, reduce, type Turn } from './state';

function TurnView({ turn }: { turn: Turn }) {
  return (
    <section className="turn">
      <div className="you">
        <p className="who">You</p>
        <p>{turn.question}</p>
      </div>
      {turn.steps.length > 0 && (
        <details className="steps">
          <summary>
            {turn.steps.length} step{turn.steps.length === 1 ? '' : 's'}: what Pseudo did
          </summary>
          <ol>
            {turn.steps.map((step, index) => (
              <li key={index}>{step}</li>
            ))}
          </ol>
        </details>
      )}
      {turn.answer !== undefined && (
        <article className="answer" aria-label={`Answer from ${turn.label || 'Pseudo'}`}>
          <p className="who">Pseudo{turn.label ? ` · ${turn.label}` : ''}</p>
          <Markdown text={turn.answer} />
        </article>
      )}
      {turn.failed && <p className="failed" role="alert">No answer: {turn.failed}</p>}
    </section>
  );
}

export function App() {
  const [state, dispatch] = useReducer(reduce, initial);
  const [draft, setDraft] = useState('');
  const end = useRef<HTMLDivElement>(null);

  useEffect(() => {
    window.pseudo.onMessage((message) => dispatch({ type: 'from_brain', message }));
  }, []);
  useEffect(() => {
    end.current?.scrollIntoView({ block: 'end' });
  }, [state.turns]);

  const idle = state.phase === 'ready' && state.working === null;
  const current = state.providers.find((provider) => provider.id === state.provider);

  function send(message: ToBrain, what: string) {
    window.pseudo.send(message);
    dispatch({ type: 'working', what });
  }

  function ask() {
    const text = draft.trim();
    if (!text || !idle) return;
    window.pseudo.send({ type: 'ask', text });
    dispatch({ type: 'asked', text });
    setDraft('');
  }

  function restart() {
    dispatch({ type: 'restarting' });
    window.pseudo.send({ type: 'restart' });
  }

  const status = state.phase === 'stopped' ? "Pseudo's brain stopped."
    : state.phase === 'starting' ? 'Starting the brain'
    : state.working ?? (state.notice || 'Ready. Pseudo reads the window you were on before this one.');

  return (
    <div className={state.sessions ? 'app with-sessions' : 'app'}>
      <header className="top">
        <h1 className="wordmark">Pseudo</h1>
        <ProviderBar providers={state.providers} current={state.provider} disabled={!idle}
                     onSwitch={(id) => send({ type: 'provider', id }, `Switching to ${id}`)} />
        <div className="actions">
          <button type="button" disabled={!idle} onClick={() => send({ type: 'new_session' }, 'Starting a new session')}>
            New session
          </button>
          <button type="button" disabled={state.phase !== 'ready'} onClick={() => window.pseudo.send({ type: 'list_sessions' })}>
            Saved sessions
          </button>
        </div>
      </header>
      <PrivacyNote provider={current} />

      <main className="transcript" aria-label="Conversation">
        {state.phase === 'starting' && (
          <p className="empty">Starting Pseudo's brain. Loading pseudo_hands takes about ten seconds.</p>
        )}
        {state.phase === 'ready' && state.turns.length === 0 && (
          <div className="empty">
            <strong>Ask about the window you were on.</strong>
            <p>Go to that window, then switch back here and ask.</p>
          </div>
        )}
        {state.turns.map((turn, index) => (
          <TurnView key={`${state.session}-${index}`} turn={turn} />
        ))}
        <div ref={end} />
      </main>

      {state.sessions && (
        <Sessions items={state.sessions} current={state.session} disabled={!idle}
                  onOpen={(name) => send({ type: 'open_session', name }, 'Opening the session')}
                  onClose={() => dispatch({ type: 'close_sessions' })} />
      )}

      <footer className="bottom">
        <p className={state.working ? 'status working' : 'status'} aria-live="polite">{status}</p>
        {state.phase === 'stopped' ? (
          <div className="stopped" role="alert">
            <p>Your finished questions are saved. Restarting starts a new session on the default provider.</p>
            <button type="button" onClick={restart}>Restart the brain</button>
          </div>
        ) : (
          <form onSubmit={(event) => { event.preventDefault(); ask(); }}>
            <textarea
              aria-label="Your question"
              rows={2}
              autoFocus
              value={draft}
              placeholder="Ask about the window you were on"
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.shiftKey) { // Enter asks; Shift+Enter is a new line
                  event.preventDefault();
                  ask();
                }
              }}
            />
            <button type="submit" disabled={!idle || !draft.trim()}>Ask</button>
          </form>
        )}
      </footer>
    </div>
  );
}
