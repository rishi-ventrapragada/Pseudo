// M38's C4, as a render test since M39: the compact bar must always show what Pseudo is doing (M40: the approval
// line, or the working word), the steps, the answer, a failure, the Restart block and the mic. (It replaced
// compact-css.test.mjs, which read the CSS that used to hide parts of the full page.) All states are fake.
import { createRef } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { Composer } from '../Composer';
import type { Turn, Waiting } from '../state';
import type { Compact } from '../useCompact';
import type { Voice } from '../useVoice';
import { APPROVAL } from './Activity';
import { CompactBar } from './CompactBar';
import { MicButton } from './MicButton';

const voice: Voice = { listening: false, seconds: 0, speaking: false, speakOn: false, problem: '', toggle() {},
                       setSpeakOn() {}, stopSpeaking() {} };
const bar = (over: Partial<Compact> = {}): Compact => ({ on: true, grown: false, setOn() {}, open() {}, close() {}, ...over });
const ANSWERED: Turn = { question: 'What is on the fake form?', steps: [{ label: 'Read the window you were on' }], answer: 'A fake form.', running: false };
const FAILED: Turn = { question: 'Tick the fake box.', steps: [], failed: 'billing check: NOT CLEAN', running: false };
const RUNNING: Turn = { question: 'Tick the fake box.', steps: [{ label: 'Asked to tick or untick a box' }], running: true, askedAt: 0 };
const ASKS: Waiting = { name: 'act_on_control', asks: true };

function show(over: { compact?: Compact; waiting?: Waiting | null; stopped?: boolean; latest?: Turn; notice?: string } = {}) {
  const composer = <Composer draft="" setDraft={() => {}} canAsk onAsk={() => {}} box={createRef<HTMLTextAreaElement>()} row
                             mic={<MicButton voice={voice} canTalk why="" />} />;
  return renderToStaticMarkup(
    <CompactBar compact={over.compact ?? bar()} notice={over.notice ?? ''} waiting={over.waiting ?? null}
                stopped={over.stopped ?? false} latest={over.latest} onRestart={() => {}} composer={composer} />);
}

describe('the compact bar (C4)', () => {
  it('small: what Pseudo is doing, the mic, the question box, Ask and Full window', () => {
    const html = show({ notice: 'Switched to groq.' });
    expect(html).toContain('Switched to groq.');
    expect(show()).toContain('>Ready</p>');
    expect(html).toContain('aria-label="Start talking"');
    expect(html).toContain('aria-label="Your question"');
    expect(html).toContain('aria-label="Ask"');
    expect(html).toContain('aria-label="Full window"');
    expect(html).not.toContain('aria-label="Conversation"'); // no room for the turn until it grows
  });

  it('M40: the approval line shows whenever a popup tool runs, grown or not, and no playful word with it', () => {
    const small = show({ waiting: ASKS, latest: RUNNING });
    expect(small).toContain(APPROVAL);
    expect(small).not.toContain('Pseudo is working');
    expect(show({ waiting: ASKS, compact: bar({ grown: true }), latest: RUNNING }).split(APPROVAL)).toHaveLength(3); // top row and turn
  });

  it('M40: a reading tool shows the working word, never the approval line', () => {
    const html = show({ waiting: { name: 'read_active_window', asks: false }, latest: RUNNING });
    expect(html).toContain('aria-label="Pseudo is working"');
    expect(html).not.toContain(APPROVAL);
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
