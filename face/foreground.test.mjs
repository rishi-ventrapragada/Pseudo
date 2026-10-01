// M18: the face lets ONLY pseudo_hands' process (the pid the bridge reports in `ready`) bring the
// approval popup to the front, and only when you press Ask (foreground.js). `allow` is a fake here:
// it records every pid it's given, so these tests never touch Windows.
import { createRequire } from 'node:module';
import { describe, expect, it } from 'vitest';

const { ASFW_ANY, ForegroundGrant } = createRequire(import.meta.url)('./foreground.js');

function setup() {
  const granted = [];
  const grant = new ForegroundGrant((pid) => {
    granted.push(pid);
    return true;
  });
  return { grant, granted };
}

describe('ForegroundGrant', () => {
  it('grants only the pid from ready, once per Ask', () => {
    const { grant, granted } = setup();
    grant.fromBrain({ type: 'ready', hands_pid: 4321, tools: [] });
    expect(grant.onAsk()).toBe(true);
    grant.onAsk();
    expect(granted).toEqual([4321, 4321]);
  });

  it('grants nothing before ready, or after the brain stops', () => {
    const { grant, granted } = setup();
    expect(grant.onAsk()).toBe(false);
    grant.fromBrain({ type: 'ready', hands_pid: 4321 });
    grant.brainStopped();
    expect(grant.onAsk()).toBe(false);
    expect(granted).toEqual([]);
  });

  it('never grants ASFW_ANY or anything that is not a real pid', () => {
    for (const odd of [ASFW_ANY, -1, 0, 1.5, '4321', null, undefined, 2 ** 40]) {
      const { grant, granted } = setup();
      grant.fromBrain({ type: 'ready', hands_pid: odd });
      expect(grant.onAsk()).toBe(false);
      expect(granted).toEqual([]);
    }
  });

  it('only ready can set the pid; a later ready replaces it', () => {
    const { grant, granted } = setup();
    grant.fromBrain({ type: 'ready', hands_pid: 4321 });
    grant.fromBrain({ type: 'event', kind: 'answer', data: {}, hands_pid: 999 });
    grant.fromBrain({ type: 'switched', hands_pid: 998 });
    grant.onAsk();
    grant.brainStopped();
    grant.fromBrain({ type: 'ready', hands_pid: 5555 }); // the brain was restarted
    grant.onAsk();
    expect(granted).toEqual([4321, 5555]);
  });
});
