// M18: the banner shown while a tool waits for its result, because that is when pseudo_hands may
// have its approval popup open (D13). The face can't know which tools ask for approval (it decides
// nothing, D11), so the banner shows for every tool call, until that tool's result arrives.
// M39: restyled, and kept neutral: amber means "a popup IS waiting", which the face can tell only from M40 on.
import { ShieldAlert } from 'lucide-react';

export const BANNER_TEXT = 'Working… an approval popup may appear'; // true for reads too (most tools ask nothing)

export function ApprovalBanner({ waiting }: { waiting: string | null }) {
  if (waiting === null) return null;
  return (
    <p className="flex items-center gap-2.5 rounded-xl border border-edge bg-raised px-3.5 py-2.5 text-[13.5px] font-medium"
       role="alert">
      <ShieldAlert aria-hidden="true" className="size-[18px] shrink-0 text-muted" />
      {BANNER_TEXT}
    </p>
  );
}
