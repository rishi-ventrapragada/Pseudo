// M40: the steps of "what Pseudo did", in plain words (steps.ts). All data is fake.
import { describe, expect, it } from 'vitest';
import { answerLabel, brainOf, describeStep, who } from './steps';

describe('describeStep', () => {
  it('a model call and its tokens', () => {
    expect(describeStep('sending', { call: 1, of: 6, messages: 2, tools: 3, estimate: 812, dropped_turns: 0, memories: 2,
                                     provider: 'groq', model: 'openai/gpt-oss-120b' }))
      .toEqual({ label: 'Asked groq · openai/gpt-oss-120b', detail: 'call 1 of 6, about 812 tokens, with 2 memory(ies)' });
    expect(describeStep('tokens', { in: 1644, out: 40, budget_left: '6862', budget: '8000' }))
      .toEqual({ label: 'Tokens used', detail: '1,644 in, 40 out; budget left this minute: 6,862 of 8,000' });
    expect(describeStep('tokens', { in: 9, out: 1, budget_left: null })?.detail).toBe('9 in, 1 out');
  });

  it('a fallback and a wait are said, with the model each time', () => {
    expect(describeStep('fallback', { provider: 'groq', from: 'openai/gpt-oss-120b', to: 'openai/gpt-oss-20b' })?.detail)
      .toBe('openai/gpt-oss-120b → openai/gpt-oss-20b, still groq (never another provider)');
    expect(describeStep('rate_limited', { seconds: 7.2, wait: 1, of: 3, provider: 'Groq', model: 'openai/gpt-oss-20b' })?.label)
      .toBe('Rate limited: waited 7 s');
  });

  it('tools by what they do, and whether they ask in a popup', () => {
    expect(describeStep('tool_call', { name: 'read_active_window', arguments: '{}', asks: false }))
      .toEqual({ label: 'Read the window you were on' });
    expect(describeStep('tool_call', { name: 'focus_window', arguments: '{"window_id":"w3"}', asks: true }))
      .toEqual({ label: 'Asked to switch to a window', detail: 'asks your approval in a popup' });
    expect(describeStep('tool_call', { name: 'act_on_control', arguments: '{"control_id":"c9","action":"toggle"}', asks: true })?.label)
      .toBe('Asked to tick or untick a box');
    expect(describeStep('tool_call', { name: 'act_on_control', arguments: 'not json', asks: true })?.label).toBe('Asked to act on a control');
    expect(describeStep('tool_call', { name: 'new_tool', arguments: '{}' })).toEqual({ label: 'Used the new_tool tool',
                                                                                        detail: 'asks your approval in a popup' });
    expect(describeStep('tool_result', { name: 'read_active_window', chars: 1180, is_error: false }))
      .toEqual({ label: 'Got the result', detail: '1,180 characters, sent to the model, kept in memory only' });
  });

  it('who answered is in the "Answered" step, with a fallback said', () => {
    expect(describeStep('answer', { calls: 2, tokens_in: 1644, tokens_out: 112, provider: 'groq', model: 'openai/gpt-oss-20b', fallback: true }))
      .toEqual({ label: 'Answered', detail: 'groq · openai/gpt-oss-20b (fallback model), 2 call(s), 1,644 tokens in, 112 out' });
    expect(describeStep('answer', { calls: 3, tokens_in: 10, tokens_out: 5, provider: 'claude-code', model: 'claude-sonnet-5-5', fallback: false })?.detail)
      .toBe('Claude Code · claude-sonnet-5-5 (your subscription), 3 call(s), 10 tokens in, 5 out');
    expect(describeStep('failed', { reason: 'could not reach Groq' })).toEqual({ label: 'No answer', detail: 'could not reach Groq' });
  });

  it('an action request: the route, the billing check (names and booleans only), and the session', () => {
    expect(describeStep('routed', { name: 'Claude Code', model: 'sonnet', privacy: 'Fake note.' }))
      .toEqual({ label: 'Sent to Claude Code, as an action request', detail: 'sonnet. Fake note.' });
    expect(describeStep('billing', { clean: true, line: 'billing check: CLEAN | outranking credentials set: none | your account: True' }))
      .toEqual({ label: 'Billing check: clean', detail: 'outranking credentials set: none, your account: True' });
    expect(describeStep('billing', { clean: false, line: 'x' })?.label).toBe('Billing check: not clean, so nothing was sent');
    expect(describeStep('warm', { request: 3, of: 6 })?.detail).toBe('request 3 of 6');
    expect(describeStep('warm_opened', { opened: false, why: "the billing check wasn't clean" })?.detail).toBe("the billing check wasn't clean");
  });

  it('memory: what joined the question, and the save', () => {
    expect(describeStep('memories', { count: 0, chars: 0, note: '' })).toEqual({ label: 'Searched your memory', detail: 'nothing relevant' });
    expect(describeStep('memories', { count: 2, chars: 500, note: '' })?.detail).toBe('2 past task(s) added, 500 characters, redacted');
    expect(describeStep('tool_call', { name: 'save_memory', by: 'pseudo', asks: true })?.label).toBe('Offered this task to memory');
    expect(describeStep('tool_result', { name: 'save_memory', by: 'pseudo' })).toBeNull();
    expect(describeStep('memory_saved', { note: '2026-10-02-120000-001.md' })?.detail).toBe('redacted, as 2026-10-02-120000-001.md');
  });

  it("the main process's own event, and an unknown one, show nothing", () => {
    expect(describeStep('hands_pid', { pid: 7777 })).toBeNull();
    expect(describeStep('something_new', {})).toBeNull();
  });
});

describe('who answered', () => {
  it('reads a live or a saved label', () => {
    expect(answerLabel({ provider: 'local', model: 'granite4.1:3b', fallback: false })).toBe('local · granite4.1:3b');
    expect(who('groq · openai/gpt-oss-20b (fallback)')).toBe('groq · openai/gpt-oss-20b (fallback model)');
    expect(who('claude-code · claude-sonnet-5-5')).toBe('Claude Code · claude-sonnet-5-5 (your subscription)');
    expect(brainOf('claude-code · x')).toBe('action');
    expect(brainOf(undefined)).toBe('chat');
  });
});
