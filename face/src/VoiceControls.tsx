// M26: the mic button, the Speak answers switch and Stop speaking. Display only: useVoice does the work.

import { clock, MAX_SECONDS } from './audio';
import type { Voice } from './useVoice';

type Props = { voice: Voice; canTalk: boolean; why: string };

export function VoiceControls({ voice, canTalk, why }: Props) {
  return (
    <div className="voice" role="group" aria-label="Voice">
      <button type="button" className={voice.listening ? 'mic on' : 'mic'} aria-pressed={voice.listening}
              disabled={!canTalk && !voice.listening} title={canTalk ? 'Click, or hold Ctrl+Space' : why}
              onClick={voice.toggle}>
        {voice.listening ? `Stop talking ${clock(voice.seconds)} / ${clock(MAX_SECONDS)}` : 'Start talking'}
      </button>
      <label className="speak">
        <input type="checkbox" checked={voice.speakOn} onChange={(event) => voice.setSpeakOn(event.target.checked)} />
        Speak answers
      </label>
      {voice.speaking && (
        <button type="button" className="quiet" onClick={voice.stopSpeaking}>Stop speaking</button>
      )}
      <span className="hint">{canTalk ? 'Hold Ctrl+Space to talk' : why}</span>
    </div>
  );
}
