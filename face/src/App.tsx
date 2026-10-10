// M18: the window. It shows what the brain says and sends what you ask; it decides nothing (D11).
// Every message from the brain goes through reduce() (state.ts); every click becomes one
// message to the brain (protocol.ts), through window.pseudo (preload.js).
// M26: voice (useVoice.ts). What you say comes back as text in the input box: you read it, fix it if
// needed, and press Enter, exactly like typing (L8). Nothing you say is ever sent as a question by itself.
// M39: the Phase 10 layout (components/): a sidebar, a top row, the conversation and the question box, with the
// switches in Settings. This file wires state to them; the parts only draw. The logic here is unchanged.
// M40: suggestions ask like Enter does; a question's progress is said in the conversation; nothing under the box.
// M41: the sidebar searches, renames and deletes chats, and holds the provider picker; the top row shows a title.
// M42: the look-at chip in the question box, Chats or Memory (the memory browser), and the Status panel.

import { useEffect, useReducer, useRef, useState } from 'react';
import { BottomArea } from './components/BottomArea';
import { CompactBar } from './components/CompactBar';
import { Conversation } from './components/Conversation';
import { LookingAtChip } from './components/LookingAtChip';
import { MemoryView } from './components/MemoryView';
import type { Panel } from './components/PanelSwitch';
import { ListeningChip, MicButton } from './components/MicButton';
import { ProviderPicker } from './components/ProviderPicker';
import { SettingsDialog } from './components/SettingsDialog';
import { Sidebar } from './components/Sidebar';
import { StatusPanel } from './components/StatusPanel';
import { TopBar } from './components/TopBar';
import { Composer } from './Composer';
import type { ToBrain } from './protocol';
import { initial, reduce } from './state';
import { useCompact } from './useCompact';
import { useLookingAt } from './useLookingAt';
import { useVoice } from './useVoice';
import { useWarm } from './useWarm';

