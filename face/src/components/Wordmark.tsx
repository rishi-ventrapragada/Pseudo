// M44: Pseudo's name as the window shows it, in the sidebar's top row and the compact bar's: the icon, then
// "Pseudo" in Geist semibold as before. Both are the owner's pick from the Claude Design prototypes.
// At 14-18 px the icon is the plain drawing (pseudo-icon-small.svg): the detailed iris would blur at that size.
// Vite copies the SVG into dist as a file of its own (assetsInlineLimit: 0), so the page's security policy, which
// allows only the page's own files, lets it load: no data: URI, nothing from the network.
// alt="": the word beside it already says the name, so screen readers hear "Pseudo" once.

import icon from '../assets/pseudo-icon-small.svg';
import { cn } from '../lib/cn';

const LOOK = {
  sidebar: { gap: 'gap-2', icon: 'size-[18px]', word: 'text-[15px] font-semibold tracking-tight' },
  bar: { gap: 'gap-1.5', icon: 'size-3.5', word: 'text-xs font-semibold text-muted' },
};

export function Wordmark({ where }: { where: keyof typeof LOOK }) {
  const look = LOOK[where];
  return (
    <span className={cn('inline-flex shrink-0 items-center', look.gap)}>
      <img src={icon} alt="" draggable={false} className={cn('shrink-0', look.icon)} />
      <span className={look.word}>Pseudo</span>
    </span>
  );
}
