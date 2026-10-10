// M42: when the page asks which app a question would read (the chip): when Pseudo becomes free (ready, or a
// question just finished), and whenever its window gains focus, meaning you came back from another app. Only
// while Pseudo is idle: the brain answers `look` only then (bridge_sees.py). Each question also refreshes it.

import { useEffect } from 'react';

export function useLookingAt(idle: boolean): void {
  useEffect(() => {
    if (!idle) return;
    const look = () => window.pseudo.send({ type: 'look' });
    look();
    window.addEventListener('focus', look);
    return () => window.removeEventListener('focus', look);
  }, [idle]);
}