export function App() {
  const [state, dispatch] = useReducer(reduce, initial);
  const [draft, setDraft] = useState('');
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [panel, setPanel] = useState<Panel>('chats'); // M42: the chat, or your memory
  const end = useRef<HTMLDivElement>(null);
  const box = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    window.pseudo.onMessage((message) => dispatch({ type: 'from_brain', message, at: Date.now() }));
  }, []);
  useEffect(() => {
    end.current?.scrollIntoView({ block: 'end' });
  }, [state.turns]);

  const idle = state.phase === 'ready' && state.working === null;
  const current = state.providers.find((provider) => provider.id === state.provider);
  const canTalk = idle && Boolean(current?.transcribe_model);
  const why = current && !current.transcribe_model
    ? 'Voice needs a provider with a speech model: your voice stays on this laptop' : 'Wait for Pseudo to finish';

  useEffect(() => { // M39: the sidebar's chats, asked for only while Pseudo is free (a refusal mid-question would
    if (idle) window.pseudo.send({ type: 'list_sessions' }); // clear the approval banner; M40 fixes that in state.ts)
  }, [idle, state.session]);
  useLookingAt(idle); // M42: the chip, when Pseudo is free and whenever its window gains focus
  useEffect(() => { // M42: the memory list, once, and again after a memory is saved; only while Pseudo is free
    if (!idle || !state.seen.memory.stale) return;
    window.pseudo.send({ type: 'list_memories' });
    dispatch({ type: 'memory', change: 'asked' });
  }, [idle, state.seen.memory.stale]);

  function send(message: ToBrain, what: string) {
    window.pseudo.send(message);
    dispatch({ type: 'working', what });
  }

  const voice = useVoice({ canTalk, ready: state.phase === 'ready', speech: state.speech,
                           onRecorded: (audio) => send({ type: 'transcribe', audio }, 'Turning what you said into text') });
  const warm = useWarm(state.phase === 'ready'); // M32: the remembered warm-session switch
  const compact = useCompact(state.compact, state.turns.length, state.phase); // M38: the bar, and whether it shows an answer
  useEffect(() => { // a transcript lands in the input box, after anything you'd already typed
    const heard = state.heard?.text;
    if (!heard) return;
    setDraft((typed) => (typed.trim() ? `${typed.trim()} ${heard}` : heard));
    box.current?.focus();
  }, [state.heard]);

  useEffect(() => { // M37: Ctrl+Alt+T, pressed in any app, is one press of the mic button (start, or stop)
    if (state.talk) voice.toggle(); // it does nothing while Pseudo can't listen: starting, busy, or no speech model
  }, [state.talk]);

  /** Ask the draft, or (M40) a suggestion: the same message either way; a suggestion leaves the draft alone. */
  function ask(suggestion?: string) {
    const text = (suggestion ?? draft).trim();
    if (!text || !idle) return;
    window.pseudo.send({ type: 'ask', text });
    dispatch({ type: 'asked', text, at: Date.now() });
    compact.open(); // M38: the bar grows to show this turn's steps, approval line and answer
    if (suggestion === undefined) setDraft('');
  }

  const switchTo = (id: string) => send({ type: 'provider', id }, `Switching to ${id}`);
  function showPanel(next: Panel) { // M42: Memory lists your notes afresh: you may have edited them in Obsidian
    setPanel(next);
    if (next === 'memory' && idle) window.pseudo.send({ type: 'list_memories' });
  }

  function restart() {
    dispatch({ type: 'restarting' });
    window.pseudo.send({ type: 'restart' });
  }

  // M40: a question's progress is said in the conversation (Activity.tsx); this line is for everything else.
  const questionRunning = Boolean(state.turns.at(-1)?.running);
  const notice = state.phase === 'stopped' ? "Pseudo's brain stopped."
    : state.phase === 'starting' ? 'Starting the brain'
    : voice.listening ? 'Listening. Let go of Ctrl+Space, or click the mic, when you have finished.'
    : (!questionRunning && state.working) || voice.problem || state.notice;

  const composer = (row: boolean) => (
    <Composer draft={draft} setDraft={setDraft} canAsk={idle} onAsk={() => ask()} box={box} row={row}
              mic={<MicButton voice={voice} canTalk={canTalk} why={why} />}
              chips={row ? <LookingAtChip looking={state.seen.lookingAt} short /> // M43: the bar's row has room for the name only
                         : <><LookingAtChip looking={state.seen.lookingAt} /><ListeningChip voice={voice} /></>} />
  );
  const stopped = state.phase === 'stopped';

  if (compact.on) {
    return <CompactBar compact={compact} latest={state.turns.at(-1)} composer={composer(true)} notice={notice}
                       waiting={state.waiting} stopped={stopped} onRestart={restart} />;
  }
  return (
    <div className="flex h-full bg-ground text-ink">
      {sidebarOpen && (
        <Sidebar onHide={() => setSidebarOpen(false)} idle={idle} sessions={state.sessions} found={state.found}
                 current={state.session}
                 onNewChat={() => { setPanel('chats'); send({ type: 'new_session' }, 'Starting a new chat'); }}
                 onOpen={(name) => { setPanel('chats'); send({ type: 'open_session', name }, 'Opening the chat'); }}
                 panel={panel} onPanel={showPanel} memoryCount={state.seen.memory.items?.length ?? null}
                 status={<StatusPanel totals={state.seen.totals} warm={state.warm} />}
                 onSearch={(text) => window.pseudo.send({ type: 'search_sessions', text })} // a read: never busy
                 onRename={(name, title) => send({ type: 'rename_session', name, title }, 'Renaming the chat')}
                 onDelete={(name) => send({ type: 'delete_session', name }, 'Deleting the chat')}
                 picker={<ProviderPicker providers={state.providers} current={state.provider} idle={idle}
                                         onSwitch={switchTo} actionBrain={state.actionBrain}
                                         onSettings={() => setSettingsOpen(true)} />} />
      )}
      <main className="flex min-w-0 flex-1 flex-col">
        <TopBar sidebarOpen={sidebarOpen} onShowSidebar={() => setSidebarOpen(true)} compact={compact}
                title={panel === 'memory' ? 'Memory' : state.title || state.turns[0]?.question || 'New chat'} />
        {panel === 'memory' ? (
          <MemoryView memory={state.seen.memory} disabled={!idle} notice={notice}
                      onOpen={(name) => window.pseudo.send({ type: 'open_memory', name })}
                      onClose={() => dispatch({ type: 'memory', change: 'closed' })} />
        ) : (
          <>
            <Conversation phase={state.phase} turns={state.turns} session={state.session} end={end} waiting={state.waiting}
                          suggestions={state.suggestions} canAsk={idle} onAsk={ask} />
            <BottomArea composer={composer(false)} notice={notice} stopped={stopped} onRestart={restart} />
          </>
        )}
      </main>
      <SettingsDialog open={settingsOpen} onClose={() => setSettingsOpen(false)} providers={state.providers}
                      current={state.provider} idle={idle} onSwitch={switchTo}
                      actionBrain={state.actionBrain} warm={state.warm} warmOn={warm.warmOn} setWarmOn={warm.setWarmOn}
                      autostart={state.autostart} voice={voice} hotkeys={state.hotkeys} />
    </div>
  );
}
