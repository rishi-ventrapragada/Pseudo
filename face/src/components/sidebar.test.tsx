// M41: the sidebar's chats (from the mockup): date headings, the "…" menu, renaming, the delete confirm, search,
// and the provider picker. Drawn to HTML as in the other render tests; every chat and provider here is fake.
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import type { Provider, SessionItem } from '../protocol';
import { ProviderBar } from '../ProviderBar';
import { ChatRow } from './ChatRow';
import { DeleteChat } from './DeleteChat';
import { ProviderPicker } from './ProviderPicker';
import { SessionList } from './SessionList';
import { whatToList } from './Sidebar';

const NOW = new Date(2026, 9, 10, 9, 30); // Saturday 10 October 2026
const chat = (name: string, title: string): SessionItem => ({ name, provider: 'groq', questions: 1, title });
const TODAY = chat('20261010-090000-000', "What's on my screen?");
const ITEMS = [TODAY, chat('20261009-180000-000', 'Read the booking form'),
               chat('20261005-120000-000', 'Fill in the booking subject'), chat('20260901-080000-000', 'Draft a reply')];
const GROQ: Provider = { id: 'groq', name: 'Groq', models: ['big-model'], leaves_laptop: true, privacy: 'Fake cloud note.',
                         transcribe_model: '', disabled: '' };
const OFF: Provider = { id: 'local', name: 'Private mode', models: ['tiny'], leaves_laptop: false, privacy: 'Fake local note.',
                        transcribe_model: '', disabled: 'fake: removed' };

const list = (items: SessionItem[] | null, noMatch = false) => renderToStaticMarkup(
  <SessionList items={items} current={TODAY.name} disabled={false} noMatch={noMatch} now={NOW}
               onOpen={() => {}} onRename={() => {}} onAskDelete={() => {}} />);
const row = (state: { menuOpen?: boolean; renaming?: boolean; disabled?: boolean }) => renderToStaticMarkup(
  <ChatRow item={ITEMS[1]} open={false} disabled={Boolean(state.disabled)} menuOpen={Boolean(state.menuOpen)}
           renaming={Boolean(state.renaming)} onOpen={() => {}} onMenu={() => {}} onStartRename={() => {}}
           onRename={() => {}} onAskDelete={() => {}} />);

describe('the chats, by day (M41)', () => {
  it('sit under Today, Yesterday, Previous 7 days and Older, in that order', () => {
    const html = list(ITEMS);
    const order = ['>Today<', 'What&#x27;s on my screen?', '>Yesterday<', 'Read the booking form', '>Previous 7 days<',
                   'Fill in the booking subject', '>Older<', 'Draft a reply'].map((text) => html.indexOf(text));
    expect(order.every((at, i) => at > -1 && (i === 0 || at > order[i - 1])), String(order)).toBe(true);
  });

  it('a heading with no chats is left out; no chats at all says so; a search with none says that', () => {
    expect(list([TODAY])).not.toContain('Yesterday');
    expect(list([])).toContain('No saved chats yet. Every question you ask is saved here.');
    const none = list([], true);
    expect(none).toContain('No chats match your search.');
    expect(none).not.toContain('No saved chats yet');
  });
});

describe('a chat’s menu (M41)', () => {
  it('"…" names the chat and opens Rename and Delete, Delete in red', () => {
    const html = row({ menuOpen: true });
    expect(html).toContain('aria-label="Options for “Read the booking form”"');
    expect(html).toContain('aria-expanded="true"');
    expect(html).toMatch(/role="menu"[^>]*aria-label="Chat options"|aria-label="Chat options"[^>]*role="menu"/);
    expect(html).toMatch(/role="menuitem"[^>]*class="[^"]*text-ink[^"]*"[^>]*>.*Rename/);
    expect(html).toMatch(/role="menuitem"[^>]*class="[^"]*text-danger[^"]*"[^>]*>.*Delete/);
  });

  it('closed, it shows no items; while Pseudo is busy, the chat and its menu can’t be used', () => {
    expect(row({})).not.toContain('role="menuitem"');
    const busy = row({ disabled: true });
    expect(busy.match(/<button[^>]*disabled=""/g)).toHaveLength(2);
  });

  it('renaming shows a box with the old name, 60 characters at most, and a save button', () => {
    const html = row({ renaming: true });
    expect(html).toContain('aria-label="New name for this chat"');
    expect(html).toContain('value="Read the booking form"');
    expect(html).toContain('maxLength="60"');
    expect(html).toContain('aria-label="Save the new name"');
    expect(html).not.toContain('Options for');
  });
});

describe('the delete confirm (M41)', () => {
  it('says what goes and what stays, with Cancel before a red Delete', () => {
    const html = renderToStaticMarkup(<DeleteChat item={ITEMS[1]} onCancel={() => {}} onDelete={() => {}} />);
    expect(html).toContain('role="alertdialog"');
    expect(html).toContain('Delete this chat?');
    expect(html).toContain('“Read the booking form” will be removed from this laptop. This can&#x27;t be undone. Saved memories stay.');
    expect(html.indexOf('>Cancel<')).toBeLessThan(html.indexOf('>Delete<'));
    expect(html).toMatch(/class="[^"]*bg-danger-strong[^"]*"[^>]*>Delete</);
  });
});

describe('search (M41)', () => {
  const found = { text: 'booking', items: [ITEMS[1], ITEMS[2]] };
  it('no words: every chat', () => {
    expect(whatToList('  ', ITEMS, found)).toEqual({ items: ITEMS, noMatch: false });
  });
  it('words: the reply; while a newer one is on its way, the one before', () => {
    expect(whatToList('booking', ITEMS, found).items).toEqual([ITEMS[1], ITEMS[2]]);
    expect(whatToList('booking f', ITEMS, found)).toEqual({ items: [ITEMS[1], ITEMS[2]], noMatch: false });
    expect(whatToList('booking', ITEMS, null)).toEqual({ items: null, noMatch: false });
  });
  it('"no match" only when the reply for exactly these words is empty', () => {
    expect(whatToList('zzz', ITEMS, { text: 'zzz', items: [] }).noMatch).toBe(true);
    expect(whatToList('zzzz', ITEMS, { text: 'zzz', items: [] }).noMatch).toBe(false);
  });
});

describe('the provider picker (M41)', () => {
  it('says who answers and opens "Choose a model"; Settings sits beside it', () => {
    const html = renderToStaticMarkup(<ProviderPicker providers={[GROQ, OFF]} current="groq" idle onSwitch={() => {}}
                                                      actionBrain={null} onSettings={() => {}} />);
    expect(html).toContain('aria-label="Questions go to Groq · big-model. Choose a model"');
    expect(html).toContain('aria-haspopup="dialog"');
    expect(html).toContain('aria-label="Settings"');
  });

  it('a switched-off provider is not offered, here or in Settings (both use this list)', () => {
    const html = renderToStaticMarkup(<ProviderBar providers={[GROQ, OFF]} current="groq" disabled={false} onSwitch={() => {}} />);
    expect(html).toContain('Fake cloud note.');
    expect(html).not.toContain('Private mode');
    expect(html).not.toContain('Fake local note.');
  });
});
