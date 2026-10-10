// M42: what Pseudo sees, as its window shows it: the look-at chip, the memory browser and the Status panel's numbers.
// Pure functions that state.ts calls, like a slice of a Redux reducer. Nothing is decided here: the brain says which
// app a question would read, which memories exist and what each answer cost; the page only adds numbers up (D11).

import type { EventData, FromBrain, MemoryItem, MemoryNote } from './protocol';

/** The chip: the app's own name, or private (a blocked app, never named). null = nothing to show. */
export type LookingAt = { app: string; private: boolean };
/** The memory browser: the list (null = not asked yet), why it is empty, the open note, and whether to ask again. */
export type Memory = { items: MemoryItem[] | null; note: string; open: MemoryNote | null; stale: boolean };
/** Groq's tokens left this minute, and when it said so (ms). */
export type Budget = { left: number; limit: number; at: number };
/** The Status panel's numbers for the open chat, since it was opened in this window (saved chats keep no tokens). */
export type Totals = { tokens: number; masked: number; budget: Budget | null };
export type Seen = { lookingAt: LookingAt | null; memory: Memory; totals: Totals };

export const noTotals: Totals = { tokens: 0, masked: 0, budget: null };
export const nothingSeen: Seen = { lookingAt: null, memory: { items: null, note: '', open: null, stale: true },
                                   totals: noTotals };
export const BUDGET_MS = 60_000; // a per-minute budget refills within the minute

/** A number the brain sent (Groq's headers arrive as text); NaN if there is none. */
function num(value: unknown): number {
  return typeof value === 'number' || (typeof value === 'string' && value.trim() !== '') ? Number(value) : NaN;
}

/** One event's share of the totals: tokens from the turn's end (`answer`, or `failed`: a failed turn used tokens
 *  too), Groq's budget from `tokens`, masked items from `tool_result`. */
export function addEvent(totals: Totals, kind: string, data: EventData, at: number): Totals {
  if (kind === 'answer' || kind === 'failed') {
    return { ...totals, tokens: totals.tokens + (num(data.tokens_in) || 0) + (num(data.tokens_out) || 0) };
  }
  if (kind === 'tool_result') return { ...totals, masked: totals.masked + (num(data.masked) || 0) };
  const left = num(data.budget_left), limit = num(data.budget);
  if (kind === 'tokens' && left >= 0 && limit > 0) return { ...totals, budget: { left, limit, at } };
  return totals;
}

/** Groq's budget as the panel shows it: the last figure for a minute, then full again. null = not known yet. */
export function budgetNow(budget: Budget | null, now: number): { left: number; limit: number } | null {
  if (!budget) return null;
  return now - budget.at < BUDGET_MS ? { left: budget.left, limit: budget.limit } : { left: budget.limit, limit: budget.limit };
}

/** How one message from the brain changes what the window sees. `at` is when it arrived (ms). */
export function seeMessage(seen: Seen, message: FromBrain, at: number): Seen {
  switch (message.type) {
    case 'looking_at':
      return { ...seen, lookingAt: message.private ? { app: '', private: true }
                                   : message.app ? { app: message.app, private: false } : null };
    case 'memory_list':
      return { ...seen, memory: { ...seen.memory, items: message.items, note: message.note, stale: false } };
    case 'memory_note': {
      const { type: _type, ...note } = message;
      return { ...seen, memory: { ...seen.memory, open: note } };
    }
    case 'switched':
    case 'session': // a new or opened chat starts at 0 (deleting the open chat sends `session` too)
      return { ...seen, totals: noTotals };
    case 'event': {
      const stale = seen.memory.stale || message.kind === 'memory_saved'; // a new memory: list them again
      return { ...seen, memory: { ...seen.memory, stale }, totals: addEvent(seen.totals, message.kind, message.data, at) };
    }
    default:
      return seen;
  }
}

/** The page's own memory actions: it asked for the list (so it doesn't ask twice), or closed the open note. */
export function memoryAction(seen: Seen, change: 'asked' | 'closed'): Seen {
  return { ...seen, memory: change === 'asked' ? { ...seen.memory, stale: false } : { ...seen.memory, open: null } };
}
