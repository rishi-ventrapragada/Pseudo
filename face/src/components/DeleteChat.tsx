// M41: the question before a chat is deleted (from the mockup). Every delete asks; there is no "don't ask
// again". Cancel comes first and has the focus, so Enter or Esc right away deletes nothing. Red is used only here
// and for recording (the Phase 10 rules). Saved memories are separate files (M24), so they stay.

import type { SessionItem } from '../protocol';
import { Button } from './ui/Button';
import { Dialog } from './ui/Dialog';

type Props = { item: SessionItem | null; onCancel(): void; onDelete(name: string): void }; // item null: closed

export function DeleteChat({ item, onCancel, onDelete }: Props) {
  return (
    <Dialog open={item !== null} onClose={onCancel} title="Delete this chat?" alert className="w-[420px]"
            footer={<>
              <Button variant="outline" autoFocus onClick={onCancel}>Cancel</Button>
              <Button variant="danger" onClick={() => item && onDelete(item.name)}>Delete</Button>
            </>}>
      <p className="text-sm leading-[1.55] text-muted">
        “{item?.title || '(no questions)'}” will be removed from this laptop. This can't be undone. Saved memories stay.
      </p>
    </Dialog>
  );
}
