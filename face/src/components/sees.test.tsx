// M42: the look-at chip, Chats or Memory, the memory browser and the Status panel (from the mockup), drawn to HTML
// as in the other render tests. Every app, memory and number here is fake.
import { createRef } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { Composer } from '../Composer';
import type { Warm } from '../protocol';
import type { Memory, Totals } from '../sees';
import { LookingAtChip } from './LookingAtChip';
import { INTRO, MemoryView, READ_ONLY } from './MemoryView';
import { PanelSwitch } from './PanelSwitch';
import { short, StatusPanel, warmText } from './StatusPanel';

const html = renderToStaticMarkup;
const NOTE = { name: '2026-10-07-101500-123.md', date: '2026-10-07', title: 'Read the booking form',
               question: 'Read the booking form', answer: 'Booked by [PERSON] for **Thursday**.', note: '' };
const LIST: Memory = { items: [{ name: NOTE.name, date: NOTE.date, title: NOTE.title },
                               { name: '2026-09-30-080000-000.md', date: '2026-09-30', title: 'Summarise the release notes' }],
                       note: '', open: null, stale: false };
const view = (memory: Memory, disabled = false) =>
  html(<MemoryView memory={memory} disabled={disabled} notice="" onOpen={() => {}} onClose={() => {}} />);
const status = (totals: Partial<Totals>, warm: Warm | null = null, now = 10_000) =>
  html(<StatusPanel totals={{ tokens: 0, masked: 0, budget: null, ...totals }} warm={warm} now={now} />);

describe('the look-at chip (M42)', () => {
  it("names the app, with the mockup's tooltip", () => {
    const chip = html(<LookingAtChip looking={{ app: 'Brave Browser', private: false }} />);
    expect(chip).toContain('Looking at <span class="font-medium text-ink">Brave Browser</span>');
    expect(chip).toContain('title="The window Pseudo will read when you ask"');
  });

  it('says "a private app" for a blocked app, and nothing at all when there is no app', () => {
    expect(html(<LookingAtChip looking={{ app: '', private: true }} />)).toContain('a private app');
    expect(html(<LookingAtChip looking={null} />)).toBe('');
  });

  it('sits in the question box, above where you type', () => {
    const box = html(<Composer draft="" setDraft={() => {}} canAsk onAsk={() => {}} box={createRef<HTMLTextAreaElement>()}
                               chips={<LookingAtChip looking={{ app: 'Fake Notes', private: false }} />} />);
    expect(box.indexOf('Looking at')).toBeGreaterThan(-1);
    expect(box.indexOf('Looking at')).toBeLessThan(box.indexOf('<textarea'));
  });

  it('M43: the short form shows the name only, and screen readers still hear "Looking at"', () => {
    const chip = html(<LookingAtChip looking={{ app: 'Brave Browser', private: false }} short />);
    expect(chip).toContain('<span class="sr-only">Looking at </span><span class="text-ink">Brave Browser</span>');
    expect(chip).toContain('title="Looking at Brave Browser: the window Pseudo will read when you ask"');
    expect(chip).toContain('truncate'); // a long name is cut short
    expect(html(<LookingAtChip looking={{ app: '', private: true }} short />)).toContain('>a private app</span>');
    expect(html(<LookingAtChip looking={null} short />)).toBe('');
  });

  it("M43: in the compact bar's row it sits between the mic and where you type", () => {
    const row = html(<Composer draft="" setDraft={() => {}} canAsk onAsk={() => {}} box={createRef<HTMLTextAreaElement>()} row
                               mic={<button type="button" aria-label="Start talking" />}
                               chips={<LookingAtChip looking={{ app: 'Fake Notes', private: false }} short />} />);
    const [mic, chip, text] = ['Start talking', 'Fake Notes', '<textarea'].map((part) => row.indexOf(part));
    expect(mic).toBeGreaterThan(-1);
    expect(mic < chip && chip < text).toBe(true);
    expect(row).toContain('placeholder="Ask about this window"');
  });
});

