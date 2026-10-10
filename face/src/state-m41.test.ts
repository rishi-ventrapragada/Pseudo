// M41: the open chat's title, a search's reply, and the end of a rename or delete (state.ts). All fake.
import { describe, expect, it } from 'vitest';
import type { FromBrain } from './protocol';
import { asked, brain, READY, run } from './state-fixtures';

const OPEN = '20260101-000000-000'; // READY's session
const OTHER = '20251231-120000-000';
const item = (name: string, title: string) => ({ name, provider: 'groq', questions: 1, title });
const working = { type: 'working', what: 'Renaming the chat' } as const;

describe('the open chat’s title (M41)', () => {
  it('comes with ready and with an opened chat; a switch starts a chat with none', () => {
    const titled = { ...READY, session: { name: OPEN, provider: 'groq', messages: [], title: 'Booking form' } } as FromBrain;
    expect(run(brain(titled)).title).toBe('Booking form');
    expect(run(brain(READY)).title).toBe(''); // an older brain sends no title
    const opened = run(brain(READY), brain({ type: 'session', name: OTHER, provider: 'groq', messages: [], title: 'Old one' }));
    expect(opened.title).toBe('Old one');
    expect(run(brain(titled), brain({ type: 'switched', provider: 'local',
                                      session: { name: OTHER, provider: 'local', messages: [] } })).title).toBe('');
  });

  it('a rename of the open chat changes it and ends the job; a rename of another chat only ends the job', () => {
    const renamed = run(brain(READY), working, brain({ type: 'renamed', name: OPEN, title: 'Greeting' }));
    expect([renamed.title, renamed.working]).toEqual(['Greeting', null]);
    const other = run(brain(READY), working, brain({ type: 'renamed', name: OTHER, title: 'Old one' }));
    expect([other.title, other.working]).toEqual(['', null]);
  });
});

describe('a delete (M41)', () => {
  it('ends the job and says what went', () => {
    const done = run(brain(READY), { type: 'working', what: 'Deleting the chat' },
                     brain({ type: 'deleted', name: OTHER, title: 'What does the form say?' }));
    expect([done.working, done.notice]).toEqual([null, 'Deleted “What does the form say?”.']);
  });

  it('of the open chat: the new chat came first, and the notice is about the delete', () => {
    const done = run(brain(READY), asked('hello'), brain({ type: 'turn_done', ok: true }),
                     brain({ type: 'session', name: OTHER, provider: 'groq', messages: [], title: '' }),
                     brain({ type: 'sessions', items: [] }), brain({ type: 'deleted', name: OPEN, title: 'hello' }));
    expect([done.session, done.turns, done.sessions, done.notice]).toEqual([OTHER, [], [], 'Deleted “hello”.']);
  });

  it('a chat with no questions still gets a notice', () => {
    expect(run(brain(READY), brain({ type: 'deleted', name: OTHER, title: '' })).notice).toBe('Deleted “a chat with no questions”.');
  });
});

describe('search (M41)', () => {
  it('keeps the reply with the words it was for, and leaves the full list alone', () => {
    const state = run(brain(READY), brain({ type: 'sessions', items: [item(OPEN, 'a'), item(OTHER, 'b')] }),
                      brain({ type: 'found', text: 'b', items: [item(OTHER, 'b')] }));
    expect(state.found).toEqual({ text: 'b', items: [item(OTHER, 'b')] });
    expect(state.sessions).toHaveLength(2);
  });

  it('a refused rename while nothing runs ends the job with the reason', () => {
    const refused = run(brain(READY), working, brain({ type: 'refused', reason: "a chat's name can't be empty" }));
    expect([refused.working, refused.notice]).toEqual([null, "a chat's name can't be empty"]);
  });
});
