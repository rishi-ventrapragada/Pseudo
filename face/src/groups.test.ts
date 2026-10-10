// M41: the sidebar's date headings (groups.ts). The dates are fixed, so the tests pass on any day.
import { describe, expect, it } from 'vitest';
import { groupOf, grouped } from './groups';

const NOW = new Date(2026, 9, 10, 9, 30); // Saturday 10 October 2026, 09:30 local time

describe('groupOf', () => {
  it.each([
    ['20261010-000000-000', 'Today'], ['20261010-235959-999', 'Today'],
    ['20261009-235959-999', 'Yesterday'], ['20261009-000000-000', 'Yesterday'],
    ['20261008-120000-000', 'Previous 7 days'], ['20261003-000000-000', 'Previous 7 days'], // 7 days ago
    ['20261002-235959-999', 'Older'], ['20250101-000000', 'Older'], // M14's names have no milliseconds
    ['20261012-080000-000', 'Today'], // after today: the clock was changed
    ['not-a-date', 'Older'], ['', 'Older'],
  ])('%s is under %s', (name, group) => {
    expect(groupOf(name, NOW)).toBe(group);
  });

  it('counts calendar days across a month and a year', () => {
    expect(groupOf('20260930-230000-000', new Date(2026, 9, 1, 0, 5))).toBe('Yesterday');
    expect(groupOf('20261231-230000-000', new Date(2027, 0, 1, 8, 0))).toBe('Yesterday');
  });

  it('counts calendar days across a change to or from summer time', () => {
    expect(groupOf('20260328-120000-000', new Date(2026, 2, 29, 12, 0))).toBe('Yesterday'); // Europe's spring change
    expect(groupOf('20261024-120000-000', new Date(2026, 9, 31, 12, 0))).toBe('Previous 7 days');
  });
});

describe('grouped', () => {
  it('keeps the newest-first order under each heading and leaves out empty headings', () => {
    const items = [{ name: '20261010-090000-000' }, { name: '20261010-080000-000' }, { name: '20260901-000000-000' }];
    expect(grouped(items, NOW)).toEqual([
      { label: 'Today', items: [{ name: '20261010-090000-000' }, { name: '20261010-080000-000' }] },
      { label: 'Older', items: [{ name: '20260901-000000-000' }] },
    ]);
  });

  it('no chats: no headings', () => {
    expect(grouped([], NOW)).toEqual([]);
  });
});
