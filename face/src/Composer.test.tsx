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

// M39: Ask is a round icon button now, named by its label; the checks are the same.
const askButton = (page: string) => page.match(/<button type="submit"[^>]*>/)?.[0] ?? '';

describe('Composer', () => {
  it('is the labelled question box and an Ask button', () => {
    const page = show('what is on my screen?', true);
    expect(page).toContain('aria-label="Your question"');
    expect(page).toContain('what is on my screen?');
    expect(askButton(page)).toContain('aria-label="Ask"');
    expect(askButton(page)).not.toContain('disabled=""'); // the attribute; Tailwind's class names say "disabled:" too
  });

  it('Ask is off while Pseudo is busy, and for an empty draft', () => {
    expect(askButton(show('a question', false))).toContain('disabled=""');
    expect(askButton(show('   ', true))).toContain('disabled=""');
  });

  it('the compact bar gets the same box and button on one line', () => {
    const row = renderToStaticMarkup(<Composer draft="x" setDraft={() => {}} canAsk onAsk={() => {}} row
                                               box={createRef<HTMLTextAreaElement>()} />);
    expect(row).toContain('rows="1"');
    expect(askButton(row)).toContain('aria-label="Ask"');
  });
});
