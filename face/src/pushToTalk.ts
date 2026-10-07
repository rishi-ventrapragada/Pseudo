// M26: the push-to-talk key: hold Ctrl+Space while the face is focused (D24). Pure functions, tested.
// Windows repeats keydown about 30 times a second while a key is held; only the first one starts.

type Key = Pick<KeyboardEvent, 'code' | 'key' | 'ctrlKey' | 'altKey' | 'repeat'>;

/** Is this keydown part of Ctrl+Space? (Then the page must not type a space, even on repeats.)
 *  (M37) Not with Alt: Ctrl+Alt+Space is the global show-or-hide shortcut. It normally never reaches the
 *  page, but if another program holds it, pressing it here must not start a recording. */
export function isTalkKey(event: Key): boolean {
  return event.code === 'Space' && event.ctrlKey && !event.altKey;
}

/** Does this keydown START talking? Ctrl+Space, the first press only. */
export function startsTalking(event: Key): boolean {
  return isTalkKey(event) && !event.repeat;
}

/** Does this keyup STOP talking? Letting go of either Space or Ctrl. */
export function stopsTalking(event: Key): boolean {
  return event.code === 'Space' || event.key === 'Control';
}
