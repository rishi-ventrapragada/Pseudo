// M18: the messages the page and the brain exchange (pseudo_brain/bridge.py), as TypeScript types.
// The page reaches the brain only through window.pseudo, which preload.js provides.

export type Provider = { id: string; name: string; models: string[]; leaves_laptop: boolean; privacy: string;
                         transcribe_model: string; // M26: '' = no voice input on this provider
                         disabled?: string }; // M41: why it is switched off ('' or missing = usable); hidden from pickers
export type ActionBrain = { id: string; name: string; model: string; privacy: string }; // M30, D26
// M32: the warm Claude Code session, as the brain reports it (bridge_warm.py). Numbers and names only.
export type Warm = { on: boolean; open: boolean; ram_mb: number | null; asked: number; of: number;
                     idle_minutes: number; note: string };
// M36: the Start with Windows entry, as the main process read it from Windows (face/autostart.js).
export type Autostart = { available: boolean; on: boolean; note: string };
// M37: one global shortcut, as the main process registered it (face/hotkeys.js); ok = Windows gave it to Pseudo.
export type Hotkey = { id: string; label: string; ok: boolean };
export type SavedMessage = { role: 'user' | 'assistant'; content: string; answered_by?: string };
export type SessionInfo = { name: string; provider: string; messages: SavedMessage[];
                            title?: string }; // M41: the name you gave the chat; '' or missing = none
export type SessionItem = { name: string; provider: string; questions: number; title: string };
// M42: a saved memory, as the brain lists and opens it (pseudo_hands' memory_browse.py): redacted again.
export type MemoryItem = { name: string; date: string; title: string };
export type MemoryNote = { name: string; date: string; title: string; question: string; answer: string;
                           note: string }; // note: why it can't be opened, or ''
export type EventData = Record<string, any>; // each event kind has its own fields (see events.ts)

export type FromBrain =
  | { type: 'ready'; providers: Provider[]; provider: string; session: SessionInfo; tools: string[];
      action_brain?: ActionBrain | null; // M30: who answers action requests; null = nobody
      suggestions?: string[] } // M40: the empty chat's one-click questions (pseudo_brain/suggestions.py)
  | { type: 'event'; kind: string; data: EventData }
  | { type: 'switched'; provider: string; session: SessionInfo }
  | ({ type: 'session' } & SessionInfo)
  | { type: 'sessions'; items: SessionItem[] }
  | { type: 'found'; text: string; items: SessionItem[] } // M41: a search's reply, with the words it was for
  | { type: 'renamed'; name: string; title: string } // M41: a rename's last message (bridge_sessions.py)
  | { type: 'deleted'; name: string; title: string } // M41: a delete's last message
  | { type: 'looking_at'; app: string; private: boolean; note: string } // M42: the app a question would read now
  | { type: 'memory_list'; items: MemoryItem[]; note: string } // M42: your saved memories, newest first
  | ({ type: 'memory_note' } & MemoryNote) // M42: one memory, read-only
  | { type: 'refused'; reason: string }
  | { type: 'turn_done'; ok: boolean }
  | { type: 'transcript'; text: string; note: string; seconds: number } // M26: goes into the input box, never sent by itself
  | { type: 'speech'; audio: string; reason: string } // M26: a spoken answer (base64 WAV), or why there's none
  | ({ type: 'warm' } & Warm) // M32: sent whenever the warm session's state changes
  | { type: 'brain_stopped'; code: number | null } // sent by the main process, not the brain
  | ({ type: 'autostart' } & Autostart) // M36: sent by the main process: what Windows says right now
  | { type: 'hotkeys'; keys: Hotkey[] } // M37: sent by the main process: the two global shortcuts
  | { type: 'talk' } // M37: sent by the main process: Ctrl+Alt+T was pressed (in any app)
  | { type: 'window_mode'; compact: boolean }; // M38: sent by the main process: the window is the compact bar, or full

export type ToBrain =
  | { type: 'ask'; text: string }
  | { type: 'provider'; id: string }
  | { type: 'new_session' }
  | { type: 'list_sessions' }
  | { type: 'open_session'; name: string }
  | { type: 'search_sessions'; text: string } // M41: the chats whose title or your messages hold `text`
  | { type: 'rename_session'; name: string; title: string } // M41: refused while Pseudo is busy
  | { type: 'delete_session'; name: string } // M41: only after the confirm; refused while Pseudo is busy
  | { type: 'look' } // M42: which app a question would read now (the chip); answered only while Pseudo is idle
  | { type: 'list_memories' } // M42: the memory browser's list; refused while Pseudo is busy
  | { type: 'open_memory'; name: string } // M42: one memory, by its name, never a path
  | { type: 'restart' } // handled by the main process: start the brain again
  | { type: 'transcribe'; audio: string } // M26: one push-to-talk recording, base64 PCM (16 kHz mono 16-bit)
  | { type: 'speak_answers'; on: boolean } // M26: the Speak answers switch
  | { type: 'warm_sessions'; on: boolean } // M32: the warm-session switch
  | { type: 'autostart'; on?: boolean } // M36: answered by the main process; without `on`, it only asks
  // M38: answered by the main process (face/window-mode.js). `compact` switches the mode; `grown` says the bar is
  // showing an answer, so it needs its taller size; (M43) `height` with it: how tall the grown bar's content is.
  | { type: 'window_mode'; compact?: boolean; grown?: boolean; height?: number };

declare global {
  interface Window {
    pseudo: {
      send(message: ToBrain): void;
      onMessage(callback: (message: FromBrain) => void): void;
    };
  }
}
