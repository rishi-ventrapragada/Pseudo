// M18: the face flashes its taskbar button while a tool waits for its result, but only if you're
// in another window (taskbar-flash.js). `flash` and `isFocused` are fakes: no window is touched.
import { createRequire } from 'node:module';
import { describe, expect, it } from 'vitest';

const { TaskbarFlash } = createRequire(import.meta.url)('./taskbar-flash.js');

const toolCall = { type: 'event', kind: 'tool_call', data: { name: 'focus_window', arguments: '{}' } };
const toolResult = { type: 'event', kind: 'tool_result', data: { name: 'focus_window', chars: 40 } };

function setup(focused) {
  const calls = [];
  const flash = new TaskbarFlash((on) => calls.push(on), () => focused.now);
  return { flash, calls };
}

describe('TaskbarFlash', () => {
  it('flashes while a tool waits, if you are in another window, and stops at its result', () => {
    const { flash, calls } = setup({ now: false });
    flash.fromBrain(toolCall);
    expect(calls).toEqual([true]);
    flash.fromBrain(toolResult);
    expect(calls).toEqual([true, false]);
  });

  it('does not flash when the face is the window you are using', () => {
    const { flash, calls } = setup({ now: true });
    flash.fromBrain(toolCall);
    flash.fromBrain(toolResult);
    expect(calls).toEqual([]); // and never stops a flash it didn't start
  });

  it('stops at turn_done or when the brain stops, even without a tool result', () => {
    for (const end of [(f) => f.fromBrain({ type: 'turn_done', ok: false }), (f) => f.brainStopped()]) {
      const { flash, calls } = setup({ now: false });
      flash.fromBrain(toolCall);
      end(flash);
      expect(calls).toEqual([true, false]);
    }
  });

  it('only a tool_call starts it', () => {
    const { flash, calls } = setup({ now: false });
    for (const kind of ['sending', 'tokens', 'answer', 'failed', 'server_starting']) {
      flash.fromBrain({ type: 'event', kind, data: {} });
    }
    flash.fromBrain({ type: 'ready', hands_pid: 4321 });
    expect(calls).toEqual([]);
  });
});
