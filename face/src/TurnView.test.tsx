// M30: every answer says which brain gave it (TurnView in App.tsx).
// (renderToStaticMarkup turns React output into an HTML string, so no browser is needed.)
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { TurnView } from './App';
import type { Turn } from './state';

const turn = (label?: string): Turn => ({ question: 'Tick the fake box.', steps: [], answer: 'Fake answer.', label, running: false });

describe('TurnView', () => {
  it('badges an answer from the action brain as Claude Code on your subscription', () => {
    const html = renderToStaticMarkup(<TurnView turn={turn('claude-code · claude-sonnet-5-5')} />);
    expect(html).toContain('<span class="brain action">Claude Code · your subscription</span>');
    expect(html).toContain('aria-label="Answer from claude-code · claude-sonnet-5-5"');
  });

  it('badges an answer from the chat provider, live or from a saved session', () => {
    const html = renderToStaticMarkup(<TurnView turn={turn('groq · openai/gpt-oss-120b, fallback')} />);
    expect(html).toContain('<span class="brain chat">Chat provider</span>');
    expect(html).not.toContain('Claude Code');
  });

  it('shows no badge when nobody is named (a session saved before M16)', () => {
    expect(renderToStaticMarkup(<TurnView turn={turn(undefined)} />)).not.toContain('class="brain');
  });

  it('a refused action request shows why, and no badge', () => {
    const refused: Turn = { question: 'Tick the fake box.', steps: [], failed: 'billing check: NOT CLEAN. Nothing was sent', running: false };
    const html = renderToStaticMarkup(<TurnView turn={refused} />);
    expect(html).toContain('No answer: billing check: NOT CLEAN. Nothing was sent');
    expect(html).not.toContain('class="brain');
  });
});
