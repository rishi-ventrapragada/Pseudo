// M38, C4: compact mode works by HIDING parts of the page (src/compact.css). These tests read that file and
// check it can never hide what must stay visible in the bar: the approval banner, the status line, the steps,
// the answer, a failure, the Restart block and the mic button. (Here, not in src/: the page's tests can't read files.)
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

const css = readFileSync(new URL('./src/compact.css', import.meta.url), 'utf8').replace(/\/\*[\s\S]*?\*\//g, '');
// every rule as [selectors, declarations]
const rules = [...css.matchAll(/([^{}]+)\{([^{}]*)\}/g)].map((match) => [match[1].trim(), match[2]]);
const hiding = rules.filter(([, body]) => /display:\s*none/.test(body)).map(([selectors]) => selectors);

describe('what compact.css hides', () => {
  it('found the rules', () => {
    expect(rules.length).toBeGreaterThan(8);
    expect(hiding.length).toBe(2);
  });

  it('only inside compact mode: the full window loses nothing', () => {
    for (const selectors of hiding) {
      for (const selector of selectors.split(',')) expect(selector.trim(), selector).toMatch(/^\.app\.compact/);
    }
  });

  it('never the approval banner, the status line, the steps, the answer, a failure, Restart or the mic', () => {
    for (const kept of ['.approval-banner', '.status', '.steps', '.answer', '.failed', '.stopped', '.turn', '.mic', 'form', 'textarea']) {
      for (const selectors of hiding) expect(selectors, kept).not.toContain(kept);
    }
  });

  it('the conversation is hidden only while the bar is NOT grown', () => {
    expect(hiding).toContain('.app.compact:not(.grown) .transcript');
  });
});
