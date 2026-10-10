// M38's C4, as a render test since M39: the compact bar must always show what Pseudo is doing (M40: the approval
// line, or the working word), the steps, the answer, a failure, the Restart block and the mic. (It replaced
// compact-css.test.mjs, which read the CSS that used to hide parts of the full page.) All states are fake.
// M43: the mockup's bar: "Pseudo" and a note in the top row with Full window; the look-at chip in the question row;
// grown, the question on one line with Hide answer, then the word, the amber box, or the answer and its steps.
import { createRef } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { Composer } from '../Composer';
import type { Turn, Waiting } from '../state';
import type { Compact } from '../useCompact';
import type { Voice } from '../useVoice';
import { APPROVAL, BAR_NOTE } from './Activity';
import { BAR_APPROVAL_NOTE } from './BarTurn';
import { CompactBar } from './CompactBar';
import { LookingAtChip } from './LookingAtChip';
import { MicButton } from './MicButton';

const voice: Voice = { listening: false, seconds: 0, speaking: false, speakOn: false, problem: '', toggle() {},
                       setSpeakOn() {}, stopSpeaking() {} };
const bar = (over: Partial<Compact> = {}): Compact => ({ on: true, grown: false, setOn() {}, open() {}, close() {}, ...over });
const GROWN = bar({ grown: true });
const ANSWERED: Turn = { question: 'What is on the fake form?', steps: [{ label: 'Read the window you were on' }], answer: 'A fake form.', running: false };
const FAILED: Turn = { question: 'Tick the fake box.', steps: [], failed: 'billing check: NOT CLEAN', running: false };
const RUNNING: Turn = { question: 'Tick the fake box.', steps: [{ label: 'Asked to tick or untick a box' }], running: true, askedAt: 0 };
const ASKS: Waiting = { name: 'act_on_control', asks: true };
const READS: Waiting = { name: 'read_active_window', asks: false };

function show(over: { compact?: Compact; waiting?: Waiting | null; stopped?: boolean; latest?: Turn; notice?: string } = {}) {
  const composer = <Composer draft="" setDraft={() => {}} canAsk onAsk={() => {}} box={createRef<HTMLTextAreaElement>()} row
                             mic={<MicButton voice={voice} canTalk why="" />}
                             chips={<LookingAtChip looking={{ app: 'Fake Notes', private: false }} short />} />;
  return renderToStaticMarkup(
    <CompactBar compact={over.compact ?? bar()} notice={over.notice ?? ''} waiting={over.waiting ?? null}
                stopped={over.stopped ?? false} latest={over.latest} onRestart={() => {}} composer={composer} />);
}
const count = (html: string, part: string) => html.split(part).length - 1;

describe('the compact bar (C4)', () => {
  it('small: the top row (Pseudo, the note, Full window), then the mic, the chip, the question box and Ask', () => {
    const html = show();
    const order = ['>Pseudo</span>', `>${BAR_NOTE.onTop}</p>`, 'aria-label="Full window"', 'aria-label="Start talking"',
                   '>Fake Notes</span>', 'aria-label="Your question"', 'aria-label="Ask"'].map((part) => html.indexOf(part));
    expect(order.every((at) => at > -1), JSON.stringify(order)).toBe(true);
    expect([...order].sort((a, b) => a - b)).toEqual(order);
    expect(html).toContain('h-[30px]'); // the top row is as tall as the title bar's buttons (window-look.js)
    expect(html).not.toContain('aria-label="Conversation"'); // no room for the turn until it grows
    expect(show({ notice: 'Switched to groq.' })).toContain('>Switched to groq.</p>');
  });

  it('M40: the approval line shows whenever a popup tool runs, grown or not, and no playful word with it', () => {
    const small = show({ waiting: ASKS, latest: RUNNING });
    expect(small).toContain(APPROVAL);
    expect(small).not.toContain('Pseudo is working');
    const grown = show({ waiting: ASKS, compact: GROWN, latest: RUNNING });
    expect(count(grown, APPROVAL)).toBe(1); // the amber box in the turn; the top row says why the bar stepped down
    expect(grown).toContain(BAR_APPROVAL_NOTE);
    expect(grown).toContain(`>${BAR_NOTE.steppedDown}</p>`);
    expect(grown).not.toContain('Pseudo is working');
  });

  it('M40: a reading tool shows the working word, never the approval line: in the top row small, in the turn grown', () => {
    const small = show({ waiting: READS, latest: RUNNING });
    expect(small).toContain('aria-label="Pseudo is working"');
    expect(small).not.toContain(APPROVAL);
    const grown = show({ waiting: READS, compact: GROWN, latest: RUNNING });
    expect(count(grown, 'aria-label="Pseudo is working')).toBe(1); // the turn's working line, with its steps
    expect(grown).not.toContain(APPROVAL);
    expect(grown).not.toContain(BAR_NOTE.onTop); // not claimed while a tool may be running
  });

  it('grown: the question on one line with Hide answer, the answer and its steps, above the question box', () => {
    const html = show({ compact: GROWN, latest: ANSWERED });
    const order = ['aria-label="Conversation"', 'What is on the fake form?', 'Hide answer', 'A fake form.',
                   '1 step: what Pseudo did', 'aria-label="Your question"'].map((part) => html.indexOf(part));
    expect(order.every((at) => at > -1), JSON.stringify(order)).toBe(true);
    expect([...order].sort((a, b) => a - b)).toEqual(order);
    expect(html).toContain('title="What is on the fake form?"'); // the whole question, if it is cut short
  });

  it('grown: a failure is shown', () => {
    expect(show({ compact: GROWN, latest: FAILED })).toContain('No answer: billing check: NOT CLEAN');
  });

  it('a stopped brain: Restart, and Full window is still there', () => {
    const html = show({ compact: GROWN, stopped: true });
    expect(html).toContain('Restart the brain');
    expect(html).toContain('aria-label="Full window"');
    expect(html).not.toContain('aria-label="Your question"');
  });
});
