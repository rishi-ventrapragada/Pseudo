// M40: the working line and the approval line (Activity.tsx), the greeting with suggestions (Conversation.tsx),
// and nothing under the question box (BottomArea.tsx). All states are fake.
import { createRef } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { ApprovalLine, APPROVAL, WORDS, WorkingLine } from './Activity';
import { BottomArea } from './BottomArea';
import { Conversation } from './Conversation';

const SUGGESTIONS = ["What's on my screen?", 'Summarise the window I was on', 'Which buttons are on this window?',
                     'What did I work on yesterday?'];
const empty = (canAsk: boolean, suggestions = SUGGESTIONS) => renderToStaticMarkup(
  <Conversation phase="ready" turns={[]} session="s" end={createRef<HTMLDivElement>()} waiting={null}
                suggestions={suggestions} canAsk={canAsk} onAsk={() => {}} />);

describe('the working line', () => {
  it('a playful word from Pseudo\'s own list, a timer, and steps; screen readers hear one plain label', () => {
    const html = renderToStaticMarkup(<WorkingLine askedAt={Date.now()} open={false} onToggle={() => {}} />);
    expect(html).toContain('aria-label="Pseudo is working. Show what it has done so far."');
    expect(html).toContain(`${WORDS[0]}…`);
    expect(html).toMatch(/aria-hidden="true"[^>]*>0s</);
    expect(html).toContain('aria-expanded="false"');
  });

  it('only pulses when motion is allowed', () => {
    expect(renderToStaticMarkup(<WorkingLine open={false} onToggle={() => {}} />)).toContain('motion-safe:animate-pulse');
  });
});

describe('the approval line', () => {
  it('says it plainly, in amber, announced once', () => {
    const html = renderToStaticMarkup(<ApprovalLine open={false} onToggle={() => {}} />);
    expect(html).toMatch(/^<div role="status"/);
    expect(html).toContain(APPROVAL);
    expect(html).toContain('Cancel, or no answer within 20 seconds, means no.');
    expect(html).toContain('text-wait');
    expect(html).toContain('>Show steps</button>');
  });
});

describe('an empty chat', () => {
  it('greets you and offers the suggestions as buttons', () => {
    const html = empty(true);
    expect(html).toContain('What can I help with?');
    expect(html).toContain('I read the window you were on before this one.');
    for (const text of SUGGESTIONS) expect(html).toContain(text.replace("'", '&#x27;'));
    expect(html.match(/<button type="button"/g)).toHaveLength(4);
    expect(html).not.toContain('disabled=""');
  });

  it('suggestions wait while Pseudo is busy, and an older brain without them shows the greeting alone', () => {
    expect(empty(false).match(/disabled=""/g)).toHaveLength(4);
    const none = empty(true, []);
    expect(none).toContain('What can I help with?');
    expect(none).not.toContain('<button');
  });
});

describe('under the question box', () => {
  it('there is nothing: no privacy text, no footnote (D28)', () => {
    const html = renderToStaticMarkup(<BottomArea notice="" stopped={false} onRestart={() => {}} composer={<form id="box" />} />);
    expect(html.endsWith('<form id="box"></form></div></div>')).toBe(true);
    expect(html).not.toMatch(/Leaves this laptop|Stays on this laptop|privacy/i);
  });

  it('the notice line sits above the box, and is empty when there is nothing to say', () => {
    const html = renderToStaticMarkup(<BottomArea notice="Switched to local." stopped={false} onRestart={() => {}} composer={<form />} />);
    expect(html.indexOf('Switched to local.')).toBeLessThan(html.indexOf('<form'));
    expect(renderToStaticMarkup(<BottomArea notice="" stopped={false} onRestart={() => {}} composer={<form />} />))
      .toMatch(/<p aria-live="polite"[^>]*><\/p>/);
  });
});
