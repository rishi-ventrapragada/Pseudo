/**
 * M18: the preload script, the ONLY door between the page and the main process.
 *
 * It runs before the page, sandboxed, and gives the page exactly two functions, as window.pseudo:
 *   send(message)       only these message types get through; anything else stops here
 *   onMessage(callback) every message from the brain (plus brain_stopped from the main process)
 * The page never gets ipcRenderer itself (Electron's checklist): with it, the page could send anything.
 */

const { contextBridge, ipcRenderer } = require('electron');

// The same types are listed in to-brain.js (TO_BRAIN) and src/protocol.ts (ToBrain); message-types.test.mjs
// checks the three agree. (M32: `warm_sessions` was missing here at first, and the switch did nothing.)
const TYPES = ['ask', 'provider', 'new_session', 'list_sessions', 'open_session', 'restart',
               'transcribe', 'speak_answers', // M26: push-to-talk and the Speak answers switch
               'warm_sessions', // M32: the warm-session switch
               'autostart', // M36: the Start with Windows switch (answered by the main process)
               'window_mode', // M38: full or compact, and whether the bar shows an answer (answered by the main process)
               'search_sessions', 'rename_session', 'delete_session']; // M41: the sidebar's chats
let listener = null;
const early = []; // messages that arrived before the page started listening

ipcRenderer.on('pseudo:message', (_event, message) => {
  if (listener) listener(message);
  else early.push(message);
});

contextBridge.exposeInMainWorld('pseudo', {
  send(message) {
    if (message && TYPES.includes(message.type)) ipcRenderer.send('pseudo:send', message);
  },
  onMessage(callback) {
    listener = callback;
    early.splice(0).forEach(callback);
  },
});
