// M39: join Tailwind class names, skipping the ones that are off.
// cn('rounded-lg', busy && 'opacity-50') -> 'rounded-lg' or 'rounded-lg opacity-50'.
// shadcn uses two packages for this (clsx and tailwind-merge); five lines are enough here.
export function cn(...names: (string | false | null | undefined)[]): string {
  return names.filter(Boolean).join(' ');
}
