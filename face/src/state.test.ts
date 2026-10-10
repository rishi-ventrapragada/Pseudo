// M18: how the window's state follows the brain's messages (state.ts). All messages are fake.
// M40: steps are plain-language objects now (steps.ts), and the wait carries `asks`; the checks are the same.
import { describe, expect, it } from 'vitest';
import type { FromBrain } from './protocol';
import { reduce, type State } from './state';
import { asked, brain, READY, run } from './state-fixtures';

const labels = (state: State) => state.turns[0].steps.map((step) => step.label);

describe('reduce', () => {
  it('follows one question from asking to its answer, with who answered in the steps', () => {
    const state = run(brain(READY), asked('What does my window say?'),
      brain({ type: 'event', kind: 'tool_call', data: { name: 'read_active_window', arguments: '{}', asks: false } }),
      brain({ type: 'event', kind: 'answer', data: { text: 'BLUE', calls: 2, tokens_in: 1, tokens_out: 1,
                                                     provider: 'groq', model: 'big', fallback: true } }));
    expect(state.working).toBe('Answered');
    expect(state.turns[0].askedAt).toBe(1000);
    const done = reduce(state, brain({ type: 'turn_done', ok: true }));
    expect(done.working).toBeNull();
    expect(done.turns).toEqual([{ question: 'What does my window say?', running: false, answer: 'BLUE', label: 'groq · big, fallback',
                                  askedAt: undefined, steps: [{ label: 'Read the window you were on' },
                                    { label: 'Answered', detail: 'groq · big (fallback model), 2 call(s), 1 tokens in, 1 out' }] }]);
  });

  it('keeps the wait while a tool runs, and only then', () => {
    const call = brain({ type: 'event', kind: 'tool_call', data: { name: 'focus_window', arguments: '{}', asks: true } });
    const before = run(brain(READY), asked('focus it'));
    expect(before.waiting).toBeNull();
    const waiting = reduce(before, call);
    expect(waiting.waiting).toEqual({ name: 'focus_window', asks: true });
    expect(reduce(waiting, brain({ type: 'event', kind: 'sending', data: {} })).waiting).toEqual({ name: 'focus_window', asks: true });
    for (const end of [brain({ type: 'event', kind: 'tool_result', data: { name: 'focus_window' } }), brain({ type: 'turn_done', ok: false }),
                       brain({ type: 'brain_stopped', code: 1 })]) {
      expect(reduce(waiting, end).waiting).toBeNull();
    }
  });

  it('keeps the answer and the wait while the memory popup is up, then shows the outcome (M24)', () => {
    const answered = run(brain(READY), asked('fix my build'),
      brain({ type: 'event', kind: 'answer', data: { text: 'Add the variable.', calls: 1, tokens_in: 1, tokens_out: 1,
                                                     provider: 'groq', model: 'big', fallback: false } }));
    const saving = reduce(answered, brain({ type: 'event', kind: 'tool_call',
                                            data: { name: 'save_memory', arguments: '{}', by: 'pseudo', asks: true } }));
    expect(saving.waiting).toEqual({ name: 'save_memory', asks: true });
    expect(saving.working).toBe('Offered this task to memory');
    const done = [
      brain({ type: 'event', kind: 'tool_result', data: { name: 'save_memory', chars: 0, is_error: false, by: 'pseudo' } }),
      brain({ type: 'event', kind: 'memory_saved', data: { note: '2026-10-02-120000-001.md' } }),
    ].reduce(reduce, saving);
    expect(done.waiting).toBeNull();
    expect(done.turns[0].answer).toBe('Add the variable.');
    expect(done.turns[0].steps.at(-1)).toEqual({ label: 'Saved this task to memory', detail: 'redacted, as 2026-10-02-120000-001.md' });
  });

  it('marks a refused question as not sent', () => {
    const state = run(brain(READY), asked('/new'), brain({ type: 'refused', reason: 'that looks like a command' }));
    expect(state.turns[0]).toMatchObject({ failed: 'Not sent: that looks like a command', running: false });
  });

  it('opens a saved session with its answers, and who answered as their one step, on its provider', () => {
    const state = run(brain(READY), brain({ type: 'session', name: '20250101-000000-000', provider: 'local', messages: [
      { role: 'user', content: 'q' }, { role: 'assistant', content: 'a', answered_by: 'local · tiny' },
      { role: 'user', content: 'old' }, { role: 'assistant', content: 'b' }] }));
    expect(state.provider).toBe('local');
    expect(state.turns).toEqual([
      { question: 'q', steps: [{ label: 'Answered', detail: 'local · tiny' }], running: false, answer: 'a', label: 'local · tiny' },
      { question: 'old', steps: [], running: false, answer: 'b', label: '' }]); // saved before M16: nobody named
  });

  it('shows a stopped brain, and a switch starts an empty session', () => {
    const switched = run(brain(READY), asked('hi'), brain({ type: 'turn_done', ok: true }),
      brain({ type: 'switched', provider: 'local', session: { name: 'x', provider: 'local', messages: [] } }));
    expect(switched.turns).toEqual([]);
    expect(switched.notice).toContain('new session');
    const stopped = reduce(reduce(switched, asked('hi')), brain({ type: 'brain_stopped', code: 1 }));
    expect(stopped.phase).toBe('stopped');
    expect(stopped.turns[0].failed).toBe('The brain stopped before answering.');
  });

  it('M26: puts each transcript in `heard` once, and explains an empty one', () => {
    const transcribing = run(brain(READY), { type: 'working', what: 'Turning what you said into text' });
    const one = reduce(transcribing, brain({ type: 'transcript', text: 'Say hello.', note: '', seconds: 3.9 }));
    expect([one.working, one.heard, one.turns]).toEqual([null, { text: 'Say hello.', n: 1 }, []]); // not asked (L8)
    const two = reduce(one, brain({ type: 'transcript', text: 'Say hello.', note: '', seconds: 2 }));
    expect(two.heard).toEqual({ text: 'Say hello.', n: 2 }); // the same words again still land again
    const none = reduce(two, brain({ type: 'transcript', text: '', note: "Didn't hear anything, so nothing was sent.", seconds: 1 }));
    expect([none.heard, none.notice]).toEqual([{ text: 'Say hello.', n: 2 }, "Didn't hear anything, so nothing was sent."]);
  });

  it('M26: hands spoken answers to the player without disturbing a running turn', () => {
    const state = run(brain(READY), asked('hi'),
      brain({ type: 'event', kind: 'tool_call', data: { name: 'save_memory', arguments: '{}', by: 'pseudo', asks: true } }),
      brain({ type: 'speech', audio: 'UklGRg==', reason: '' }));
    expect(state.speech).toEqual({ audio: 'UklGRg==', n: 1 });
    expect(state.waiting?.asks).toBe(true); // the memory popup is still waiting: still said
    const failed = reduce(state, brain({ type: 'speech', audio: '', reason: 'the voice is not installed' }));
    expect([failed.speech, failed.notice]).toEqual([{ audio: 'UklGRg==', n: 1 }, "Couldn't speak the answer: the voice is not installed"]);
  });

  it('M30: remembers who answers action requests, and names Claude Code in the steps', () => {
    const actionBrain = { id: 'claude-code', name: 'Claude Code', model: 'sonnet', privacy: 'fake note' };
    const ready = brain({ ...READY, action_brain: actionBrain } as FromBrain);
    expect(run(brain(READY)).actionBrain).toBeNull();
    const state = run(ready, asked('Tick the fake box.'),
      brain({ type: 'event', kind: 'routed', data: { to: 'claude-code', name: 'Claude Code', model: 'sonnet', privacy: 'fake note' } }),
      brain({ type: 'event', kind: 'billing', data: { clean: true, line: 'billing check: CLEAN' } }),
      brain({ type: 'event', kind: 'hands_pid', data: { pid: 7777 } }),
      brain({ type: 'event', kind: 'answer', data: { text: 'Not approved.', calls: 3, tokens_in: 1, tokens_out: 1,
                                                     provider: 'claude-code', model: 'claude-sonnet-5-5', fallback: false } }));
    expect(state.actionBrain).toEqual(actionBrain);
    expect(state.turns[0].label).toBe('claude-code · claude-sonnet-5-5');
    expect(labels(state)).toEqual(['Sent to Claude Code, as an action request', 'Billing check: clean', 'Answered']); // no hands_pid
    expect(state.turns[0].steps[2].detail).toContain('Claude Code · claude-sonnet-5-5 (your subscription)');
  });

  it('M30: a refused action request shows why, and no answer', () => {
    const state = run(brain(READY), asked('Tick the fake box.'),
      brain({ type: 'event', kind: 'billing', data: { clean: false, line: 'billing check: NOT CLEAN' } }),
      brain({ type: 'event', kind: 'failed', data: { reason: 'billing check: NOT CLEAN. Nothing was sent' } }));
    expect(state.turns[0].answer).toBeUndefined();
    expect(state.turns[0].failed).toBe('billing check: NOT CLEAN. Nothing was sent');
  });

  it("M32: keeps the brain's latest word on its warm session, between questions too, and forgets it with the brain", () => {
    const open = { on: true, open: true, ram_mb: 356.4, asked: 2, of: 6, idle_minutes: 10, note: '' };
    const asking = run(brain(READY), asked('Tick the fake box.'));
    expect(asking.warm).toBeNull();
    const during = reduce(asking, brain({ type: 'warm', ...open }));
    expect(during.warm).toMatchObject(open);
    expect(during.working).toBe(asking.working); // it is not a step: what Pseudo is doing stays said
    expect(during.turns).toEqual(asking.turns);
    const idle = reduce(reduce(during, brain({ type: 'turn_done', ok: true })),
      brain({ type: 'warm', ...open, open: false, ram_mb: null, asked: 0, note: 'stopped: idle for 10 minutes' }));
    expect([idle.warm?.open, idle.warm?.note, idle.working]).toEqual([false, 'stopped: idle for 10 minutes', null]);
    expect(reduce(idle, brain(READY)).warm).toBeNull(); // a restarted brain has no session until it says so
    expect(reduce(idle, brain({ type: 'brain_stopped', code: 1 })).phase).toBe('stopped');
  });

  it('M32: the warm-session steps join the turn, also the ones that come after the answer', () => {
    const state = run(brain(READY), asked('Tick the fake box.'),
      brain({ type: 'event', kind: 'warm', data: { request: 6, of: 6 } }),
      brain({ type: 'event', kind: 'answer', data: { text: 'Done.', calls: 3, tokens_in: 1, tokens_out: 1,
                                                     provider: 'claude-code', model: 'claude-sonnet-5-5', fallback: false } }),
      brain({ type: 'event', kind: 'warm_restart', data: { why: 'it has answered 6 requests' } }),
      brain({ type: 'event', kind: 'warm_opened', data: { opened: true, why: '', of: 6 } }));
    expect(state.turns[0].answer).toBe('Done.');
    expect(labels(state)).toEqual(['Used the open Claude Code session', 'Answered', 'The Claude Code session restarts after this request',
                                   'Opened a Claude Code session for your next action requests']);
  });
});
