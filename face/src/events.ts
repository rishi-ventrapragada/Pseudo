// M18: one loop event -> one line of text, worded exactly as the terminal prints it
// (format_event in pseudo_brain/terminal.py), without the "---" around it. So the face and
// the terminal tell you the same story: which provider and model, the tokens, 429s, fallbacks,
// the tools called and the SIZE of each result. Never a tool result's text: that isn't sent here.
// M24: memory events too: how many past tasks joined a question, and whether this one was saved.

import type { EventData } from './protocol';

/** "groq · openai/gpt-oss-120b", plus ", fallback" when the answer came from a fallback model. */
export function answerLabel(data: EventData): string {
  return `${data.provider} · ${data.model}` + (data.fallback ? ', fallback' : '');
}

// M30: two brains can answer. The action brain's id is the start of its label, live or saved.
export const ACTION_BRAIN = 'claude-code';

/** Which brain a label names: 'action' (Claude Code, D26) or 'chat' (the provider in the bar). */
export function brainOf(label: string | undefined): 'action' | 'chat' {
  return (label ?? '').startsWith(ACTION_BRAIN) ? 'action' : 'chat';
}

export function describeEvent(kind: string, data: EventData): string | null {
  switch (kind) {
    case 'sending': {
      const trimmed = data.dropped_turns ? ` | dropped ${data.dropped_turns} old turn(s) to fit` : '';
      const memories = data.memories ? ` | ${data.memories} memory(ies)` : '';
      return (
        `SENDING TO ${data.provider} · ${data.model} (call ${data.call} of max ${data.of}) | ` +
        `${data.messages} messages + ${data.tools} tools, ~${data.estimate} tokens${memories}${trimmed}`
      );
    }
    case 'tokens': {
      const budget = data.budget_left
        ? `budget left this minute: ${data.budget_left} of ${data.budget || '?'}`
        : 'no rate-limit info';
      return `tokens: ${data.in} in / ${data.out} out (estimated ~${data.estimate} in) | ${budget}`;
    }
    case 'fallback':
      return (
        `RATE LIMITED (429) on ${data.from}: switching to ${data.to} ` +
        `(the next model of ${data.provider}; never another provider)`
      );
    case 'rate_limited':
      return (
        `RATE LIMITED (429) on ${data.model}: waiting ${Number(data.seconds).toFixed(0)} s as ${data.provider} ` +
        `asked (wait ${data.wait} of ${data.of})`
      );
    case 'routed': // M30
      return `ACTION REQUEST: going to ${data.name} (${data.model}), not the chat provider | ${data.privacy}`;
    case 'billing': // M30: names and booleans only
      return String(data.line);
    case 'launch': // M32: the four steps of the warm session's rules (pseudo_brain/warm_sessions.py)
      return `LAUNCH: starting Claude Code for this request (${data.why})`;
    case 'warm':
      return `WARM SESSION: request ${data.request} of ${data.of} in the open Claude Code session`;
    case 'warm_restart':
      return `WARM SESSION: restarting it after this request (${data.why})`;
    case 'warm_opened':
      return data.opened
        ? `WARM SESSION: opened for your next action requests (restarted after ${data.of})`
        : `WARM SESSION: not opened (${data.why})`;
    case 'model_retry':
      return 'MODEL WROTE AN INVALID TOOL CALL (400): asking again';
    case 'tool_call':
      if (data.by === 'pseudo') return 'SAVING TO MEMORY: the approval popup asks you first (redacted; default no)';
      return `MODEL WANTS TO CALL TOOL: ${data.name} ${data.arguments || '{}'}`;
    case 'tool_result':
      if (data.by === 'pseudo') return null; // memory_saved / memory_not_saved says how it went
      return `TOOL RESULT${data.is_error ? ' (ERROR)' : ''}: ${data.chars} chars, sent to the model, kept in memory only`;
    case 'answer':
      return (
        `ANSWER (${answerLabel(data)} | ${data.calls} model call(s), ` +
        `${data.tokens_in} tokens in / ${data.tokens_out} out)`
      );
    case 'failed':
      return `FAILED: ${data.reason}. No answer was produced.`;
    case 'memories':
      return data.count
        ? `MEMORY: ${data.count} past task(s) added to this question (${data.chars} chars, redacted)`
        : `MEMORY: none added (${data.note})`;
    case 'memory_saved':
      return `MEMORY: saved this task, redacted, as ${data.note}`;
    case 'memory_not_saved':
      return `MEMORY: not saved (${data.reason})`;
    case 'server_starting':
      return `PRIVATE SERVER for ${data.provider}: checking cloud is off, then starting it on ${data.address}`;
    case 'server_ready':
      return data.started_by_us
        ? `SERVER READY on ${data.address} in ${Number(data.seconds).toFixed(1)} s (started by Pseudo; stopped when Pseudo exits)`
        : `SERVER FOUND on ${data.address}: already running, not started by Pseudo, so Pseudo won't stop it`;
    default:
      return null;
  }
}
