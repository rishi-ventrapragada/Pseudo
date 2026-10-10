// M30: every answer says which brain gave it (TurnView). M39 moved it to components/ and restyled it;
// the checks are the same. (renderToStaticMarkup turns React output into an HTML string, so no browser is needed.)
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import type { Turn } from '../state';
import { TurnView } from './TurnView';

const turn = (label?: string): Turn => ({ question: 'Tick the fake box.', steps: [], answer: 'Fake answer.', label, running: false });

describe('TurnView', () => {
  it('badges an answer from the action brain as Claude Code on your subscription', () => {
    const html = renderToStaticMarkup(<TurnView turn={turn('claude-code · claude-sonnet-5-5')} />);
    expect(html).toMatch(/data-brain="action"[^>]*>Claude Code · your subscription</);
    expect(html).toContain('aria-label="Answer from claude-code · claude-sonnet-5-5"');
  });

  it('badges an answer from the chat provider, live or from a saved session', () => {
    const html = renderToStaticMarkup(<TurnView turn={turn('groq · openai/gpt-oss-120b, fallback')} />);
    expect(html).toMatch(/data-brain="chat"[^>]*>Chat provider</);
    expect(html).not.toContain('Claude Code');
  });

  it('shows no badge when nobody is named (a session saved before M16)', () => {
    expect(renderToStaticMarkup(<TurnView turn={turn(undefined)} />)).not.toContain('data-brain');
  });

  it('a refused action request shows why, and no badge', () => {
    const refused: Turn = { question: 'Tick the fake box.', steps: [], failed: 'billing check: NOT CLEAN. Nothing was sent', running: false };
    const html = renderToStaticMarkup(<TurnView turn={refused} />);
    expect(html).toContain('No answer: billing check: NOT CLEAN. Nothing was sent');
    expect(html).not.toContain('data-brain');
  });

  it('the question, the answer, and the steps one click away', () => {
    const html = renderToStaticMarkup(<TurnView turn={{ ...turn(), steps: ['Read the window', 'Answered'] }} />);
    expect(html).toContain('Tick the fake box.');
    expect(html).toContain('Fake answer.');
    expect(html).toContain('2 steps: what Pseudo did');
    expect(html).toContain('aria-expanded="false"');
  });
});
