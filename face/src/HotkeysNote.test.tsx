// M37: the shortcuts line (HotkeysNote.tsx). All states are fake.
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { HotkeysNote, hotkeysLine } from './HotkeysNote';
import type { Hotkey } from './protocol';

const BOTH: Hotkey[] = [{ id: 'toggle', label: 'Ctrl+Alt+Enter', ok: true }, { id: 'talk', label: 'Ctrl+Alt+T', ok: true }];
const TALK_TAKEN: Hotkey[] = [BOTH[0], { ...BOTH[1], ok: false }];

describe('hotkeysLine', () => {
  it('says what each shortcut does', () => {
    expect(hotkeysLine(BOTH)).toBe('Ctrl+Alt+Enter shows or hides Pseudo from any app · Ctrl+Alt+T starts and stops talking');
  });

  it('says which one another program holds, and still names the one that works', () => {
    expect(hotkeysLine(TALK_TAKEN))
      .toBe('Ctrl+Alt+Enter shows or hides Pseudo from any app · Ctrl+Alt+T is held by another program, so it is off here');
  });

  it('a shortcut this page has no words for is still named', () => {
    expect(hotkeysLine([{ id: 'new_one', label: 'Ctrl+Alt+N', ok: true }])).toBe('Ctrl+Alt+N is a Pseudo shortcut');
  });
});

describe('HotkeysNote', () => {
  it('shows nothing until the main process has said which shortcuts it holds', () => {
    expect(renderToStaticMarkup(<HotkeysNote keys={null} />)).toBe('');
    expect(renderToStaticMarkup(<HotkeysNote keys={[]} />)).toBe('');
  });

  it('is one labelled note, marked when a shortcut is off', () => { // M39: Settings' Shortcuts section now
    const fine = renderToStaticMarkup(<HotkeysNote keys={BOTH} />);
    expect(fine).toContain('aria-label="Shortcuts"');
    expect(fine).toContain('data-off="false"');
    const taken = renderToStaticMarkup(<HotkeysNote keys={TALK_TAKEN} />);
    expect(taken).toContain('data-off="true"');
    expect(taken).toContain('Off here: another program holds it');
  });

  it('draws each shortcut as key caps, and says what it does', () => {
    const fine = renderToStaticMarkup(<HotkeysNote keys={BOTH} />);
    expect(fine).toContain('Shows or hides Pseudo from any app');
    expect(fine.match(/<kbd/g)).toHaveLength(8); // Ctrl Alt Enter, Ctrl Alt T, Ctrl Space
  });
});
