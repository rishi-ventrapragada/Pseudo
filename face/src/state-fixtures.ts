// M40: fake messages shared by the state tests (state.test.ts, state-m40.test.ts). Not a test file itself.
import type { FromBrain } from './protocol';
import { initial, reduce, type Action, type State } from './state';

export const READY: FromBrain = {
  type: 'ready', provider: 'groq', tools: ['read_active_window'],
  providers: [{ id: 'groq', name: 'Groq', models: ['big'], leaves_laptop: true, privacy: 'fake note', transcribe_model: 'ears' }],
  session: { name: '20260101-000000-000', provider: 'groq', messages: [] },
};

export const run = (...actions: Action[]): State => actions.reduce(reduce, initial);
export const brain = (message: FromBrain): Action => ({ type: 'from_brain', message });
export const asked = (text: string): Action => ({ type: 'asked', text, at: 1000 });
