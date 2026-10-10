// M18 (moved out of App.tsx in M39): shown instead of the question box when the brain has stopped.
import { RotateCcw } from 'lucide-react';
import { Button } from './ui/Button';

export function Stopped({ onRestart }: { onRestart(): void }) {
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-2xl border border-edge-strong bg-composer px-4 py-3" role="alert">
      <p className="min-w-0 flex-1 text-[13.5px] text-ink-soft">
        Your finished questions are saved. Restarting starts a new session on the default provider.
      </p>
      <Button variant="primary" className="font-medium" onClick={onRestart}>
        <RotateCcw aria-hidden="true" className="size-4" /> Restart the brain
      </Button>
    </div>
  );
}