describe('Chats or Memory (M42)', () => {
  it('marks the chosen one, and Memory shows how many there are once listed', () => {
    const chats = html(<PanelSwitch panel="chats" count={4} onChange={() => {}} />);
    expect(chats).toMatch(/aria-pressed="true"[^>]*>.*Chats/);
    expect(chats).toContain('>4</span>');
    expect(html(<PanelSwitch panel="memory" count={null} onChange={() => {}} />)).not.toMatch(/font-mono/);
  });
});

describe('the memory browser (M42)', () => {
  it('lists the memories newest first, with their dates, under the intro', () => {
    const list = view(LIST);
    expect(list).toContain('>Memory</h1>');
    expect(list).toContain(INTRO);
    expect(list.indexOf('Read the booking form')).toBeLessThan(list.indexOf('Summarise the release notes'));
    expect(list).toContain('>2026-10-07</span>');
  });

  it('shows a mask in a title as a chip, as answers do', () => {
    const masked = view({ ...LIST, items: [{ name: NOTE.name, date: NOTE.date, title: 'Call [PERSON] about the notes' }] });
    expect(masked).toContain('title="Masked on this laptop: [PERSON]">name</span>');
  });

  it('says why there are none, and that it is still listing before the first reply', () => {
    expect(view({ ...LIST, items: [], note: 'there is no memory folder yet' })).toContain('there is no memory folder yet');
    expect(view({ ...LIST, items: null })).toContain('Listing your memories');
  });

  it('can’t open a memory while Pseudo is busy', () => {
    expect(view(LIST, true).match(/<button[^>]*disabled/g)).toHaveLength(2);
  });

  it('opens one read-only: its date, question and answer, with masks as chips, and the way back', () => {
    const note = view({ ...LIST, open: NOTE });
    expect(note).toContain('2026-10-07 · saved with your approval');
    expect(note).toContain('title="Masked on this laptop: [PERSON]">name</span>');
    expect(note).toContain('<strong>Thursday</strong>');
    expect(note).toContain('All memories');
    expect(note).toContain(READ_ONLY);
  });

  it('a memory that can’t be opened says why, and shows nothing else', () => {
    const refused = view({ ...LIST, open: { ...NOTE, question: '', answer: '', note: 'that memory can’t be opened' } });
    expect(refused).toContain('that memory can’t be opened');
    expect(refused).not.toContain('<article');
  });
});

describe('the Status panel (M42)', () => {
  it('is open by default and shows the four numbers', () => {
    const panel = status({ tokens: 4812, masked: 9, budget: { left: 6200, limit: 8000, at: 9000 } },
                         { on: true, open: true, ram_mb: 312, asked: 1, of: 6, idle_minutes: 0, note: '' });
    for (const text of ['Status', 'Tokens this chat', '4,812', 'Groq budget this minute', '6.2K / 8K', 'Warm Claude Code',
                        '312 MB, open', 'Masked before sending', '9 items']) {
      expect(panel).toContain(text);
    }
    expect(panel).toContain('aria-expanded="true"');
    expect(panel).toMatch(/<progress aria-hidden="true" value="6200" max="8000"/);
  });

  it("shows Groq's full budget a minute after the last answer, and a dash before the first", () => {
    expect(status({ budget: { left: 6200, limit: 8000, at: 0 } }, null, 60_000)).toContain('8K / 8K');
    const unknown = status({});
    expect(unknown).toContain('>–</dd>');
    expect(unknown).not.toContain('<progress');
  });

  it('says the warm session as it is, and one item in the singular', () => {
    const warm = (on: boolean, open: boolean): Warm => ({ on, open, ram_mb: 250, asked: 0, of: 6, idle_minutes: 0, note: '' });
    expect([warmText(null), warmText(warm(false, false)), warmText(warm(true, false)), warmText(warm(true, true))])
      .toEqual(['off', 'off', 'on, none open', '250 MB, open']);
    expect(status({ masked: 1 })).toContain('1 item<');
  });

  it('shortens thousands', () => {
    expect([short(950), short(6200), short(8000), short(12_345)]).toEqual(['950', '6.2K', '8K', '12.3K']);
  });
});
