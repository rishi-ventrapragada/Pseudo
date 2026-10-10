// M38's C4, as a render test since M39: the compact bar must always show the approval banner, the status line,
// the steps, the answer, a failure, the Restart block and the mic. (It replaces compact-css.test.mjs, which read
// the CSS that used to hide parts of the full page.) All states are fake.
import { createRef } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { BANNER_TEXT } from '../ApprovalBanner';
import { Composer } from '../Composer';
import type { Turn } from '../state';
import type { Compact } from '../useCompact';
import type { Voice } from '../useVoice';
import { CompactBar } from './CompactBar';
import { MicButton } from './MicButton';

const voice: Voice = { listening: false, seconds: 0, speaking: false, speakOn: false, problem: '', toggle() {},
                       setSpeakOn() {}, stopSpeaking() {} };
const bar = (over: Partial<Compact> = {}): Compact => ({ on: true, grown: false, setOn() {}, open() {}, close() {}, ...over });
const ANSWERED: Turn = { question: 'What is on the fake form?', steps: ['Read the window'], answer: 'A fake form.', running: false };
const FAILED: Turn = { question: 'Tick the fake box.', steps: [], failed: 'billing check: NOT CLEAN', running: false };

function show(over: { compact?: Compact; waiting?: string | null; stopped?: boolean; latest?: Turn } = {}) {
  const composer = <Composer draft="" setDraft={() => {}} canAsk onAsk={() => {}} box={createRef<HTMLTextAreaElement>()} row
                             mic={<MicButton voice={voice} canTalk why="" />} />;
  return renderToStaticMarkup(
    <CompactBar compact={over.compact ?? bar()} status="Ready. Pseudo reads the window you were on before this one."
                working={false} waiting={over.waiting ?? null} stopped={over.stopped ?? false} latest={over.latest}
                onRestart={() => {}} composer={composer} />);
}

describe('the compact bar (C4)', () => {
  it('small: the status line, the mic, the question box, Ask and Full window', () => {
    const html = show();
    expect(html).toContain('Ready. Pseudo reads the window');
    expect(html).toContain('aria-label="Start talking"');
    expect(html).toContain('aria-label="Your question"');
    expect(html).toContain('aria-label="Ask"');
    expect(html).toContain('aria-label="Full window"');
    expect(html).not.toContain('aria-label="Conversation"'); // no room for the turn until it grows
  });

  it('the approval banner shows whenever a tool waits, grown or not', () => {
    expect(show({ waiting: 'focus_window' })).toContain(BANNER_TEXT);
    expect(show({ waiting: 'focus_window', compact: bar({ grown: true }), latest: ANSWERED })).toContain(BANNER_TEXT);
  });

  it('grown: Hide answer, the question, the answer and its steps', () => {
    const html = show({ compact: bar({ grown: true }), latest: ANSWERED });
    for (const part of ['Hide answer', 'What is on the fake form?', 'A fake form.', '1 step: what Pseudo did']) {
      expect(html).toContain(part);
    }
  });

  it('grown: a failure is shown', () => {
    expect(show({ compact: bar({ grown: true }), latest: FAILED })).toContain('No answer: billing check: NOT CLEAN');
  });

  it('a stopped brain: Restart, and Full window is still there', () => {
    const html = show({ compact: bar({ grown: true }), stopped: true });
    expect(html).toContain('Restart the brain');
    expect(html).toContain('aria-label="Full window"');
    expect(html).not.toContain('aria-label="Your question"');
  });
});
