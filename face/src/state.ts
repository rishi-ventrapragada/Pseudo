// M18: everything the window shows, and how each message from the brain changes it.
// A pure function (reduce), like a Redux reducer: (state, action) -> new state. No logic
// about providers or sessions lives here; the brain decides, and this only records what it said.
// M40: steps are plain-language objects (steps.ts); `waiting` says whether the running tool can show the approval
// popup (the brain's `asks`); a running question keeps when it was asked, for the working line's timer.

import { answerLabel, describeStep, type Step, who } from './steps';
import type { ActionBrain, Autostart, FromBrain, Hotkey, Provider, SavedMessage, SessionItem, Warm } from './protocol';

export type Turn = {
  question: string;
  steps: Step[]; // what Pseudo did, in plain words; who answered is the "Answered" step (D28)
  answer?: string;
  label?: string; // who answered: "groq · openai/gpt-oss-120b" (", fallback")
  failed?: string;
  running: boolean;
  askedAt?: number; // M40: when it was asked (ms), for the timer; only while it runs
};

/** M40: the tool that is running. asks = it can show the approval popup (unmarked tools count as asking). */
export type Waiting = { name: string; asks: boolean };

export type State = {
  phase: 'starting' | 'ready' | 'stopped';
  providers: Provider[];
  provider: string; // the id in use
  actionBrain: ActionBrain | null; // M30: who answers action requests (D26); null = nobody
  session: string; // the session's name (when it started)
  turns: Turn[];
  working: string | null; // what Pseudo is doing right now; null = waiting for you
  waiting: Waiting | null; // M40: a tool that is running, and whether its popup may be open; null = none
  notice: string; // the last switch or refusal, in plain words
  sessions: SessionItem[] | null; // the saved chats; null = not listed yet
  suggestions: string[]; // M40: the empty chat's one-click questions, from the brain
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
  | { type: 'asked'; text: string; at: number }
  | { type: 'working'; what: string }
  | { type: 'restarting' };

export const initial: State = {
  phase: 'starting', providers: [], provider: '', actionBrain: null, session: '', turns: [], working: null, waiting: null,
  notice: '', sessions: null, suggestions: [], heard: null, speech: null, warm: null, autostart: null, hotkeys: null, talk: 0,
  compact: false,
};

/** A saved session's messages -> turns: each question with the answer that followed it. Who answered is kept
 *  as the turn's one step, so it stays one click away (D28). */
export function turnsFrom(messages: SavedMessage[]): Turn[] {
  const turns: Turn[] = [];
  for (const message of messages) {
    if (message.role === 'user') turns.push({ question: message.content, steps: [], running: false });
    else if (turns.length) {
      const label = message.answered_by ?? '';
      Object.assign(turns[turns.length - 1], { answer: message.content, label,
                                               steps: label ? [{ label: 'Answered', detail: who(label) }] : [] });
    }
  }
  return turns;
}

/** Change only the last turn, if it is still running. */
function updateRunning(turns: Turn[], change: (turn: Turn) => Partial<Turn>): Turn[] {
  const last = turns[turns.length - 1];
  return last?.running ? [...turns.slice(0, -1), { ...last, ...change(last) }] : turns;
}

/** A question that is running and has already been taken by the brain (it has steps). */
function questionRunning(state: State): boolean {
  const last = state.turns[state.turns.length - 1];
  return Boolean(last?.running && last.steps.length);
}

function fromBrain(state: State, message: FromBrain): State {
  switch (message.type) {
    case 'ready':
      return { ...initial, ...fromMain(state), phase: 'ready', // M36: what the main process said is kept
               providers: message.providers, provider: message.provider,
               actionBrain: message.action_brain ?? null, suggestions: message.suggestions ?? [],
               session: message.session.name, turns: turnsFrom(message.session.messages) };
    case 'event': {
      const { kind, data } = message;
      if (kind === 'hands_pid') return state; // M30: for the main process only (foreground.js)
      const step = describeStep(kind, data);
      const turns = updateRunning(state.turns, (turn) => ({
        steps: step ? [...turn.steps, step] : turn.steps,
        ...(kind === 'answer' ? { answer: data.text || '(empty answer)', label: answerLabel(data) } : {}),
        ...(kind === 'failed' ? { failed: data.reason } : {}),
      }));
      const waiting = kind === 'tool_call' ? { name: String(data.name), asks: data.asks !== false } // no mark: it asks
        : kind === 'tool_result' ? null : state.waiting;
      return { ...state, turns, working: step?.label ?? state.working, waiting };
    }
    case 'turn_done':
      return { ...state, working: null, waiting: null,
               turns: updateRunning(state.turns, () => ({ running: false, askedAt: undefined })) };
    case 'switched':
      return { ...state, provider: message.provider, session: message.session.name, turns: [], working: null,
               waiting: null, notice: `Switched to ${message.provider}. This is a new session: a session keeps one provider.` };
    case 'session':
      return { ...state, provider: message.provider, session: message.name, turns: turnsFrom(message.messages),
               working: null, waiting: null, sessions: null,
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
        return { ...state, working: null, waiting: null,
                 turns: updateRunning(state.turns, () => ({ failed: `Not sent: ${message.reason}`, running: false })) };
      }
      // M40: a side request refused while a question runs leaves the question, and its approval wait, alone
      if (questionRunning(state)) return { ...state, notice: message.reason };
      return { ...state, working: null, waiting: null, notice: message.reason };
    }
    case 'brain_stopped':
      return { ...state, phase: 'stopped', working: null, waiting: null,
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
               turns: [...state.turns, { question: action.text, steps: [], running: true, askedAt: action.at }] };
    case 'working':
      return { ...state, notice: '', working: action.what };
    case 'restarting':
      return { ...initial, ...fromMain(state) }; // what the main process said has nothing to do with the brain
  }
}
