// M36: the Start with Windows switch and its line (AutostartControl.tsx). All states are fake.
// renderToStaticMarkup turns React output into an HTML string, so no browser is needed.
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { AutostartControl, autostartLine } from './AutostartControl';
import type { Autostart } from './protocol';

const OFF: Autostart = { available: true, on: false, note: '' };
const ON: Autostart = { available: true, on: true, note: '' };
const NPM: Autostart = { available: false, on: false, note: 'Start with Windows works from Pseudo.exe, not from npm start.' };

describe('autostartLine', () => {
  it('says what happens at the next sign-in', () => {
    expect(autostartLine(ON)).toContain('starts hidden when you sign in');
    expect(autostartLine(ON)).toContain('Its brain starts when you first open it');
    expect(autostartLine(OFF)).toBe('Off: Pseudo starts only when you open it.');
  });

  it("shows the main process's reason instead, when there is one", () => {
    expect(autostartLine(NPM)).toBe(NPM.note);
    const blocked = { ...OFF, note: 'Windows has this switched off (Task Manager > Startup apps).' };
    expect(autostartLine(blocked)).toBe(blocked.note);
  });
});

describe('AutostartControl', () => {
  it('shows nothing until Windows has been asked', () => {
    expect(renderToStaticMarkup(<AutostartControl autostart={null} />)).toBe('');
  });

  // M39: a switch in a Settings row now; the checks are the same.
  it('the switch follows what Windows says', () => {
    expect(renderToStaticMarkup(<AutostartControl autostart={ON} />)).toMatch(/role="switch" aria-checked="true"/);
    expect(renderToStaticMarkup(<AutostartControl autostart={OFF} />)).toMatch(/role="switch" aria-checked="false"/);
  });

  it('under npm start the switch is disabled, off, and the reason is shown', () => {
    const html = renderToStaticMarkup(<AutostartControl autostart={NPM} />);
    expect(html).toContain('disabled=""');
    expect(html).toContain('aria-checked="false"');
    expect(html).toContain('not from npm start');
  });

  it('is labelled for assistive tools and for the checks that look for it', () => {
    const html = renderToStaticMarkup(<AutostartControl autostart={OFF} />);
    expect(html).toContain('role="group" aria-label="Start with Windows"');
    expect(html).toMatch(/role="switch"[^>]*aria-label="Start with Windows"/);
    expect(html).not.toContain('disabled=""'); // the attribute; Tailwind's class names say "disabled:" too
  });
});
