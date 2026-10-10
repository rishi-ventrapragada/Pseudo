// M40: one brain event -> one step of "what Pseudo did", in plain words (from the Phase 10 mockup).
// The terminal keeps its own wording (pseudo_brain/terminal.py); the window speaks to a person. Each step is a
// short label and a quieter detail: "Asked groq · openai/gpt-oss-120b, call 1 of 6". Like events.ts before it,
// it shows sizes and names, never a tool result's text (that never reaches the page).
// D28: who answered, and any fallback, are here, in the "Answered" step, not on the answer itself.
// tests/test_face_wording.py checks that every event the brain sends has a case below.

import type { EventData } from './protocol';

export type Step = { label: string; detail?: string };

const n = (value: unknown) => Number(value ?? 0).toLocaleString('en-US');

/** "groq · openai/gpt-oss-120b", plus ", fallback" when the answer came from a fallback model. */
export function answerLabel(data: EventData): string {
  return `${data.provider} · ${data.model}` + (data.fallback ? ', fallback' : '');
}

// M30: two brains can answer. The action brain's id is the start of its label, live or saved.
export const ACTION_BRAIN = 'claude-code';

/** Which brain a label names: 'action' (Claude Code, D26) or 'chat' (the provider). */
export function brainOf(label: string | undefined): 'action' | 'chat' {
  return (label ?? '').startsWith(ACTION_BRAIN) ? 'action' : 'chat';
}

/** Who answered, for people: "Claude Code · sonnet (your subscription)" or "groq · gpt-oss-20b (fallback model)". */
export function who(label: string): string {
  const FALLBACK = /(, fallback| \(fallback\))$/; // live answers say ", fallback"; saved sessions " (fallback)"
  const plain = label.replace(FALLBACK, '');
  if (brainOf(plain) === 'action') return `Claude Code · ${plain.split(' · ').slice(1).join(' · ')} (your subscription)`;
  return plain + (FALLBACK.test(label) ? ' (fallback model)' : '');
}

const ACTIONS: Record<string, string> = {
  press: 'press a control', set_text: "replace a field's text", insert_text: 'add text to a field',
  toggle: 'tick or untick a box', select: 'select an item', choose: 'choose an option', open: 'open a control',
};

function toolStep(data: EventData): Step {
  const name = String(data.name ?? '');
  const asks = data.asks === false ? undefined : 'asks your approval in a popup';
  if (data.by === 'pseudo') return { label: 'Offered this task to memory', detail: 'the popup asks you first; no answer means no' };
  if (name === 'read_active_window') return { label: 'Read the window you were on' };
  if (name === 'list_open_windows') return { label: 'Listed your open windows' };
  if (name === 'focus_window') return { label: 'Asked to switch to a window', detail: asks };
  if (name === 'act_on_control') {
    let action = '';
    try { action = String(JSON.parse(data.arguments || '{}').action ?? ''); } catch { /* not JSON: say it generally */ }
    return { label: `Asked to ${ACTIONS[action] ?? 'act on a control'}`, detail: asks };
  }
  return { label: `Used the ${name} tool`, detail: asks };
}

export function describeStep(kind: string, data: EventData): Step | null {
  switch (kind) {
    case 'memories': { // M42: which ones joined, by their (redacted) titles
      const which = Array.isArray(data.titles) && data.titles.length
        ? `: ${data.titles.map((title: unknown) => `“${String(title)}”`).join(', ')}` : `, ${n(data.chars)} characters, redacted`;
      return { label: 'Searched your memory', detail: data.count ? `${data.count} past task(s) added${which}` : data.note || 'nothing relevant' };
    }
    case 'sending': {
      const extra = (data.memories ? `, with ${data.memories} memory(ies)` : '')
        + (data.dropped_turns ? `, ${data.dropped_turns} old turn(s) left out to fit` : '');
      return { label: `Asked ${data.provider} · ${data.model}`, detail: `call ${data.call} of ${data.of}, about ${n(data.estimate)} tokens${extra}` };
    }
    case 'tokens':
      return { label: 'Tokens used', detail: `${n(data.in)} in, ${n(data.out)} out` + (data.budget_left
        ? `; budget left this minute: ${n(data.budget_left)} of ${data.budget ? n(data.budget) : '?'}` : '') };
    case 'fallback':
      return { label: 'Rate limited: switched to the next model',
               detail: `${data.from} → ${data.to}, still ${data.provider} (never another provider)` };
    case 'rate_limited':
      return { label: `Rate limited: waited ${Number(data.seconds).toFixed(0)} s`,
               detail: `${data.model}, as ${data.provider} asked (wait ${data.wait} of ${data.of})` };
    case 'routed':
      return { label: `Sent to ${data.name}, as an action request`, detail: `${data.model}. ${data.privacy}` };
    case 'billing':
      return { label: data.clean ? 'Billing check: clean' : 'Billing check: not clean, so nothing was sent',
               detail: String(data.line ?? '').split(' | ').slice(1).join(', ') || undefined };
    case 'launch':
      return { label: 'Started Claude Code for this request', detail: data.why };
    case 'warm':
      return { label: 'Used the open Claude Code session', detail: `request ${data.request} of ${data.of}` };
    case 'warm_restart':
      return { label: 'The Claude Code session restarts after this request', detail: data.why };
    case 'warm_opened':
      return data.opened ? { label: 'Opened a Claude Code session for your next action requests', detail: `restarted after ${data.of} requests` }
                         : { label: 'No Claude Code session was opened', detail: data.why };
    case 'model_retry':
      return { label: 'The model wrote a broken tool call', detail: 'asked it again' };
    case 'tool_call':
      return toolStep(data);
    case 'tool_result':
      if (data.by === 'pseudo') return null; // memory_saved / memory_not_saved says how it went
      return { label: data.is_error ? 'The tool reported an error' : 'Got the result',
               detail: `${n(data.chars)} characters` + (data.masked ? `, ${n(data.masked)} item(s) masked` : '') // M42
                 + ', sent to the model, kept in memory only' };
    case 'answer':
      return { label: 'Answered', detail: `${who(answerLabel(data))}, ${data.calls} call(s), ${n(data.tokens_in)} tokens in, ${n(data.tokens_out)} out` };
    case 'failed':
      return { label: 'No answer', detail: data.reason };
    case 'memory_saved':
      return { label: 'Saved this task to memory', detail: `redacted, as ${data.note}` };
    case 'memory_not_saved':
      return { label: 'Not saved to memory', detail: data.reason };
    case 'server_starting':
      return { label: "Starting private mode's server", detail: `${data.provider}: checking its cloud is off, on ${data.address}` };
    case 'server_ready':
      return data.started_by_us
        ? { label: "Private mode's server is ready", detail: `${data.address}, in ${Number(data.seconds).toFixed(1)} s; stopped when Pseudo quits` }
        : { label: "Private mode's server was already running", detail: `${data.address}; Pseudo didn't start it, so it won't stop it` };
    case 'hands_pid': // for the main process only (foreground.js)
    default:
      return null;
  }
}
