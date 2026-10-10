// M39: every button has a name a screen reader can say. An icon-only button (the mic, Ask, the sidebar button,
// Compact bar) has no words inside, so it needs an aria-label. All states are fake.
import { createRef } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { Composer } from '../Composer';
import type { Compact } from '../useCompact';
import type { Voice } from '../useVoice';
import { ChatRow } from './ChatRow';
import { CompactBar } from './CompactBar';
import { Conversation } from './Conversation';
import { DeleteChat } from './DeleteChat';
import { LookingAtChip } from './LookingAtChip';
import { MemoryView } from './MemoryView';
import { ListeningChip, MicButton } from './MicButton';
import { ProviderPicker } from './ProviderPicker';
import { Sidebar } from './Sidebar';
import { StatusPanel } from './StatusPanel';
import { TopBar } from './TopBar';

const voice: Voice = { listening: true, seconds: 3, speaking: true, speakOn: true, problem: '', toggle() {},
                       setSpeakOn() {}, stopSpeaking() {} };
const compact: Compact = { on: false, grown: false, setOn() {}, open() {}, close() {} };
const composer = <Composer draft="" setDraft={() => {}} canAsk onAsk={() => {}} box={createRef<HTMLTextAreaElement>()}
                           mic={<MicButton voice={voice} canTalk why="" />}
                           chips={<><LookingAtChip looking={{ app: 'Fake Notes', private: false }} /><ListeningChip voice={voice} /></>} />;
const MEMORY = { items: [{ name: '2026-10-07-101500-123.md', date: '2026-10-07', title: 'A fake memory' },
                         { name: '2026-10-06-101500-123.md', date: '2026-10-06', title: 'Another one' }],
                 note: '', open: null, stale: false };
const NOTE = { name: '2026-10-07-101500-123.md', date: '2026-10-07', title: 'A fake memory', question: 'A fake question?',
               answer: 'A fake answer about [PERSON].', note: '' };
const ITEMS = [{ name: '20261010-101500-001', provider: 'groq', questions: 1, title: 'A fake chat' }];
const PROVIDERS = [{ id: 'groq', name: 'Groq', models: ['big'], leaves_laptop: true, privacy: 'Fake note.', transcribe_model: '' }];
const picker = <ProviderPicker providers={PROVIDERS} current="groq" idle onSwitch={() => {}} actionBrain={null} onSettings={() => {}} />;
const row = (state: { menuOpen?: boolean; renaming?: boolean }) => (
  <ChatRow item={ITEMS[0]} open={false} disabled={false} menuOpen={Boolean(state.menuOpen)} renaming={Boolean(state.renaming)}
           onOpen={() => {}} onMenu={() => {}} onStartRename={() => {}} onRename={() => {}} onAskDelete={() => {}} />);

/** Each <button ...>inside</button>: its opening tag and the words inside it, tags removed. */
function buttons(html: string): { tag: string; words: string }[] {
  return [...html.matchAll(/(<button[^>]*>)([\s\S]*?)<\/button>/g)]
    .map((match) => ({ tag: match[1], words: match[2].replace(/<[^>]+>/g, '').trim() }));
}

describe('every button has a name', () => {
  const pages = {
    sidebar: <Sidebar onHide={() => {}} onNewChat={() => {}} idle sessions={ITEMS} found={null} current="" onOpen={() => {}}
                      onSearch={() => {}} onRename={() => {}} onDelete={() => {}} picker={picker} panel="chats"
                      onPanel={() => {}} memoryCount={2} status={<StatusPanel totals={{ tokens: 9, masked: 1, budget: null }}
                                                                         warm={null} now={0} />} />,
    'the memory list (M42)': <MemoryView memory={MEMORY} disabled={false} notice="" onOpen={() => {}} onClose={() => {}} />,
    'an open memory, and the Status panel (M42)': (
      <>
        <MemoryView memory={{ ...MEMORY, open: NOTE }} disabled={false} notice="" onOpen={() => {}} onClose={() => {}} />
        <StatusPanel totals={{ tokens: 0, masked: 0, budget: null }} warm={null} now={0} />
      </>
    ),
    'a chat with its menu open (M41)': <>{row({ menuOpen: true })}{row({})}</>,
    'a chat being renamed (M41)': <>{row({ renaming: true })}{row({})}</>,
    'the delete confirm (M41)': <DeleteChat item={ITEMS[0]} onCancel={() => {}} onDelete={() => {}} />,
    'top row': <TopBar sidebarOpen={false} onShowSidebar={() => {}} title="A fake chat" compact={compact} />,
    'question box': composer,
    'compact bar': <CompactBar compact={{ ...compact, on: true }} notice="" waiting={null} stopped={false}
                               latest={undefined} onRestart={() => {}} composer={composer} />,
    'compact bar, grown with an answer (M43)': (
      <CompactBar compact={{ ...compact, on: true, grown: true }} notice="" waiting={null} stopped={false} onRestart={() => {}}
                  latest={{ question: 'A fake question?', steps: [{ label: 'Read the window you were on' }], answer: 'Fake.',
                            running: false }} composer={composer} />
    ),
    'empty chat': <Conversation phase="ready" turns={[]} session="s" end={createRef<HTMLDivElement>()} waiting={null}
                                suggestions={['A fake suggestion?', 'Another one?']} canAsk onAsk={() => {}} />,
  };

  it.each(Object.entries(pages))('%s', (_name, page) => {
    const found = buttons(renderToStaticMarkup(page));
    expect(found.length).toBeGreaterThan(1);
    for (const button of found) {
      expect(button.words !== '' || /aria-label="[^"]+"/.test(button.tag), button.tag).toBe(true);
    }
  });
});
