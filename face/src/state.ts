// M18: everything the window shows, and how each message from the brain changes it.
// A pure function (reduce), like a Redux reducer: (state, action) -> new state. No logic
// about providers or sessions lives here; the brain decides, and this only records what it said.

import { answerLabel, describeEvent } from './events';
import type { ActionBrain, Autostart, FromBrain, Hotkey, Provider, SavedMessage, SessionItem, Warm } from './protocol';

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
  actionBrain: ActionBrain | null; // M30: who answers action requests (D26); null = nobody
  session: string; // the session's name (when it started)
  turns: Turn[];
  working: string | null; // what Pseudo is doing right now; null = waiting for you
  toolWaiting: string | null; // a tool that is running (its approval popup may be open); null = none
  notice: string; // the last switch or refusal, in plain words
  sessions: SessionItem[] | null; // the saved-sessions panel; null = closed
  heard: { text: string; n: number } | null; // M26: the latest transcript; n counts them, so each one lands once
  speech: { audio: string; n: number } | null; // M26: the latest spoken answer, for the player
  warm: Warm | null; // M32: what this brain last said about its warm session; null = nothing yet
  autostart: Autostart | null; // M36: what Windows says about Start with Windows; null = not asked yet
  hotkeys: Hotkey[] | null; // M37: the global shortcuts and whether each is ours; null = not told yet
  talk: number; // M37: how often Ctrl+Alt+T was pressed; each press lands once on the mic button
  compact: boolean; // M38: the window is the compact bar (the main process says so; the page only lays itself out)
};

/** What the MAIN process told the page. The brain starting, restarting or stopping never clears it. */
const fromMain = (state: State) => ({ autostart: state.autostart, hotkeys: state.hotkeys, talk: state.talk,
                                      compact: state.compact });

export type Action =
  | { type: 'from_brain'; message: FromBrain }
  | { type: 'asked'; text: string }
  | { type: 'working'; what: string }
  | { type: 'close_sessions' }
  | { type: 'restarting' };

export const initial: State = {
  phase: 'starting', providers: [], provider: '', actionBrain: null, session: '', turns: [], working: null, toolWaiting: null, notice: '',
  sessions: null, heard: null, speech: null, warm: null, autostart: null, hotkeys: null, talk: 0, compact: false,
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
      return { ...initial, ...fromMain(state), phase: 'ready', // M36: what the main process said is kept
               providers: message.providers, provider: message.provider,
               actionBrain: message.action_brain ?? null,
               session: message.session.name, turns: turnsFrom(message.session.messages) };
    case 'event': {
      const { kind, data } = message;
      if (kind === 'hands_pid') return state; // M30: for the main process only (foreground.js)
      const step = describeEvent(kind, data);
      const turns = updateRunning(state.turns, (turn) => ({
        steps: step ? [...turn.steps, step] : turn.steps,
        ...(kind === 'answer' ? { answer: data.text || '(empty answer)', label: answerLabel(data) } : {}),
        ...(kind === 'failed' ? { failed: data.reason } : {}),
      }));
      const working = kind === 'tool_call'
        ? (data.by === 'pseudo' // M24: Pseudo itself offers the answered task to memory
          ? 'Saving this task to memory: answer the approval popup (no answer means no).'
          : `Running ${data.name}. If it needs your approval, a popup asks you; nothing happens until you answer.`)
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
    case 'transcript': // M26: words go to the input box; no words -> the brain's note says why
      return { ...state, working: null, notice: message.text ? '' : message.note,
               heard: message.text ? { text: message.text, n: (state.heard?.n ?? 0) + 1 } : state.heard };
    case 'speech': // M26: it doesn't touch `working`: a memory popup may still be waiting
      return message.audio ? { ...state, speech: { audio: message.audio, n: (state.speech?.n ?? 0) + 1 } }
                           : { ...state, notice: `Couldn't speak the answer: ${message.reason}` };
    case 'warm': // M32: it doesn't touch `working`: it also arrives between questions, every few seconds
      return { ...state, warm: message };
    case 'autostart': // M36: from the main process, not the brain; it can arrive at any time, even while stopped
      return { ...state, autostart: { available: message.available, on: message.on, note: message.note } };
    case 'hotkeys': // M37: from the main process
      return { ...state, hotkeys: message.keys };
    case 'talk': // M37: App turns each new count into one press of the mic button
      return { ...state, talk: state.talk + 1 };
    case 'window_mode': // M38: from the main process, which has already resized the window
      return { ...state, compact: message.compact === true };
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
    default: // a message this page doesn't know (a newer main process): ignored. Without this line the state
      return state; // became undefined and the page went blank (M35's prototype, and nearly M36).
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
      return { ...initial, ...fromMain(state) }; // what the main process said has nothing to do with the brain
  }
}
