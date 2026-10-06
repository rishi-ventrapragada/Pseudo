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

  it("M30: during an action request, grants Claude Code's pseudo_hands instead, until the turn is done", () => {
    const { grant, granted } = setup();
    grant.fromBrain({ type: 'ready', hands_pid: 4321 });
    grant.fromBrain({ type: 'event', kind: 'hands_pid', data: { pid: 7777 } });
    grant.fromBrain(toolCall);
    grant.fromBrain({ type: 'turn_done', ok: true });
    grant.fromBrain(toolCall); // the next question is Groq's again
    expect(granted).toEqual([7777, 4321]);
  });

  it('M30: an uncertain or odd action pid grants nothing new', () => {
    const { grant, granted } = setup();
    grant.fromBrain({ type: 'ready', hands_pid: 4321 });
    for (const pid of [null, 0, -5, 1.5, '7777', ASFW_ANY]) {
      grant.fromBrain({ type: 'event', kind: 'hands_pid', data: { pid } });
      grant.fromBrain(toolCall);
    }
    expect(granted).toEqual([4321, 4321, 4321, 4321, 4321, 4321]);
  });

  it("M32: a warm session's pseudo_hands is named again by every request, and only for that request", () => {
    const { grant, granted } = setup();
    const warmRequest = () => {
      grant.fromBrain({ type: 'event', kind: 'hands_pid', data: { pid: 7777 } }); // the same process each time
      grant.fromBrain(toolCall);
      grant.fromBrain({ type: 'turn_done', ok: true });
    };
    grant.fromBrain({ type: 'ready', hands_pid: 4321 });
    warmRequest();
    grant.fromBrain(toolCall); // a Groq question in between: the brain's own pseudo_hands
    grant.fromBrain({ type: 'turn_done', ok: true });
    warmRequest();
    grant.fromBrain({ type: 'warm', on: true, open: true, ram_mb: 350, asked: 2, of: 6, idle_minutes: 10, note: '' });
    grant.fromBrain(toolCall); // the session's state is not a grant, and names no process
    expect(granted).toEqual([7777, 4321, 7777, 4321]);
  });

  it("M30: Pseudo's own memory popup is granted to the brain's pseudo_hands, even during an action request", () => {
    const { grant, granted } = setup();
    grant.fromBrain({ type: 'ready', hands_pid: 4321 });
    grant.fromBrain({ type: 'event', kind: 'hands_pid', data: { pid: 7777 } });
    grant.fromBrain(toolCall);
    grant.fromBrain({ type: 'event', kind: 'tool_call', data: { name: 'save_memory', arguments: '{}', by: 'pseudo' } });
    expect(granted).toEqual([7777, 4321]);
  });
});
