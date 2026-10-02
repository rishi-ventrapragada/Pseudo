// M18: the face words every event exactly as the terminal does (pseudo_brain/terminal.py,
// format_event, minus the "---" around each line). The expected strings are the terminal's.
import { describe, expect, it } from 'vitest';
import { answerLabel, describeEvent } from './events';

describe('describeEvent', () => {
  it('words a model call like the terminal', () => {
    expect(describeEvent('sending', { call: 1, of: 6, messages: 2, tools: 3, estimate: 812, dropped_turns: 1,
                                      provider: 'groq', model: 'openai/gpt-oss-120b' }))
      .toBe('SENDING TO groq · openai/gpt-oss-120b (call 1 of max 6) | 2 messages + 3 tools, ~812 tokens | dropped 1 old turn(s) to fit');
    expect(describeEvent('tokens', { in: 900, out: 40, estimate: 812, budget_left: '7060', budget: '8000' }))
      .toBe('tokens: 900 in / 40 out (estimated ~812 in) | budget left this minute: 7060 of 8000');
    expect(describeEvent('tokens', { in: 900, out: 40, estimate: 812, budget_left: null, budget: null }))
      .toBe('tokens: 900 in / 40 out (estimated ~812 in) | no rate-limit info');
  });

  it('announces a fallback and a wait', () => {
    expect(describeEvent('fallback', { provider: 'groq', from: 'openai/gpt-oss-120b', to: 'openai/gpt-oss-20b' }))
      .toBe('RATE LIMITED (429) on openai/gpt-oss-120b: switching to openai/gpt-oss-20b (the next model of groq; never another provider)');
    expect(describeEvent('rate_limited', { seconds: 7.2, wait: 1, of: 3, provider: 'Groq', model: 'openai/gpt-oss-20b' }))
      .toBe('RATE LIMITED (429) on openai/gpt-oss-20b: waiting 7 s as Groq asked (wait 1 of 3)');
  });

  it('shows tools by name and results by size only', () => {
    expect(describeEvent('tool_call', { name: 'focus_window', arguments: '{"window_id":"w3"}' }))
      .toBe('MODEL WANTS TO CALL TOOL: focus_window {"window_id":"w3"}');
    expect(describeEvent('tool_call', { name: 'read_active_window', arguments: '' }))
      .toBe('MODEL WANTS TO CALL TOOL: read_active_window {}');
    expect(describeEvent('tool_result', { name: 'read_active_window', chars: 812, is_error: true }))
      .toBe('TOOL RESULT (ERROR): 812 chars, sent to the model, kept in memory only');
  });

  it('labels answers and failures', () => {
    const answer = { text: 'BLUE', calls: 2, tokens_in: 1700, tokens_out: 60, provider: 'groq', model: 'openai/gpt-oss-20b', fallback: true };
    expect(describeEvent('answer', answer))
      .toBe('ANSWER (groq · openai/gpt-oss-20b, fallback | 2 model call(s), 1700 tokens in / 60 out)');
    expect(answerLabel({ provider: 'local', model: 'granite4.1:3b', fallback: false })).toBe('local · granite4.1:3b');
    expect(describeEvent('failed', { reason: 'could not reach Groq' })).toBe('FAILED: could not reach Groq. No answer was produced.');
  });

  it("describes private mode's server", () => {
    expect(describeEvent('server_starting', { provider: 'local', address: '127.0.0.1:11434' }))
      .toBe('PRIVATE SERVER for local: checking cloud is off, then starting it on 127.0.0.1:11434');
    expect(describeEvent('server_ready', { started_by_us: true, seconds: 1.26, address: '127.0.0.1:11434' }))
      .toBe('SERVER READY on 127.0.0.1:11434 in 1.3 s (started by Pseudo; stopped when Pseudo exits)');
  });

  it('words memory events like the terminal (M24)', () => {
    expect(describeEvent('sending', { call: 1, of: 6, messages: 3, tools: 3, estimate: 950, dropped_turns: 0, memories: 2,
                                      provider: 'groq', model: 'openai/gpt-oss-120b' }))
      .toBe('SENDING TO groq · openai/gpt-oss-120b (call 1 of max 6) | 3 messages + 3 tools, ~950 tokens | 2 memory(ies)');
    expect(describeEvent('memories', { count: 2, chars: 500, note: '' }))
      .toBe('MEMORY: 2 past task(s) added to this question (500 chars, redacted)');
    expect(describeEvent('memories', { count: 0, chars: 0, note: 'no past task is relevant enough' }))
      .toBe('MEMORY: none added (no past task is relevant enough)');
    expect(describeEvent('tool_call', { name: 'save_memory', arguments: '{}', by: 'pseudo' }))
      .toBe('SAVING TO MEMORY: the approval popup asks you first (redacted; default no)');
    expect(describeEvent('tool_result', { name: 'save_memory', chars: 0, is_error: false, by: 'pseudo' })).toBeNull();
    expect(describeEvent('memory_saved', { note: '2026-10-02-120000-001.md' }))
      .toBe('MEMORY: saved this task, redacted, as 2026-10-02-120000-001.md');
    expect(describeEvent('memory_not_saved', { reason: "you didn't approve it" }))
      .toBe("MEMORY: not saved (you didn't approve it)");
  });

  it('shows nothing for an unknown event', () => {
    expect(describeEvent('something_new', {})).toBeNull();
  });
});
