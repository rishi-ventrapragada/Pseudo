// M18: the face lets ONLY pseudo_hands' process (the pid the bridge reports in `ready`) bring the
// approval popup to the front, right before each tool runs (foreground.js). `allow` is a fake here:
// it records every pid it's given, so these tests never touch Windows.
import { createRequire } from 'node:module';
import { describe, expect, it } from 'vitest';

const { ASFW_ANY, ForegroundGrant } = createRequire(import.meta.url)('./foreground.js');

const toolCall = { type: 'event', kind: 'tool_call', data: { name: 'focus_window', arguments: '{}' } };

function setup() {
  const granted = [];
  const grant = new ForegroundGrant((pid) => {
    granted.push(pid);
    return true;
  });
  return { grant, granted };
}

describe('ForegroundGrant', () => {
  it('grants only the pid from ready, once per tool_call', () => {
    const { grant, granted } = setup();
    grant.fromBrain({ type: 'ready', hands_pid: 4321, tools: [] });
    grant.fromBrain(toolCall);
    grant.fromBrain(toolCall);
    expect(granted).toEqual([4321, 4321]);
  });

  it('grants on nothing but a tool_call', () => {
    const { grant, granted } = setup();
    grant.fromBrain({ type: 'ready', hands_pid: 4321 });
    for (const kind of ['sending', 'tokens', 'tool_result', 'answer', 'failed']) {
      grant.fromBrain({ type: 'event', kind, data: {} });
    }
    grant.fromBrain({ type: 'turn_done', ok: true });
    expect(granted).toEqual([]);
  });

  it('grants nothing before ready, or after the brain stops', () => {
    const { grant, granted } = setup();
    grant.fromBrain(toolCall);
    grant.fromBrain({ type: 'ready', hands_pid: 4321 });
    grant.brainStopped();
    grant.fromBrain(toolCall);
    expect(granted).toEqual([]);
  });

  it('never grants ASFW_ANY or anything that is not a real pid', () => {
    for (const odd of [ASFW_ANY, -1, 0, 1.5, '4321', null, undefined, 2 ** 40]) {
      const { grant, granted } = setup();
      grant.fromBrain({ type: 'ready', hands_pid: odd });
      grant.fromBrain(toolCall);
      expect(granted).toEqual([]);
    }
  });

  it('only ready can set the pid; a later ready replaces it', () => {
    const { grant, granted } = setup();
    grant.fromBrain({ type: 'ready', hands_pid: 4321 });
    grant.fromBrain({ ...toolCall, hands_pid: 999 });
    grant.fromBrain({ type: 'switched', hands_pid: 998 });
    grant.brainStopped();
    grant.fromBrain({ type: 'ready', hands_pid: 5555 }); // the brain was restarted
    grant.fromBrain(toolCall);
    expect(granted).toEqual([4321, 5555]);
  });
});
