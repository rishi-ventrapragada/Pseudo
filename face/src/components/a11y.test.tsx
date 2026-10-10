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
import { ListeningChip, MicButton } from './MicButton';
import { ProviderPicker } from './ProviderPicker';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';

const voice: Voice = { listening: true, seconds: 3, speaking: true, speakOn: true, problem: '', toggle() {},
                       setSpeakOn() {}, stopSpeaking() {} };
const compact: Compact = { on: false, grown: false, setOn() {}, open() {}, close() {} };
const composer = <Composer draft="" setDraft={() => {}} canAsk onAsk={() => {}} box={createRef<HTMLTextAreaElement>()}
                           mic={<MicButton voice={voice} canTalk why="" />} chips={<ListeningChip voice={voice} />} />;
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
                      onSearch={() => {}} onRename={() => {}} onDelete={() => {}} picker={picker} />,
    'a chat with its menu open (M41)': <>{row({ menuOpen: true })}{row({})}</>,
    'a chat being renamed (M41)': <>{row({ renaming: true })}{row({})}</>,
    'the delete confirm (M41)': <DeleteChat item={ITEMS[0]} onCancel={() => {}} onDelete={() => {}} />,
    'top row': <TopBar sidebarOpen={false} onShowSidebar={() => {}} title="A fake chat" compact={compact} />,
    'question box': composer,
    'compact bar': <CompactBar compact={{ ...compact, on: true }} notice="" waiting={null} stopped={false}
                               latest={undefined} onRestart={() => {}} composer={composer} />,
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
