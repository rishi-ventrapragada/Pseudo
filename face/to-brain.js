/**
 * M37 (moved out of main.js, unchanged): which messages from the page may reach the brain, and in what shape.
 *
 * What it demonstrates: never pass input along as it arrived. The page is sandboxed, but
 * the main process still treats what it sends as untrusted: a message is REBUILT from the
 * few fields it is allowed to have, so an extra field, a wrong type or an unknown message
 * type simply doesn't exist on the other side. (The same idea as validating a request body
 * on the server even though your own front end sent it.)
 *
 * The same types are listed in preload.js (TYPES) and src/protocol.ts (ToBrain);
 * message-types.test.mjs checks that the three agree.
 */

const TO_BRAIN = new Set(['ask', 'provider', 'new_session', 'list_sessions', 'open_session', 'transcribe',
                          'speak_answers', 'warm_sessions']);
const SWITCHES = new Set(['speak_answers', 'warm_sessions']); // M26, M32: each carries one true/false, `on`
const FIELDS = ['text', 'id', 'name']; // the only text fields a message to the brain may carry
// M26: a push-to-talk recording, base64. 30.5 s of 16 kHz 16-bit mono is about 1.3 million characters;
// anything bigger is dropped here, and the brain checks the length again (voice_in.py).
const MAX_AUDIO_CHARS = 1400000;

/**
 * @param {unknown} message what the page sent
 * @returns {object | null} the message the brain gets, or null: it is dropped
 */
function cleanForBrain(message) {
  if (typeof message !== 'object' || message === null || !TO_BRAIN.has(message.type)) return null;
  const clean = { type: message.type };
  for (const field of FIELDS) {
    if (typeof message[field] === 'string') clean[field] = message[field];
  }
  if (message.type === 'transcribe') {
    if (typeof message.audio !== 'string' || message.audio.length > MAX_AUDIO_CHARS) return null;
    clean.audio = message.audio;
  }
  if (SWITCHES.has(message.type)) {
    if (typeof message.on !== 'boolean') return null;
    clean.on = message.on;
  }
  return clean;
}

module.exports = { MAX_AUDIO_CHARS, TO_BRAIN, cleanForBrain };
