// M39: a modal dialog, using the browser's own <dialog> element instead of a library.
// Why: Radix's Dialog injects a <style> tag to stop the page scrolling, and the page's security policy
// refuses injected styles (step 0, S2). The native element needs none of that: showModal() makes the rest of
// the page unreachable (no clicks, no Tab), keeps the keyboard inside, and closes on Esc by itself.
// A web-dev note: `open` is React state; the effect turns it into showModal()/close() calls, because a native
// dialog is opened by calling a method, not by setting an attribute.
import { X } from 'lucide-react';
import { useEffect, useRef, type ReactNode } from 'react';
import { cn } from '../../lib/cn';
import { Button } from './Button';

type Props = {
  open: boolean;
  onClose(): void; // Esc, the X, or a button that closes it
  title: string;
  children: ReactNode;
  footer?: ReactNode;
  alert?: boolean; // a confirm that asks before something can't be undone (role="alertdialog")
  className?: string;
};

export function Dialog({ open, onClose, title, children, footer, alert = false, className }: Props) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      role={alert ? 'alertdialog' : undefined}
      aria-label={title}
      onClose={onClose}
      className={cn('m-auto w-[560px] max-w-[calc(100vw-32px)] rounded-2xl border border-edge-strong bg-dialog p-0 text-ink',
                    'shadow-[0_24px_64px_rgba(0,0,0,0.55)] backdrop:bg-black/55', className)}
    >
      <div className="flex items-center justify-between pt-4 pr-4 pb-2 pl-[22px]">
        <h2 className="text-[17px] font-semibold">{title}</h2>
        {!alert && (
          <Button size="icon" aria-label={`Close ${title.toLowerCase()}`} onClick={onClose}>
            <X aria-hidden="true" className="size-[17px]" />
          </Button>
        )}
      </div>
      <div className="px-[22px] pb-2">{children}</div>
      {footer && <div className="flex justify-end gap-2 px-4 pt-2 pb-4">{footer}</div>}
    </dialog>
  );
}
