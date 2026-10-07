// M36, M37: what the MAIN process tells the page (state.ts): the Start with Windows entry, the global
// shortcuts, a Ctrl+Alt+T press, and messages the page doesn't know. None of it is the brain's to clear.
// Split from state.test.ts (the 200-line rule). All messages are fake.
import { describe, expect, it } from 'vitest';
import type { FromBrain } from './protocol';
import { initial, reduce, type Action, type State } from './state';

const READY: FromBrain = {
  type: 'ready', provider: 'groq', tools: ['read_active_window'],
  providers: [{ id: 'groq', name: 'Groq', models: ['big'], leaves_laptop: true, privacy: 'fake note', transcribe_model: 'ears' }],
  session: { name: '20260101-000000-000', provider: 'groq', messages: [] },
};

const run = (...actions: Action[]): State => actions.reduce(reduce, initial);

describe('M36: the Start with Windows entry', () => {
  const on = { type: 'autostart', available: true, on: true, note: '' } as const;

  it("records what Windows says, and changes nothing else", () => {
    const state = run({ type: 'from_brain', message: on });
    expect(state.autostart).toEqual({ available: true, on: true, note: '' });
    expect({ ...state, autostart: null }).toEqual(initial);
  });

  it('survives the brain becoming ready: Windows usually answers first (found in the M36 live check)', () => {
    const ready: Action = { type: 'from_brain', message: { type: 'ready', providers: [], provider: 'groq',
                                                                session: { name: 's', provider: 'groq', messages: [] }, tools: [] } };
    const state = run({ type: 'from_brain', message: on }, ready);
    expect(state.phase).toBe('ready');
    expect(state.autostart).toEqual({ available: true, on: true, note: '' });
  });

  it("survives a brain restart and a stopped brain: it is not the brain's to forget", () => {
    const stopped = run({ type: 'from_brain', message: on }, { type: 'from_brain', message: { type: 'brain_stopped', code: 1 } });
    expect(stopped.phase).toBe('stopped');
    expect(stopped.autostart?.on).toBe(true);
    expect(reduce(stopped, { type: 'restarting' })).toEqual({ ...initial, autostart: { available: true, on: true, note: '' } });
  });
});

describe('M37: a message the page does not know', () => {
  it('changes nothing, instead of blanking the page', () => {
    const unknown = { type: 'something_new', value: 1 } as unknown as FromBrain;
    const before = run({ type: 'from_brain', message: READY });
    expect(reduce(before, { type: 'from_brain', message: unknown })).toBe(before);
  });
});

describe('M37: the global shortcuts', () => {
  const keys = [{ id: 'toggle', label: 'Ctrl+Alt+Space', ok: true }, { id: 'talk', label: 'Ctrl+Alt+T', ok: false }];
  const told: Action = { type: 'from_brain', message: { type: 'hotkeys', keys } };
  const pressed: Action = { type: 'from_brain', message: { type: 'talk' } };

  it('records which shortcuts are ours', () => {
    expect(run(told).hotkeys).toEqual(keys);
  });

  it('counts each Ctrl+Alt+T press, and changes nothing else', () => {
    const state = run(pressed, pressed);
    expect(state.talk).toBe(2);
    expect({ ...state, talk: 0 }).toEqual(initial);
  });

  it('the brain becoming ready, stopping or restarting clears neither (and replays no press)', () => {
    const ready = run(told, pressed, { type: 'from_brain', message: READY });
    expect([ready.phase, ready.hotkeys, ready.talk]).toEqual(['ready', keys, 1]);
    const restarted = reduce(reduce(ready, { type: 'from_brain', message: { type: 'brain_stopped', code: 1 } }), { type: 'restarting' });
    expect([restarted.phase, restarted.hotkeys, restarted.talk]).toEqual(['starting', keys, 1]);
  });
});
