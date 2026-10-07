// M38: the question box (Composer.tsx), moved out of App.tsx unchanged. All drafts are fake.
import { createRef } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { asksOnKey, Composer } from './Composer';

const key = (over: object) => ({ key: 'Enter', shiftKey: false, ctrlKey: false, altKey: false, ...over });
const show = (draft: string, canAsk: boolean) => renderToStaticMarkup(
  <Composer draft={draft} setDraft={() => {}} canAsk={canAsk} onAsk={() => {}} box={createRef<HTMLTextAreaElement>()} />);

describe('asksOnKey', () => {
  it('Enter asks; Shift+Enter is a new line', () => {
    expect(asksOnKey(key({}))).toBe(true);
    expect(asksOnKey(key({ shiftKey: true }))).toBe(false);
    expect(asksOnKey(key({ key: 'a' }))).toBe(false);
  });

  it('M37: never with Ctrl or Alt held, so Ctrl+Alt+Enter can not send a draft', () => {
    expect(asksOnKey(key({ ctrlKey: true, altKey: true }))).toBe(false);
    expect(asksOnKey(key({ ctrlKey: true }))).toBe(false);
    expect(asksOnKey(key({ altKey: true }))).toBe(false);
  });
});

describe('Composer', () => {
  it('is the labelled question box and an Ask button', () => {
    const page = show('what is on my screen?', true);
    expect(page).toContain('aria-label="Your question"');
    expect(page).toContain('what is on my screen?');
    expect(page).toContain('<button type="submit">Ask</button>');
  });

  it('Ask is off while Pseudo is busy, and for an empty draft', () => {
    expect(show('a question', false)).toContain('<button type="submit" disabled="">Ask</button>');
    expect(show('   ', true)).toContain('<button type="submit" disabled="">Ask</button>');
  });
});
