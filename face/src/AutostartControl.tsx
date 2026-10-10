// M36: the "Start with Windows" switch. Display only: the entry is read and written by the main process
// (face/autostart.js), and the box shows what WINDOWS says, never a remembered choice. So ticking it
// doesn't tick it: it asks the main process, and the box follows the answer that comes back. If Windows
// has the entry switched off (Task Manager > Startup apps), the box is empty and the line says why.

// M39: a row in Settings, with a switch instead of a checkbox; it still follows what Windows says.

import { useEffect } from 'react';
import { SettingRow } from './components/SettingRow';
import { Switch } from './components/ui/Switch';
import type { Autostart } from './protocol';

/** One line under the switch: what will happen at your next sign-in, or why the switch can't be used. */
export function autostartLine(autostart: Autostart): string {
  if (autostart.note) return autostart.note; // unavailable, switched off by Windows, or an older entry
  return autostart.on
    ? 'On: Pseudo starts hidden when you sign in, with an icon in the taskbar corner. Its brain starts when you first open it.'
    : 'Off: Pseudo starts only when you open it.';
}

export function AutostartControl({ autostart }: { autostart: Autostart | null }) {
  useEffect(() => { // ask once, when the window opens; the main process also answers whenever the window gets focus
    window.pseudo.send({ type: 'autostart' });
  }, []);
  if (!autostart) return null; // Windows hasn't been asked yet
  return (
    <SettingRow label="Start with Windows" note={autostartLine(autostart)}>
      <Switch checked={autostart.on} disabled={!autostart.available} label="Start with Windows"
              onChange={(on) => window.pseudo.send({ type: 'autostart', on })} />
    </SettingRow>
  );
}
