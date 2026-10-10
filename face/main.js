/**
 * M18: Pseudo's face, the Electron MAIN process.
 *
 * What it demonstrates: Electron's process model.
 *   - This file is the MAIN process: Node.js, with full access to the laptop.
 *   - The window's page is the RENDERER: Chromium running the React code in src/, with
 *     NO Node.js access at all.
 *   - preload.js is the only door between them: a narrow window.pseudo API.
 * The main process relays messages between the page and the brain (brain-process.js).
 * It decides nothing about them (D11): the rules live in pseudo_brain and pseudo_hands.
 *
 * Electron's security checklist, and what each setting blocks:
 *   - contextIsolation + sandbox + no nodeIntegration: page code can't reach Node.js or the
 *     preload's internals, so a bug in the page can't read files or start programs.
 *   - webSecurity stays on: the page gets a normal browser's same-origin rules.
 *   - Pages come from app://pseudo/, a protocol that serves only files inside face/dist
 *     (serve-file.js: the path is resolved and anything outside is refused, like the M3 sandbox). There
 *     is no web server and no port (D18), not even Vite's dev server.
 *   - A strict Content-Security-Policy (index.html): scripts and styles only from our own
 *     files, and no network requests at all.
 *   - Navigation, new windows and <webview> are blocked, and there is no menu (no reload,
 *     no developer tools). Every permission request is refused except one (M26,
 *     permissions.js): the microphone, audio only, for our own page, for push-to-talk.
 *   - IPC is accepted only from our own page, and only the message types the brain knows (to-brain.js).
 *
 * Before each tool runs, this process lets pseudo_hands' process (only that one) bring its
 * approval popup to the front, above this window (foreground.js), and flashes the taskbar
 * button if you're in another window (taskbar-flash.js).
 *
 * (M36) Started by Windows at sign-in (`--start-hidden`, autostart.js), the window stays hidden, a tray
 * icon stands in for it (tray.js), and the brain is started the first time the window is shown (reveal.js).
 * (M37) Two global shortcuts show or hide the window and start or stop talking (hotkeys.js); no keyboard hook.
 * (M38) The window has two modes, full and a compact always-on-top bar (window-mode.js). The bar gives up
 * always-on-top while a tool waits, so an approval popup can't end up under it.
 * (M39) The window is always dark, with its title bar blended into the page (window-look.js).
 */

const fs = require('node:fs');
const path = require('node:path');
const { app, BrowserWindow, Menu, Tray, globalShortcut, ipcMain, nativeImage, net, protocol, screen, session } = require('electron');
const { autostartState, setAutostart, startedHidden } = require('./autostart');
const { brainHome } = require('./brain-home');
const { BrainProcess } = require('./brain-process');
const { ForegroundGrant, windowsAllow } = require('./foreground');
const { Hotkeys } = require('./hotkeys');
const { allowCheck, allowRequest } = require('./permissions');
const { Reveal } = require('./reveal');
const { serveFrom } = require('./serve-file');
const { onlyOne } = require('./single-instance');
const { TaskbarFlash } = require('./taskbar-flash');
const { cleanForBrain } = require('./to-brain');
const { createTray } = require('./tray');
const { WINDOW_LOOK } = require('./window-look');
const { WindowMode } = require('./window-mode');
const { fileStore } = require('./window-store');

const DIST = path.join(__dirname, 'dist');
const PAGE = 'app://pseudo/index.html';

protocol.registerSchemesAsPrivileged([
  { scheme: 'app', privileges: { standard: true, secure: true, supportFetchAPI: true } },
]);
app.enableSandbox(); // every renderer is sandboxed, whatever its window says

let win = null;
let quitting = false;
let tray = null; // made at a hidden start (M36), or the first time the window is hidden (M37)
const startHidden = startedHidden(app); // M36: started by the Start with Windows entry
// M38: full, or a compact always-on-top bar, on the same window; sizes are remembered in the profile folder.
const mode = new WindowMode(() => win, screen, fileStore(path.join(app.getPath('userData'), 'window-mode.json'), fs));
// M36: every way of showing the window. Before a hide: a tray icon exists (M37) and the bar lets go of always-on-top (M38).
const reveal = new Reveal(() => win, () => brain.start(), () => { ensureTray(); mode.letGo(); });
const first = onlyOne(app, () => reveal.show()); // M34: a second launch shows the first Pseudo's window
if (!first) app.quit(); // and then quits, before it opens a window or starts a brain
// M37: Ctrl+Alt+Enter shows or hides; Ctrl+Alt+T shows and presses the page's mic button (start, or stop).
const hotkeys = new Hotkeys(globalShortcut, {
  toggle: () => reveal.toggle(),
  talk: () => reveal.show() && toPage({ type: 'talk' }),
});
const grant = new ForegroundGrant(windowsAllow());
const flash = new TaskbarFlash(
  (on) => win && !win.isDestroyed() && win.flashFrame(on),
  () => Boolean(win && !win.isDestroyed() && win.isFocused()),
);
const brain = new BrainProcess(
  (message) => {
    grant.fromBrain(message); // `ready` names pseudo_hands' process; `tool_call` grants
    flash.fromBrain(message); // `tool_call` flashes if you're elsewhere; its result stops it
    mode.fromBrain(message); // M38: `tool_call` takes the bar out of always-on-top; its result puts it back
    toPage(message);
  },
  (code) => {
    grant.brainStopped();
    flash.brainStopped();
    mode.brainStopped();
    if (!quitting) toPage({ type: 'brain_stopped', code }); // the page offers a Restart button
  },
  brainHome(app.isPackaged, process.resourcesPath, __dirname), // M34: Pseudo.exe reads where the repo is
);

