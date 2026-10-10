// M40: where your words go is in Settings now (D28): each provider's privacy note and fallback models, and where
// requests to click, type or tick go. All providers and brains here are fake.
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import type { ActionBrain, Provider } from '../protocol';
import type { Voice } from '../useVoice';
import { SettingsDialog } from './SettingsDialog';

const GROQ: Provider = { id: 'groq', name: 'Groq', models: ['big-model', 'small-model'], leaves_laptop: true,
                         privacy: 'Fake cloud note.', transcribe_model: 'ears' };
const LOCAL: Provider = { id: 'local', name: 'Private mode', models: ['tiny'], leaves_laptop: false,
                          privacy: 'Fake local note.', transcribe_model: '' };
const BRAIN: ActionBrain = { id: 'claude-code', name: 'Claude Code', model: 'sonnet', privacy: 'Fake action note.' };
const voice: Voice = { listening: false, seconds: 0, speaking: false, speakOn: true, problem: '', toggle() {},
                       setSpeakOn() {}, stopSpeaking() {} };

const settings = (current: string, actionBrain: ActionBrain | null = BRAIN) => renderToStaticMarkup(
  <SettingsDialog open={false} onClose={() => {}} providers={[GROQ, LOCAL]} current={current} idle onSwitch={() => {}}
                  actionBrain={actionBrain} warm={null} warmOn setWarmOn={() => {}} autostart={null} voice={voice} hotkeys={null} />);

describe('Settings holds the privacy information (M40, D28)', () => {
  it("every provider's privacy note, and its fallback models", () => {
    const html = settings('groq');
    expect(html).toContain('Fake cloud note.');
    expect(html).toContain('On a rate limit: small-model, never another provider.');
    expect(html).toContain('Fake local note.');
    expect(html).toContain('Leaves this laptop');
    expect(html).toContain('Stays on this laptop');
  });

  it('where action requests go, while they really go there', () => {
    const html = settings('groq');
    expect(html).toContain('aria-label="Where action requests go"');
    expect(html).toContain('These requests go to Claude Code · sonnet, after a billing check. Fake action note.');
  });

  it('not in private mode (it never routes), and not when there is no action brain', () => {
    expect(settings('local')).not.toContain('Where action requests go');
    expect(settings('groq', null)).not.toContain('Where action requests go');
  });
});
