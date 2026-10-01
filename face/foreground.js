/**
 * M18: letting pseudo_hands' approval popup come to the front, above the face.
 *
 * What it demonstrates: Windows' foreground rules. Windows lets a program put a window in
 * front of the one you're using only if that program got your last input (or was just
 * started by the one that did). The popup comes from pseudo_hands, which started minutes
 * earlier, while your last keystroke went to the face, so Windows kept the popup BEHIND
 * the face, and it timed out as no (M18, V6).
 *
 * The fix: the face, the window you're using, passes that right on with Windows'
 * AllowSetForegroundWindow, and only to the ONE process the bridge named as pseudo_hands
 * (ready.hands_pid). Never to ASFW_ANY ("any process").
 *
 * When: on every tool_call event, right before the tool runs. Windows takes the right back at
 * your next input, so the first version, which granted when you pressed Ask, never worked
 * with Enter: the key's own key-up, a moment later, cancelled it (M18, V6).
 *
 * If anything is off (no pid yet, an odd pid, koffi can't load), nothing is granted. The
 * popup still appears, possibly behind the face, and still means no after 20 s (D13).
 * koffi is the npm package that lets JavaScript call a function in a Windows DLL.
 */

const ASFW_ANY = 0xffffffff; // Windows' "any process": never granted

/** A pid we may grant to: a whole number above 0 that isn't ASFW_ANY. */
function isProcessId(pid) {
  return Number.isInteger(pid) && pid > 0 && pid < ASFW_ANY;
}

class ForegroundGrant {
  /** @param {(pid: number) => boolean} allow Windows' AllowSetForegroundWindow (a fake in tests) */
  constructor(allow) {
    this.allow = allow;
    this.handsPid = null;
  }

  /** Every message from the brain passes here: `ready` names pseudo_hands' process, `tool_call` grants. */
  fromBrain(message) {
    if (message.type === 'ready') this.handsPid = isProcessId(message.hands_pid) ? message.hands_pid : null;
    else if (message.type === 'event' && message.kind === 'tool_call') this.grant();
  }

  /** The brain stopped, and its pseudo_hands with it: forget the pid. */
  brainStopped() {
    this.handsPid = null;
  }

  /** A tool is about to run: let pseudo_hands' process, and only it, bring its popup to the front. */
  grant() {
    if (this.handsPid === null) return false;
    return this.allow(this.handsPid) === true;
  }
}

/** The real AllowSetForegroundWindow from user32.dll, through koffi. Grants nothing if it can't load. */
function windowsAllow() {
  try {
    const koffi = require('koffi');
    const allowSetForegroundWindow = koffi
      .load('user32.dll')
      .func('int __stdcall AllowSetForegroundWindow(uint32_t dwProcessId)');
    return (pid) => allowSetForegroundWindow(pid) !== 0;
  } catch (error) {
    console.error(`[face] AllowSetForegroundWindow unavailable (${error.message}): popups may open behind the face`);
    return () => false;
  }
}

module.exports = { ASFW_ANY, ForegroundGrant, isProcessId, windowsAllow };
