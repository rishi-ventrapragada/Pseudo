// M18: everything the window shows, and how each message from the brain changes it.
// A pure function (reduce), like a Redux reducer: (state, action) -> new state. No logic
// about providers or sessions lives here; the brain decides, and this only records what it said.

import { answerLabel, describeEvent } from './events';
import type { FromBrain, Provider, SavedMessage, SessionItem } from './protocol';

export type Turn = {
  question: string;
  steps: string[]; // the loop's events, worded as in the terminal
  answer?: string;
  label?: string; // who answered: "groq · openai/gpt-oss-120b" (", fallback")
  failed?: string;
  running: boolean;
};

export type State = {
  phase: 'starting' | 'ready' | 'stopped';
  providers: Provider[];
  provider: string; // the id in use
  session: string; // the session's name (when it started)
  turns: Turn[];
  working: string | null; // what Pseudo is doing right now; null = waiting for you
  toolWaiting: string | null; // a tool that is running (its approval popup may be open); null = none
  notice: string; // the last switch or refusal, in plain words
  sessions: SessionItem[] | null; // the saved-sessions panel; null = closed
};

export type Action =
  | { type: 'from_brain'; message: FromBrain }
  | { type: 'asked'; text: string }
  | { type: 'working'; what: string }
  | { type: 'close_sessions' }
  | { type: 'restarting' };

export const initial: State = {
  phase: 'starting', providers: [], provider: '', session: '', turns: [], working: null, toolWaiting: null, notice: '',
  sessions: null,
};

/** A saved session's messages -> turns: each question with the answer that followed it. */
export function turnsFrom(messages: SavedMessage[]): Turn[] {
  const turns: Turn[] = [];
  for (const message of messages) {
    if (message.role === 'user') turns.push({ question: message.content, steps: [], running: false });
    else if (turns.length) Object.assign(turns[turns.length - 1], { answer: message.content, label: message.answered_by ?? '' });
  }
  return turns;
}

/** Change only the last turn, if it is still running. */
function updateRunning(turns: Turn[], change: (turn: Turn) => Partial<Turn>): Turn[] {
  const last = turns[turns.length - 1];
  return last?.running ? [...turns.slice(0, -1), { ...last, ...change(last) }] : turns;
}

function fromBrain(state: State, message: FromBrain): State {
  switch (message.type) {
    case 'ready':
      return { ...initial, phase: 'ready', providers: message.providers, provider: message.provider,
               session: message.session.name, turns: turnsFrom(message.session.messages) };
    case 'event': {
      const { kind, data } = message;
      const step = describeEvent(kind, data);
      const turns = updateRunning(state.turns, (turn) => ({
        steps: step ? [...turn.steps, step] : turn.steps,
        ...(kind === 'answer' ? { answer: data.text || '(empty answer)', label: answerLabel(data) } : {}),
        ...(kind === 'failed' ? { failed: data.reason } : {}),
      }));
      const working = kind === 'tool_call'
        ? `Running ${data.name}. If it needs your approval, a popup asks you; nothing happens until you answer.`
        : step ?? state.working;
      const toolWaiting = kind === 'tool_call' ? String(data.name) : kind === 'tool_result' ? null : state.toolWaiting;
      return { ...state, turns, working, toolWaiting };
    }
    case 'turn_done':
      return { ...state, working: null, toolWaiting: null, turns: updateRunning(state.turns, () => ({ running: false })) };
    case 'switched':
      return { ...state, provider: message.provider, session: message.session.name, turns: [], working: null,
               toolWaiting: null, notice: `Switched to ${message.provider}. This is a new session: a session keeps one provider.` };
    case 'session':
      return { ...state, provider: message.provider, session: message.name, turns: turnsFrom(message.messages),
               working: null, toolWaiting: null, sessions: null,
               notice: message.messages.length ? `Continuing a saved session on ${message.provider}.`
                                               : `New session on ${message.provider}.` };
    case 'sessions':
      return { ...state, sessions: message.items };
    case 'refused': {
      const last = state.turns[state.turns.length - 1];
      if (last?.running && !last.steps.length) { // the question itself was refused: it was never sent
        return { ...state, working: null, toolWaiting: null,
                 turns: updateRunning(state.turns, () => ({ failed: `Not sent: ${message.reason}`, running: false })) };
      }
      return { ...state, working: null, toolWaiting: null, notice: message.reason };
    }
    case 'brain_stopped':
      return { ...state, phase: 'stopped', working: null, toolWaiting: null,
               turns: updateRunning(state.turns, () => ({ failed: 'The brain stopped before answering.', running: false })) };
  }
}

export function reduce(state: State, action: Action): State {
  switch (action.type) {
    case 'from_brain':
      return fromBrain(state, action.message);
    case 'asked':
      return { ...state, notice: '', working: 'Sending your question',
               turns: [...state.turns, { question: action.text, steps: [], running: true }] };
    case 'working':
      return { ...state, notice: '', working: action.what };
    case 'close_sessions':
      return { ...state, sessions: null };
    case 'restarting':
      return initial;
  }
}
