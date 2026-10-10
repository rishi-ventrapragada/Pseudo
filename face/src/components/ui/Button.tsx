// M39: Pseudo's one button, in a few looks. Adapted by hand from shadcn/ui's Button (MIT), without its two
// helper packages: the looks are plain objects, and cn() joins the class names.
// A web-dev note: `variant` and `size` work like props on a styled component; each picks a string of Tailwind classes.
import type { ButtonHTMLAttributes } from 'react';
import { cn } from '../../lib/cn';

const VARIANTS = {
  primary: 'bg-ink text-sidebar hover:bg-white', // the white Ask and Done buttons
  outline: 'border border-edge text-ink hover:bg-raised',
  ghost: 'text-muted hover:bg-popover hover:text-ink', // icon buttons, quiet actions
  danger: 'bg-danger-strong text-white hover:brightness-110', // only the Delete button in a confirm
};

const SIZES = {
  md: 'h-[34px] rounded-[10px] px-3.5 text-[13.5px]',
  sm: 'h-[30px] rounded-lg px-2 text-[12.5px]',
  icon: 'size-8 rounded-lg', // a square icon button
  round: 'size-[34px] rounded-full', // the mic and Ask, inside the question box
  xs: 'h-[26px] rounded-lg px-2.5 text-xs', // (M43) Hide answer, in the compact bar
  bar: 'h-[26px] w-[30px] rounded-md', // (M43) Full window, in the compact bar's 30 px top row
};

type Props = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: keyof typeof VARIANTS; size?: keyof typeof SIZES };

export function Button({ variant = 'ghost', size = 'md', type = 'button', className, ...rest }: Props) {
  return (
    <button
      type={type}
      className={cn('inline-flex shrink-0 cursor-pointer items-center justify-center gap-2 transition-colors',
                    'disabled:cursor-default disabled:opacity-50', VARIANTS[variant], SIZES[size], className)}
      {...rest}
    />
  );
}
