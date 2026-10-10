// M41: which heading a saved chat sits under in the sidebar (from the Phase 10 mockup).
// A chat's name is the local date and time it started ("20261010-091500-123", session.py), so the group needs
// no file and no question to the brain: only the name and "now", which the tests fix. Display only (D11).

export const GROUPS = ['Today', 'Yesterday', 'Previous 7 days', 'Older'] as const;
export type Group = (typeof GROUPS)[number];

const DAY_MS = 24 * 60 * 60 * 1000;

/** The day a chat started, as local midnight; null if the name isn't a date. */
export function dayOf(name: string): Date | null {
  const m = name.match(/^(\d{4})(\d{2})(\d{2})-/);
  return m ? new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3])) : null;
}

/** Today; Yesterday; Previous 7 days (2 to 7 days ago); or Older. A day after today (the clock was changed)
 *  counts as Today, and a name that isn't a date as Older. */
export function groupOf(name: string, now: Date): Group {
  const day = dayOf(name);
  if (!day) return 'Older';
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const days = Math.round((today.getTime() - day.getTime()) / DAY_MS); // round: a summer-time day is 23 or 25 hours
  if (days <= 0) return 'Today';
  if (days === 1) return 'Yesterday';
  return days <= 7 ? 'Previous 7 days' : 'Older';
}

/** The chats under each heading, in the order they came (newest first); a heading with no chats is left out. */
export function grouped<T extends { name: string }>(items: T[], now: Date): { label: Group; items: T[] }[] {
  return GROUPS.map((label) => ({ label, items: items.filter((item) => groupOf(item.name, now) === label) }))
    .filter((group) => group.items.length > 0);
}
