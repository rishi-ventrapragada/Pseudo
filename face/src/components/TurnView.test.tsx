// M18 and M30, since M40: an answer carries no "who answered" label (D28); who answered is in its steps, one
// click away; while it runs, the working word or the approval line. (renderToStaticMarkup: no browser needed.)
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import type { Turn } from '../state';
import { APPROVAL } from './Activity';
import { TurnView } from './TurnView';

const turn = (label?: string): Turn => ({ question: 'Tick the fake box.', answer: 'Fake answer.', label, running: false,
  steps: label ? [{ label: 'Answered', detail: label }] : [] });
const RUNNING: Turn = { question: 'Tick the fake box.', steps: [{ label: 'Sent to Claude Code, as an action request' }], running: true, askedAt: 0 };

describe('TurnView', () => {
  it('an answer shows no provider or brain, from Claude Code or the chat provider', () => {
    for (const label of ['claude-code · claude-sonnet-5-5', 'groq · openai/gpt-oss-120b, fallback']) {
      const html = renderToStaticMarkup(<TurnView turn={turn(label)} />);
      expect(html).toContain('aria-label="Pseudo&#x27;s answer"'); // React writes the apostrophe as &#x27;
      const answer = html.slice(html.indexOf('<article'), html.indexOf('</article>'));
      expect(answer).not.toMatch(/groq|claude|Claude Code|Chat provider/);
      expect(html).toContain('1 step: what Pseudo did'); // who answered is one click away
    }
  });

  it('a refused action request shows why', () => {
    const refused: Turn = { question: 'Tick the fake box.', steps: [], failed: 'billing check: NOT CLEAN. Nothing was sent', running: false };
    expect(renderToStaticMarkup(<TurnView turn={refused} />)).toContain('No answer: billing check: NOT CLEAN. Nothing was sent');
  });

  it('the question, the answer, and the steps one click away', () => {
    const html = renderToStaticMarkup(<TurnView turn={{ ...turn(), steps: [{ label: 'Read the window you were on' }, { label: 'Answered', detail: 'groq · big' }] }} />);
    expect(html).toContain('Tick the fake box.');
    expect(html).toContain('Fake answer.');
    expect(html).toContain('2 steps: what Pseudo did');
    expect(html).toContain('aria-expanded="false"');
    expect(html).not.toContain('Read the window you were on'); // closed until clicked
  });

  it('while it runs: the working word; while a popup tool runs: the approval line instead, never both', () => {
    const working = renderToStaticMarkup(<TurnView turn={RUNNING} waiting={{ name: 'read_active_window', asks: false }} />);
    expect(working).toContain('aria-label="Pseudo is working. Show what it has done so far."');
    expect(working).not.toContain(APPROVAL);
    const waiting = renderToStaticMarkup(<TurnView turn={RUNNING} waiting={{ name: 'act_on_control', asks: true }} />);
    expect(waiting).toContain(APPROVAL);
    expect(waiting).toContain('role="status"');
    expect(waiting).not.toContain('Pseudo is working');
  });

  it("an earlier, finished turn never shows the wait, even while the latest one waits", () => {
    expect(renderToStaticMarkup(<TurnView turn={turn('groq · big')} waiting={{ name: 'focus_window', asks: true }} />))
      .not.toContain(APPROVAL);
  });
});
