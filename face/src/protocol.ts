// M18: the messages the page and the brain exchange (pseudo_brain/bridge.py), as TypeScript types.
// The page reaches the brain only through window.pseudo, which preload.js provides.

export type Provider = { id: string; name: string; models: string[]; leaves_laptop: boolean; privacy: string;
                         transcribe_model: string }; // M26: '' = no voice input on this provider
export type ActionBrain = { id: string; name: string; model: string; privacy: string }; // M30, D26
export type SavedMessage = { role: 'user' | 'assistant'; content: string; answered_by?: string };
export type SessionInfo = { name: string; provider: string; messages: SavedMessage[] };
export type SessionItem = { name: string; provider: string; questions: number; title: string };
export type EventData = Record<string, any>; // each event kind has its own fields (see events.ts)

export type FromBrain =
  | { type: 'ready'; providers: Provider[]; provider: string; session: SessionInfo; tools: string[];
      action_brain?: ActionBrain | null } // M30: who answers action requests; null = nobody
  | { type: 'event'; kind: string; data: EventData }
  | { type: 'switched'; provider: string; session: SessionInfo }
  | ({ type: 'session' } & SessionInfo)
  | { type: 'sessions'; items: SessionItem[] }
  | { type: 'refused'; reason: string }
  | { type: 'turn_done'; ok: boolean }
  | { type: 'transcript'; text: string; note: string; seconds: number } // M26: goes into the input box, never sent by itself
  | { type: 'speech'; audio: string; reason: string } // M26: a spoken answer (base64 WAV), or why there's none
  | { type: 'brain_stopped'; code: number | null }; // sent by the main process, not the brain

export type ToBrain =
  | { type: 'ask'; text: string }
  | { type: 'provider'; id: string }
  | { type: 'new_session' }
  | { type: 'list_sessions' }
  | { type: 'open_session'; name: string }
  | { type: 'restart' } // handled by the main process: start the brain again
  | { type: 'transcribe'; audio: string } // M26: one push-to-talk recording, base64 PCM (16 kHz mono 16-bit)
  | { type: 'speak_answers'; on: boolean }; // M26: the Speak answers switch

declare global {
  interface Window {
    pseudo: {
      send(message: ToBrain): void;
      onMessage(callback: (message: FromBrain) => void): void;
    };
  }
}
