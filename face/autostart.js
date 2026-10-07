/**
 * M36: "Start with Windows", the entry itself.
 *
 * What it demonstrates: how a Windows program starts at sign-in. There is no service and no
 * scheduler here: Windows keeps a list of commands, one registry value each, under
 *   HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run
 * and runs them when you sign in. Electron's login-item setting reads and writes that list.
 * Ours is one value named "Pseudo" holding  "<path>\Pseudo.exe" --start-hidden .
 *
 * Two rules:
 *   - The switch shows what WINDOWS says, read fresh each time, never a remembered value.
 *     You can also switch the entry off in Task Manager > Startup apps, and the page must
 *     not claim otherwise.
 *   - Only Pseudo.exe can be registered. Under `npm start` the program is a bare
 *     electron.exe, which would start an empty Electron at sign-in, so nothing is written.
 *
 * (Measured in the M36 probe: with a name and arguments given, Electron's `openAtLogin` stays
 * false even when the entry exists, so the entry is looked up in `launchItems` instead.)
 */

const path = require('node:path');

const NAME = 'Pseudo'; // the registry value's name: the one entry this file ever touches
const HIDDEN_ARG = '--start-hidden';
const NOT_PACKAGED = 'Start with Windows works from Pseudo.exe, not from npm start.';
const OFF_IN_WINDOWS = 'Windows has this switched off (Task Manager > Startup apps). Switching it on here turns it back on.';
const OTHER_EXE = 'An older entry points at another Pseudo.exe. Switch this on to replace it.';

const samePath = (a, b) => path.resolve(String(a)).toLowerCase() === path.resolve(String(b)).toLowerCase();

/**
 * What Windows says right now, as the message the page shows.
 * @param {object} app Electron's app
 * @param {string} exe this program's own path
 * @returns {{ type: 'autostart', available: boolean, on: boolean, note: string }}
 */
function autostartState(app, exe = process.execPath) {
  if (!app.isPackaged) return { type: 'autostart', available: false, on: false, note: NOT_PACKAGED };
  const items = app.getLoginItemSettings({ name: NAME, args: [HIDDEN_ARG] }).launchItems || [];
  const item = items.find((entry) => entry.name === NAME);
  if (!item) return { type: 'autostart', available: true, on: false, note: '' };
  if (!samePath(item.path, exe)) return { type: 'autostart', available: true, on: false, note: OTHER_EXE };
  if (!item.enabled) return { type: 'autostart', available: true, on: false, note: OFF_IN_WINDOWS };
  return { type: 'autostart', available: true, on: true, note: '' };
}

/** Add or remove the entry, then report what Windows says: the page shows that, not what was asked. */
function setAutostart(app, on, exe = process.execPath) {
  if (app.isPackaged) app.setLoginItemSettings({ openAtLogin: on, name: NAME, args: [HIDDEN_ARG], enabled: true });
  return autostartState(app, exe);
}

/** Was this Pseudo started by that entry? Only the packaged app listens to the argument. */
function startedHidden(app, argv = process.argv) {
  return app.isPackaged && argv.includes(HIDDEN_ARG);
}

module.exports = { HIDDEN_ARG, NAME, autostartState, setAutostart, startedHidden };