/** A hidden Pseudo must stay reachable: one tray icon, made when first needed. */
function ensureTray() {
  if (!tray) tray = createTray({ Tray, Menu, nativeImage }, () => reveal.show(), () => app.quit());
}

/** A message for the page: from the brain, or brain_stopped from here. */
function toPage(message) {
  if (win && !win.isDestroyed()) win.webContents.send('pseudo:message', message);
}

/** Did this IPC message come from our own page (not some other frame or page)? */
function fromOurPage(event) {
  try {
    const url = new URL(event.senderFrame.url);
    return url.protocol === 'app:' && url.host === 'pseudo';
  } catch {
    return false;
  }
}

ipcMain.on('pseudo:send', (event, message) => {
  if (!fromOurPage(event) || typeof message !== 'object' || message === null) return;
  if (message.type === 'restart') return brain.start(); // after "brain stopped"; ignored while it runs
  // M36: the Start with Windows switch is answered here, with what Windows says; it never reaches the brain.
  if (message.type === 'autostart') return toPage(typeof message.on === 'boolean' ? setAutostart(app, message.on) : autostartState(app));
  if (message.type === 'window_mode') return toPage(mode.fromPage(message)); // M38: answered here too (window-mode.js)
  const clean = cleanForBrain(message); // M37: rebuilt from the fields it may have (to-brain.js), or dropped
  if (clean) brain.send(clean);
});

function createWindow() {
  win = new BrowserWindow({
    ...mode.options(), // M38: the remembered mode's size, place and minimum
    title: 'Pseudo',
    show: !startHidden,
    ...WINDOW_LOOK, // M39: always dark, with the title bar blended into the page (window-look.js)
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      sandbox: true,
      nodeIntegration: false,
      webSecurity: true,
    },
  });
  win.on('focus', () => toPage(autostartState(app))); // it may have been changed in Task Manager meanwhile
  win.webContents.on('did-finish-load', () => {
    toPage(hotkeys.state()); // M37: which shortcuts Windows gave us
    toPage(mode.state()); // M38: full or compact
  });
  mode.attach(win);
  win.loadURL(PAGE);
}

app.on('web-contents-created', (_event, contents) => {
  contents.on('will-navigate', (event) => event.preventDefault());
  contents.on('will-redirect', (event) => event.preventDefault());
  contents.on('will-attach-webview', (event) => event.preventDefault());
  contents.setWindowOpenHandler(() => ({ action: 'deny' }));
});

app.whenReady().then(() => {
  if (!first) return; // quitting: another Pseudo is running
  Menu.setApplicationMenu(null);
  session.defaultSession.setPermissionRequestHandler(
    (_contents, permission, answer, details) => answer(allowRequest(permission, details)));
  session.defaultSession.setPermissionCheckHandler(
    (_contents, permission, origin, details) => allowCheck(permission, origin, details));
  protocol.handle('app', serveFrom(DIST, (fileUrl) => net.fetch(fileUrl))); // M38: serve-file.js
  hotkeys.register();
  createWindow();
  if (startHidden) ensureTray();
  else reveal.startBrain(); // opened by hand: everything starts at once, as before
});

app.on('window-all-closed', () => app.quit());
app.on('will-quit', () => {
  hotkeys.release(); // M37: give the two shortcuts back
  if (tray) tray.destroy(); // or Windows keeps a dead icon until the mouse passes over it
});

// Quitting: stop the brain first (it stops pseudo_hands and private mode's server), then quit.
app.on('before-quit', (event) => {
  if (!brain.running) return; // nothing left to stop
  event.preventDefault();
  if (quitting) return; // already stopping
  quitting = true;
  brain.stop().then(() => app.quit());
});
