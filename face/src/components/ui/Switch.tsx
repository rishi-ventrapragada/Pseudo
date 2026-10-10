// M39: an on/off switch (Radix Switch): a real <button role="switch" aria-checked>, so the keyboard and screen
// readers treat it as one. White track when on, grey when off (monochrome, from the mockup); the knob is
// centred in the track and slides across.
import * as RadixSwitch from '@radix-ui/react-switch';

type Props = { checked: boolean; onChange(on: boolean): void; label: string; disabled?: boolean };

export function Switch({ checked, onChange, label, disabled }: Props) {
  return (
    <RadixSwitch.Root
      checked={checked}
      onCheckedChange={onChange}
      disabled={disabled}
      aria-label={label}
      className="inline-flex h-5 w-9 shrink-0 cursor-pointer items-center rounded-full bg-control p-0.5 transition-colors
                 data-[state=checked]:bg-ink disabled:cursor-default disabled:opacity-50"
    >
      <RadixSwitch.Thumb
        className="block size-4 rounded-full bg-ink-soft shadow-sm transition-transform
                   data-[state=checked]:translate-x-4 data-[state=checked]:bg-sidebar"
      />
    </RadixSwitch.Root>
  );
}
