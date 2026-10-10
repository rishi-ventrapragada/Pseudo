// M39: cn() joins class names and skips the ones that are off.
import { describe, expect, it } from 'vitest';
import { cn } from './cn';

describe('cn', () => {
  it('joins the names that are on', () => {
    expect(cn('rounded-lg', 'p-2')).toBe('rounded-lg p-2');
    expect(cn('rounded-lg', false && 'opacity-50', null, undefined, '', 'p-2')).toBe('rounded-lg p-2');
  });
});
