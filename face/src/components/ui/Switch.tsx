// M39: an on/off switch (Radix Switch): a real <button role="switch" aria-checked>, so the keyboard and screen
// readers treat it as one. White when on, grey when off (monochrome, from the mockup).
import * as RadixSwitch from '@radix-ui/react-switch';

type Props = { checked: boolean; onChange(on: boolean): void; label: string; disabled?: boolean };

export function Switch({ checked, onChange, label, disabled }: Props) {
  return (
    <RadixSwitch.Root
      checked={checked}
      onCheckedChange={onChange}
      disabled={disabled}
      aria-label={label}
      className="relative mt-0.5 inline-flex h-[22px] w-[38px] shrink-0 cursor-pointer rounded-full bg-control transition-colors
                 data-[state=checked]:bg-ink disabled:cursor-default disabled:opacity-50"
    >
      <RadixSwitch.Thumb
        className="block size-4 translate-x-[3px] rounded-full bg-muted transition-transform
                   data-[state=checked]:translate-x-[19px] data-[state=checked]:bg-sidebar"
      />
    </RadixSwitch.Root>
  );
}
