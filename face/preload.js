/**
 * M18: the preload script, the ONLY door between the page and the main process.
 *
 * It runs before the page, sandboxed, and gives the page exactly two functions, as window.pseudo:
 *   send(message)       only these message types get through; anything else stops here
 *   onMessage(callback) every message from the brain (plus brain_stopped from the main process)
 * The page never gets ipcRenderer itself (Electron's checklist): with it, the page could send anything.
 */

const { contextBridge, ipcRenderer } = require('electron');

const TYPES = ['ask', 'provider', 'new_session', 'list_sessions', 'open_session', 'restart',
               'transcribe', 'speak_answers']; // M26: push-to-talk and the Speak answers switch
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
