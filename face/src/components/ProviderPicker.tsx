// M41: the sidebar's bottom row (from the mockup): who answers your questions, one click from changing it, and
// the Settings button. The panel is the same list Settings shows (ProviderBar), each provider with where your
// words go, and where requests to click, type or tick go (D28). Switching starts a new chat, as always (M16).

import { ChevronDown, SlidersHorizontal } from 'lucide-react';
import { useState } from 'react';
import type { ActionBrain, Provider } from '../protocol';
import { ActionBrainNote, ProviderBar } from '../ProviderBar';
import { Button } from './ui/Button';
import { Popover } from './ui/Popover';
import { Tip } from './ui/Tip';

type Props = {
  providers: Provider[];
  current: string;
  idle: boolean; // a switch waits until Pseudo is free
  onSwitch(id: string): void;
  actionBrain: ActionBrain | null;
  onSettings(): void;
};

export function ProviderPicker({ providers, current, idle, onSwitch, actionBrain, onSettings }: Props) {
  const [open, setOpen] = useState(false);
  const provider = providers.find((each) => each.id === current);
  const model = provider?.models[0].split('/').pop() ?? ''; // "openai/gpt-oss-120b" -> "gpt-oss-120b": the row is short
  const name = provider ? `${provider.name} · ${model}` : 'Starting';
  return ( // M42: the line above it belongs to the sidebar's bottom block (Sidebar.tsx)
    <div className="flex items-center gap-1.5 p-2.5">
      <Popover open={open} onOpenChange={setOpen} label="Choose a model"
               trigger={
                 <button type="button" aria-label={`Questions go to ${name}. Choose a model`} disabled={!provider}
                         className="flex h-[34px] min-w-0 flex-1 cursor-pointer items-center gap-1.5 rounded-[10px] border border-edge
                                    px-2.5 text-left text-[13px] hover:bg-raised disabled:cursor-default disabled:opacity-50">
                   <span className="min-w-0 flex-1 truncate">
                     {provider?.name ?? name} {provider && <span className="text-faint">· {model}</span>}
                   </span>
                   <ChevronDown aria-hidden="true" className="size-3.5 shrink-0 text-muted" />
                 </button>
               }>
        <ProviderBar providers={providers} current={current} disabled={!idle}
                     onSwitch={(id) => { setOpen(false); onSwitch(id); }} />
        <ActionBrainNote actionBrain={actionBrain} provider={provider} />
      </Popover>
      <Tip label="Settings">
        <Button variant="outline" size="icon" aria-label="Settings" className="size-[34px]" onClick={onSettings}>
          <SlidersHorizontal aria-hidden="true" className="size-4 text-muted" />
        </Button>
      </Tip>
    </div>
  );
}
