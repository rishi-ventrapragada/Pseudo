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
 *     (the path is resolved and anything outside is refused, like the M3 sandbox). There
 *     is no web server and no port (D18), not even Vite's dev server.
 *   - A strict Content-Security-Policy (index.html): scripts and styles only from our own
 *     files, and no network requests at all.
 *   - Navigation, new windows and <webview> are blocked, and there is no menu (no reload,
 *     no developer tools). Every permission request is refused except one (M26,
 *     permissions.js): the microphone, audio only, for our own page, for push-to-talk.
 *   - IPC is accepted only from our own page, and only the message types the brain knows.
 *
 * Before each tool runs, this process lets pseudo_hands' process (only that one) bring its
 * approval popup to the front, above this window (foreground.js), and flashes the taskbar
 * button if you're in another window (taskbar-flash.js).
 */

const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { app, BrowserWindow, Menu, ipcMain, nativeTheme, net, protocol, session } = require('electron');
const { brainHome } = require('./brain-home');
const { BrainProcess } = require('./brain-process');
const { ForegroundGrant, windowsAllow } = require('./foreground');
const { allowCheck, allowRequest } = require('./permissions');
const { Reveal } = require('./reveal');
const { onlyOne } = require('./single-instance');
const { TaskbarFlash } = require('./taskbar-flash');

const DIST = path.join(__dirname, 'dist');
const PAGE = 'app://pseudo/index.html';
const TO_BRAIN = new Set(['ask', 'provider', 'new_session', 'list_sessions', 'open_session', 'transcribe',
                          'speak_answers', 'warm_sessions']);
const SWITCHES = new Set(['speak_answers', 'warm_sessions']); // M26, M32: each carries one true/false, `on`
const FIELDS = ['text', 'id', 'name']; // the only text fields a message to the brain may carry
// M26: a push-to-talk recording, base64. 30.5 s of 16 kHz 16-bit mono is about 1.3 million characters;
// anything bigger is dropped here, and the brain checks the length again (voice_in.py).
const MAX_AUDIO_CHARS = 1400000;

protocol.registerSchemesAsPrivileged([
  { scheme: 'app', privileges: { standard: true, secure: true, supportFetchAPI: true } },
]);
app.enableSandbox(); // every renderer is sandboxed, whatever its window says

let win = null;
let quitting = false;
const reveal = new Reveal(() => win, () => brain.start()); // M36: every way of showing the window
const first = onlyOne(app, () => reveal.show()); // M34: a second launch shows the first Pseudo's window
if (!first) app.quit(); // and then quits, before it opens a window or starts a brain
const grant = new ForegroundGrant(windowsAllow());
const flash = new TaskbarFlash(
  (on) => win && !win.isDestroyed() && win.flashFrame(on),
  () => Boolean(win && !win.isDestroyed() && win.isFocused()),
);
const brain = new BrainProcess(
  (message) => {
    grant.fromBrain(message); // `ready` names pseudo_hands' process; `tool_call` grants
    flash.fromBrain(message); // `tool_call` flashes if you're elsewhere; its result stops it
    toPage(message);
  },
  (code) => {
    grant.brainStopped();
    flash.brainStopped();
    if (!quitting) toPage({ type: 'brain_stopped', code }); // the page offers a Restart button
  },
  brainHome(app.isPackaged, process.resourcesPath, __dirname), // M34: Pseudo.exe reads where the repo is
);

/** A message for the page: from the brain, or brain_stopped from here. */
function toPage(message) {
  if (win && !win.isDestroyed()) win.webContents.send('pseudo:message', message);
}

/** app://pseudo/<path> -> that file inside face/dist, and nothing else. */
function serveFile(request) {
  try {
    const url = new URL(request.url);
    const wanted = decodeURIComponent(url.pathname === '/' ? '/index.html' : url.pathname);
    const file = path.resolve(DIST, '.' + wanted);
    const inside = path.relative(DIST, file);
    if (url.host !== 'pseudo' || !inside || inside.startsWith('..') || path.isAbsolute(inside)) {
      return new Response('refused', { status: 403 });
    }
    return net.fetch(pathToFileURL(file).toString());
  } catch {
    return new Response('bad request', { status: 400 }); // e.g. a broken %-escape in the path
  }
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
  if (!TO_BRAIN.has(message.type)) return;
  const clean = { type: message.type };
  for (const field of FIELDS) {
    if (typeof message[field] === 'string') clean[field] = message[field];
  }
  if (message.type === 'transcribe') {
    if (typeof message.audio !== 'string' || message.audio.length > MAX_AUDIO_CHARS) return;
    clean.audio = message.audio;
  }
  if (SWITCHES.has(message.type)) {
    if (typeof message.on !== 'boolean') return;
    clean.on = message.on;
  }
  brain.send(clean);
});

function createWindow() {
  win = new BrowserWindow({
    width: 980,
    height: 740,
    minWidth: 520,
    minHeight: 420,
    title: 'Pseudo',
    backgroundColor: nativeTheme.shouldUseDarkColors ? '#15181e' : '#eef1f5',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      sandbox: true,
      nodeIntegration: false,
      webSecurity: true,
    },
  });
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
  protocol.handle('app', serveFile);
  createWindow();
  reveal.startBrain();
});

app.on('window-all-closed', () => app.quit());

// Quitting: stop the brain first (it stops pseudo_hands and private mode's server), then quit.
app.on('before-quit', (event) => {
  if (!brain.running) return; // nothing left to stop
  event.preventDefault();
  if (quitting) return; // already stopping
  quitting = true;
  brain.stop().then(() => app.quit());
});
