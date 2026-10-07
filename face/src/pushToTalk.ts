// M26: the push-to-talk key: hold Ctrl+Space while the face is focused (D24). Pure functions, tested.
// Windows repeats keydown about 30 times a second while a key is held; only the first one starts.

type Key = Pick<KeyboardEvent, 'code' | 'key' | 'ctrlKey' | 'repeat'>;

/** Is this keydown part of Ctrl+Space? (Then the page must not type a space, even on repeats.) */
export function isTalkKey(event: Key): boolean {
  return event.code === 'Space' && event.ctrlKey;
}

/** Does this keydown START talking? Ctrl+Space, the first press only. */
export function startsTalking(event: Key): boolean {
  return isTalkKey(event) && !event.repeat;
}

/** Does this keyup STOP talking? Letting go of either Space or Ctrl. */
export function stopsTalking(event: Key): boolean {
  return event.code === 'Space' || event.key === 'Control';
}
