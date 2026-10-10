// M42: the memory browser (from the mockup): your saved notes, newest first, and one opened read-only.
// Everything here was redacted AGAIN by pseudo_hands before it reached the page (memory_browse.py). The question and
// the answer are drawn by Markdown.tsx, so masks show as chips ("name", "phone"). Editing and deleting stay in
// Obsidian (D23): this view has no button that changes a note.

import { ChevronLeft, ChevronRight } from 'lucide-react';
import { Markdown, withMasks } from '../Markdown';
import type { MemoryNote } from '../protocol';
import type { Memory } from '../sees';
import { NoticeLine } from './BottomArea';
import { Button } from './ui/Button';

type Props = { memory: Memory; disabled: boolean; notice: string; onOpen(name: string): void; onClose(): void };

export const INTRO = 'Tasks you chose to save, stored redacted on this laptop. Up to three related ones join a new question.';
export const READ_ONLY = 'Read-only here. To edit or delete it, open the memory folder in Obsidian.';

function List({ memory, disabled, onOpen }: Pick<Props, 'memory' | 'disabled' | 'onOpen'>) {
  const { items, note } = memory;
  return (
    <>
      <h1 className="text-2xl font-semibold tracking-tight">Memory</h1>
      <p className="mt-1.5 text-[13.5px] text-muted">{INTRO}</p>
      {!items?.length ? <p className="mt-6 text-[13.5px] text-faint">{items ? note || 'No saved memories yet.' : 'Listing your memories'}</p> : (
        <ul aria-label="Saved memories" className="mt-5 overflow-hidden rounded-[14px] border border-edge">
          {items.map((item) => (
            <li key={item.name} className="border-b border-edge last:border-b-0">
              <button type="button" disabled={disabled} onClick={() => onOpen(item.name)}
                      className="flex w-full cursor-pointer items-center gap-3 px-4 py-3 text-left hover:bg-raised
                                 disabled:cursor-default disabled:opacity-50">
                <span className="w-[84px] shrink-0 font-mono text-xs text-faint">{item.date}</span>
                <span className="min-w-0 flex-1 truncate text-[14px] text-ink">{withMasks(item.title)}</span>
                <ChevronRight aria-hidden="true" className="size-4 shrink-0 text-faint" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

function OpenNote({ note, onClose }: { note: MemoryNote; onClose(): void }) {
  return (
    <>
      <Button className="-ml-2 gap-1 self-start px-2 text-muted" onClick={onClose}>
        <ChevronLeft aria-hidden="true" className="size-4" /> All memories
      </Button>
      {note.note ? <p className="mt-4 text-[13.5px] text-muted">{note.note}</p> : (
        <article aria-label={note.title} className="mt-4 rounded-[14px] border border-edge bg-raised p-5">
          <p className="font-mono text-xs text-faint">{note.date} · saved with your approval</p>
          <h2 className="mt-4 text-xs font-medium text-faint">Question</h2>
          <div className="answer mt-1 text-[15px] text-ink"><Markdown text={note.question} /></div>
          <h2 className="mt-4 text-xs font-medium text-faint">Answer</h2>
          <div className="answer mt-1 text-ink-soft"><Markdown text={note.answer} /></div>
        </article>
      )}
      <p className="mt-4 text-xs text-faint">{READ_ONLY}</p>
    </>
  );
}

export function MemoryView({ memory, disabled, notice, onOpen, onClose }: Props) {
  return (
    <div className="min-h-0 flex-1 overflow-y-auto px-6 py-6">
      <div className="mx-auto flex max-w-[720px] flex-col">
        {memory.open ? <OpenNote note={memory.open} onClose={onClose} /> : <List memory={memory} disabled={disabled} onOpen={onOpen} />}
        <div className="mt-4"><NoticeLine notice={notice} /></div>
      </div>
    </div>
  );
}
