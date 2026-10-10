// M39: Settings, the things you change once in a while, out of the main view (from the mockup).
// What it holds moved in unchanged: the provider, Keep Claude Code warm (only where action requests go to
// Claude Code), Start with Windows, Speak answers and the shortcuts. Each control still only asks; the brain
// or the main process decides and answers.

import { AutostartControl } from '../AutostartControl';
import { HotkeysNote } from '../HotkeysNote';
import type { ActionBrain, Autostart, Hotkey, Provider, Warm } from '../protocol';
import { ProviderBar } from '../ProviderBar';
import type { Voice } from '../useVoice';
import { WarmControl } from '../WarmControl';
import { SettingRow } from './SettingRow';
import { Button } from './ui/Button';
import { Dialog } from './ui/Dialog';
import { Switch } from './ui/Switch';

type Props = {
  open: boolean;
  onClose(): void;
  providers: Provider[];
  current: string;
  idle: boolean;
  onSwitch(id: string): void;
  actionBrain: ActionBrain | null;
  warm: Warm | null;
  warmOn: boolean;
  setWarmOn(on: boolean): void;
  autostart: Autostart | null;
  voice: Voice;
  hotkeys: Hotkey[] | null;
};

export function SettingsDialog(props: Props) {
  const { open, onClose, providers, current, idle, onSwitch, actionBrain, warm, warmOn, setWarmOn, autostart, voice, hotkeys } = props;
  const provider = providers.find((each) => each.id === current);
  return (
    <Dialog open={open} onClose={onClose} title="Settings"
            footer={<Button variant="primary" className="font-medium" onClick={onClose}>Done</Button>}>
      <div className="max-h-[calc(100vh-170px)] overflow-y-auto">
        <ProviderBar providers={providers} current={current} disabled={!idle} onSwitch={onSwitch} />
        {actionBrain && provider?.leaves_laptop && ( // M32: only where action requests go to Claude Code
          <WarmControl warm={warm} warmOn={warmOn} setWarmOn={setWarmOn} />
        )}
        <AutostartControl autostart={autostart} />
        <SettingRow label="Speak answers" note="Pseudo reads each answer aloud with Windows' own voice, on this laptop.">
          <Switch checked={voice.speakOn} onChange={voice.setSpeakOn} label="Speak answers" />
        </SettingRow>
        <HotkeysNote keys={hotkeys} />
      </div>
    </Dialog>
  );
}
