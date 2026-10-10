// M40: the approval wait, refusals during a question, and the empty chat's suggestions (state.ts). All fake.
import { describe, expect, it } from 'vitest';
import type { FromBrain } from './protocol';
import { reduce } from './state';
import { asked, brain, READY, run } from './state-fixtures';

const call = (name: string, asks?: boolean) =>
  brain({ type: 'event', kind: 'tool_call', data: { name, arguments: '{}', ...(asks === undefined ? {} : { asks }) } });

describe('the approval wait (M40)', () => {
  it('a reading tool runs without an approval wait; a popup tool waits', () => {
    expect(run(brain(READY), asked('read it'), call('read_active_window', false)).waiting).toEqual({ name: 'read_active_window', asks: false });
    expect(run(brain(READY), asked('switch'), call('focus_window', true)).waiting?.asks).toBe(true);
  });

  it('a tool_call without a mark counts as asking (an older brain, or a tool it did not know)', () => {
    expect(run(brain(READY), asked('x'), call('some_tool')).waiting).toEqual({ name: 'some_tool', asks: true });
  });

  it('a side request refused while a question runs leaves the question and its wait alone', () => {
    const waiting = run(brain(READY), asked('switch'), call('focus_window', true));
    const refused = reduce(waiting, brain({ type: 'refused', reason: 'busy: Pseudo is still working on the last request' }));
    expect(refused.waiting).toEqual({ name: 'focus_window', asks: true });
    expect(refused.working).toBe(waiting.working);
    expect(refused.turns[0].running).toBe(true);
    expect(refused.notice).toContain('busy');
  });

  it('a refused side request while nothing runs clears what the page said it was doing', () => {
    const switching = run(brain(READY), { type: 'working', what: 'Switching to local' });
    const refused = reduce(switching, brain({ type: 'refused', reason: 'private mode is off' }));
    expect([refused.working, refused.waiting, refused.notice]).toEqual([null, null, 'private mode is off']);
  });
});

describe('suggestions (M40)', () => {
  it('come with ready, and an older brain without them leaves none', () => {
    const offered = { ...READY, suggestions: ["What's on my screen?", 'Summarise the window I was on'] } as FromBrain;
    expect(run(brain(offered)).suggestions).toEqual(["What's on my screen?", 'Summarise the window I was on']);
    expect(run(brain(READY)).suggestions).toEqual([]);
  });
});
