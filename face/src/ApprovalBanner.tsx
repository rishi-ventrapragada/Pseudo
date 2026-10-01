// M18: the banner shown while a tool waits for its result, because that is when pseudo_hands may
// have its approval popup open (D13). The face can't know which tools ask for approval (it decides
// nothing, D11), so the banner shows for every tool call, until that tool's result arrives.
import './banner.css';

export const BANNER_TEXT = 'Approval popup open, check your screen';

export function ApprovalBanner({ waiting }: { waiting: string | null }) {
  if (waiting === null) return null;
  return <p className="approval-banner" role="alert">{BANNER_TEXT}</p>;
}
