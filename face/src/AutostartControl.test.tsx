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

  it('the box follows what Windows says', () => {
    expect(renderToStaticMarkup(<AutostartControl autostart={ON} />)).toMatch(/<input type="checkbox"[^>]*checked=""/);
    expect(renderToStaticMarkup(<AutostartControl autostart={OFF} />)).not.toContain('checked');
  });

  it('under npm start the box is disabled, empty, and the reason is shown', () => {
    const html = renderToStaticMarkup(<AutostartControl autostart={NPM} />);
    expect(html).toContain('disabled=""');
    expect(html).not.toContain('checked');
    expect(html).toContain('not from npm start');
  });

  it('is labelled for assistive tools and for the checks that look for it', () => {
    const html = renderToStaticMarkup(<AutostartControl autostart={OFF} />);
    expect(html).toContain('aria-label="Start with Windows"');
    expect(html).toContain('Start with Windows</label>');
    expect(html).not.toContain('disabled');
  });
});
