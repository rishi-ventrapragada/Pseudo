// M18: how the window's state follows the brain's messages (state.ts). All messages are fake.
import { describe, expect, it } from 'vitest';
import type { FromBrain } from './protocol';
import { initial, reduce, type Action, type State } from './state';

const READY: FromBrain = {
  type: 'ready', provider: 'groq', tools: ['read_active_window'],
  providers: [{ id: 'groq', name: 'Groq', models: ['big'], leaves_laptop: true, privacy: 'fake note' }],
  session: { name: '20260101-000000-000', provider: 'groq', messages: [] },
};

const run = (...actions: Action[]): State => actions.reduce(reduce, initial);
const brain = (message: FromBrain): Action => ({ type: 'from_brain', message });

describe('reduce', () => {
  it('follows one question from asking to its labelled answer', () => {
    const state = run(brain(READY), { type: 'asked', text: 'What does my window say?' },
      brain({ type: 'event', kind: 'tool_call', data: { name: 'read_active_window', arguments: '{}' } }),
      brain({ type: 'event', kind: 'answer', data: { text: 'BLUE', calls: 2, tokens_in: 1, tokens_out: 1,
                                                     provider: 'groq', model: 'big', fallback: true } }));
    expect(state.working).toMatch(/^ANSWER/);
    const done = reduce(state, brain({ type: 'turn_done', ok: true }));
    expect(done.working).toBeNull();
    expect(done.turns).toEqual([{ question: 'What does my window say?', running: false, answer: 'BLUE', label: 'groq · big, fallback',
                                  steps: ['MODEL WANTS TO CALL TOOL: read_active_window {}', expect.stringMatching(/^ANSWER/)] }]);
  });

  it('says a tool is running while an approval popup may be up', () => {
    const state = run(brain(READY), { type: 'asked', text: 'focus it' },
      brain({ type: 'event', kind: 'tool_call', data: { name: 'focus_window', arguments: '{"window_id":"w2"}' } }));
    expect(state.working).toContain('Running focus_window. If it needs your approval, a popup asks you');
  });

  it('keeps the approval banner up while a tool waits for its result, and only then', () => {
    const call = brain({ type: 'event', kind: 'tool_call', data: { name: 'focus_window', arguments: '{}' } });
    const asked = run(brain(READY), { type: 'asked', text: 'focus it' });
    expect(asked.toolWaiting).toBeNull();
    const waiting = reduce(asked, call);
    expect(waiting.toolWaiting).toBe('focus_window');
    expect(reduce(waiting, brain({ type: 'event', kind: 'sending', data: {} })).toolWaiting).toBe('focus_window');
    for (const end of [brain({ type: 'event', kind: 'tool_result', data: { name: 'focus_window' } }), brain({ type: 'turn_done', ok: false }),
                       brain({ type: 'brain_stopped', code: 1 }), brain({ type: 'refused', reason: 'x' })]) {
      expect(reduce(waiting, end).toolWaiting).toBeNull();
    }
  });

  it('marks a refused question as not sent', () => {
    const state = run(brain(READY), { type: 'asked', text: '/new' }, brain({ type: 'refused', reason: 'that looks like a command' }));
    expect(state.turns[0]).toMatchObject({ failed: 'Not sent: that looks like a command', running: false });
  });

  it('opens a saved session with its answers and labels, on its provider', () => {
    const state = run(brain(READY), brain({ type: 'session', name: '20250101-000000-000', provider: 'local', messages: [
      { role: 'user', content: 'q' }, { role: 'assistant', content: 'a', answered_by: 'local · tiny' }] }));
    expect(state.provider).toBe('local');
    expect(state.turns).toEqual([{ question: 'q', steps: [], running: false, answer: 'a', label: 'local · tiny' }]);
  });

  it('shows a stopped brain, and a switch starts an empty session', () => {
    const switched = run(brain(READY), { type: 'asked', text: 'hi' }, brain({ type: 'turn_done', ok: true }),
      brain({ type: 'switched', provider: 'local', session: { name: 'x', provider: 'local', messages: [] } }));
    expect(switched.turns).toEqual([]);
    expect(switched.notice).toContain('new session');
    const stopped = reduce(reduce(switched, { type: 'asked', text: 'hi' }), brain({ type: 'brain_stopped', code: 1 }));
    expect(stopped.phase).toBe('stopped');
    expect(stopped.turns[0].failed).toBe('The brain stopped before answering.');
  });
});
