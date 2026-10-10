// M26 (from VoiceControls.tsx; M39 moved it into the question box): the mic button, Stop speaking, and the
// "Listening" chip. Display only: useVoice does the work. Red is used only while recording (the mockup's rule).
// The Speak answers switch moved to Settings.

import { Mic, Square, VolumeX } from 'lucide-react';
import { clock, MAX_SECONDS } from '../audio';
import type { Voice } from '../useVoice';
import { cn } from '../lib/cn';
import { Button } from './ui/Button';
import { Tip } from './ui/Tip';

type Props = { voice: Voice; canTalk: boolean; why: string };

export function MicButton({ voice, canTalk, why }: Props) {
  const label = voice.listening ? `Stop talking (${clock(voice.seconds)} of ${clock(MAX_SECONDS)})` : 'Start talking';
  return (
    <>
      {/* A disabled button gets no mouse events, so the tip sits on a wrapper that always does. */}
      <Tip label={canTalk || voice.listening ? 'Click, or hold Ctrl+Space' : why}>
        <span className="inline-flex">
          <Button size="round" aria-label={label} aria-pressed={voice.listening} disabled={!canTalk && !voice.listening}
                  onClick={voice.toggle} className={cn(voice.listening && 'bg-danger/15 text-danger hover:bg-danger/20 hover:text-danger')}>
            {voice.listening ? <Square aria-hidden="true" className="size-4" /> : <Mic aria-hidden="true" className="size-[17px]" />}
          </Button>
        </span>
      </Tip>
      {voice.speaking && (
        <Button size="sm" onClick={voice.stopSpeaking}>
          <VolumeX aria-hidden="true" className="size-4" /> Stop speaking
        </Button>
      )}
    </>
  );
}

/** While recording: a chip above the text, with the time. */
export function ListeningChip({ voice }: { voice: Voice }) {
  if (!voice.listening) return null;
  return (
    <span className="inline-flex h-6 items-center gap-1.5 rounded-full bg-danger/12 pr-2.5 pl-2 text-xs text-danger" role="status">
      <span aria-hidden="true" className="size-[7px] rounded-full bg-danger" />
      Listening <span aria-hidden="true">{clock(voice.seconds)}</span> · click the mic to stop
    </span>
  );
}
