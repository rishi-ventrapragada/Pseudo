// M39: one line in Settings: a name, a sentence on what it does now, and its control on the right (from the mockup).
import type { ReactNode } from 'react';

type Props = { label: string; note: ReactNode; children?: ReactNode; open?: boolean };

export function SettingRow({ label, note, children, open }: Props) {
  return (
    <div role="group" aria-label={label} data-open={open} className="flex items-start gap-4 border-b border-bubble py-3.5">
      <div className="flex-1">
        <div className="text-sm font-medium">{label}</div>
        <div className="mt-[3px] text-[12.5px] leading-normal text-muted">{note}</div>
      </div>
      {children}
    </div>
  );
}
