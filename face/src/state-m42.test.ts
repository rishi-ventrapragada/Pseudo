// M42: what the window sees (sees.ts, through state.ts): the look-at chip, the memory browser and the Status numbers.
// All fake. Times are fixed numbers, so the 60-second budget rule is tested without waiting.
import { describe, expect, it } from 'vitest';
import type { FromBrain } from './protocol';
import { budgetNow, BUDGET_MS } from './sees';
import { brain, READY, run } from './state-fixtures';
import type { Action } from './state';

const event = (kind: string, data: Record<string, unknown>, at = 0): Action =>
  ({ type: 'from_brain', message: { type: 'event', kind, data }, at });
const NOTE = '2026-10-07-101500-123.md';
const opened: FromBrain = { type: 'memory_note', name: NOTE, date: '2026-10-07', title: 'Read the booking form',
                            question: 'Read the booking form', answer: 'Booked by [PERSON].', note: '' };

describe('the look-at chip (M42)', () => {
  it('names the app, says private for a blocked one, and shows nothing when there is none', () => {
    const look = (app: string, isPrivate: boolean) => brain({ type: 'looking_at', app, private: isPrivate, note: '' });
    expect(run(brain(READY), look('Brave Browser', false)).seen.lookingAt).toEqual({ app: 'Brave Browser', private: false });
    expect(run(brain(READY), look('', true)).seen.lookingAt).toEqual({ app: '', private: true });
    expect(run(brain(READY), look('Brave Browser', false), look('', false)).seen.lookingAt).toBeNull();
    expect(run(brain(READY)).seen.lookingAt).toBeNull();
  });
});

describe('the memory browser (M42)', () => {
  it('starts stale, so the page asks once; asking clears that, and a saved memory makes it stale again', () => {
    expect(run(brain(READY)).seen.memory.stale).toBe(true);
    const asked = run(brain(READY), { type: 'memory', change: 'asked' });
    expect(asked.seen.memory.stale).toBe(false);
    expect(run(brain(READY), { type: 'memory', change: 'asked' }, event('memory_saved', { note: NOTE })).seen.memory.stale)
      .toBe(true);
  });

  it('keeps the list and the open note; closing the note keeps the list', () => {
    const item = { name: NOTE, date: '2026-10-07', title: 'Read the booking form' };
    const state = run(brain(READY), brain({ type: 'memory_list', items: [item], note: '' }), brain(opened));
    expect(state.seen.memory.items).toEqual([item]);
    expect(state.seen.memory.open).toEqual({ name: NOTE, date: '2026-10-07', title: 'Read the booking form',
                                             question: 'Read the booking form', answer: 'Booked by [PERSON].', note: '' });
    const closed = run(brain(READY), brain({ type: 'memory_list', items: [item], note: '' }), brain(opened),
                       { type: 'memory', change: 'closed' });
    expect([closed.seen.memory.open, closed.seen.memory.items]).toEqual([null, [item]]);
  });

  it('a refused note keeps its reason, for the view to say', () => {
    const refused = { ...opened, name: '', question: '', answer: '', note: 'that memory can’t be opened' } as FromBrain;
    expect(run(brain(READY), brain(refused)).seen.memory.open?.note).toBe('that memory can’t be opened');
  });
});

describe('the Status numbers (M42)', () => {
  it('adds up tokens from answers and masked items from tool results, for this chat only', () => {
    const state = run(brain(READY), event('tool_result', { name: 'read_active_window', chars: 900, masked: 3 }),
                      event('tool_result', { name: 'save_memory', chars: 0, by: 'pseudo' }), // no count: 0
                      event('answer', { tokens_in: 1200, tokens_out: 80 }), event('tool_result', { masked: 2 }),
                      event('answer', { tokens_in: 1500, tokens_out: 20 }));
    expect([state.seen.totals.tokens, state.seen.totals.masked]).toEqual([2800, 5]);
    const fresh = run(brain(READY), event('answer', { tokens_in: 10, tokens_out: 5 }),
                      brain({ type: 'session', name: 'x', provider: 'groq', messages: [] }));
    expect(fresh.seen.totals).toEqual({ tokens: 0, masked: 0, budget: null }); // a new or opened chat starts at 0
  });

  it("keeps Groq's latest budget figure with when it came (the headers arrive as text)", () => {
    const state = run(brain(READY), event('tokens', { budget_left: '6200', budget: '8000' }, 5000),
                      event('tokens', { budget_left: null, budget: null }, 9000)); // Claude Code sends none: kept
    expect(state.seen.totals.budget).toEqual({ left: 6200, limit: 8000, at: 5000 });
  });

  it('shows the figure for a minute, then the full budget; nothing before the first question', () => {
    const budget = { left: 6200, limit: 8000, at: 5000 };
    expect(budgetNow(budget, 5000 + BUDGET_MS - 1)).toEqual({ left: 6200, limit: 8000 });
    expect(budgetNow(budget, 5000 + BUDGET_MS)).toEqual({ left: 8000, limit: 8000 });
    expect(budgetNow(null, 5000)).toBeNull();
  });
});
