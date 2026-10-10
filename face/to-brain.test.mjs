// M37: what the page may send to the brain (to-brain.js). The code moved out of main.js unchanged; it had
// no tests of its own there, because main.js needs Electron to load.
import { createRequire } from 'node:module';
import { describe, expect, it } from 'vitest';

const { MAX_AUDIO_CHARS, TO_BRAIN, cleanForBrain } = createRequire(import.meta.url)('./to-brain.js');

describe('cleanForBrain', () => {
  it('passes a question on with only its text', () => {
    expect(cleanForBrain({ type: 'ask', text: 'what is on my screen?', extra: 'x', on: true }))
      .toEqual({ type: 'ask', text: 'what is on my screen?' });
  });

  it('drops anything that is not a known message', () => {
    for (const bad of [null, undefined, 'ask', 7, [], {}, { type: 'shutdown' }, { type: 'restart' }, { type: 'autostart', on: true }]) {
      expect(cleanForBrain(bad), JSON.stringify(bad)).toBeNull();
    }
  });

  it('keeps only text fields that are text', () => {
    expect(cleanForBrain({ type: 'provider', id: 'groq', name: 5, text: { a: 1 } })).toEqual({ type: 'provider', id: 'groq' });
    expect(cleanForBrain({ type: 'open_session', name: '2026-10-01 10.00.00' })).toEqual({ type: 'open_session', name: '2026-10-01 10.00.00' });
  });

  it('a switch must carry a real true or false', () => {
    expect(cleanForBrain({ type: 'speak_answers', on: false })).toEqual({ type: 'speak_answers', on: false });
    expect(cleanForBrain({ type: 'warm_sessions', on: true })).toEqual({ type: 'warm_sessions', on: true });
    expect(cleanForBrain({ type: 'warm_sessions', on: 'yes' })).toBeNull();
    expect(cleanForBrain({ type: 'speak_answers' })).toBeNull();
  });

  it('`on` is carried by switches only', () => {
    expect(cleanForBrain({ type: 'new_session', on: true })).toEqual({ type: 'new_session' });
  });

  it('a recording must be text and not longer than 30 seconds can be', () => {
    expect(cleanForBrain({ type: 'transcribe', audio: 'AAAA' })).toEqual({ type: 'transcribe', audio: 'AAAA' });
    expect(cleanForBrain({ type: 'transcribe' })).toBeNull();
    expect(cleanForBrain({ type: 'transcribe', audio: 12 })).toBeNull();
    expect(cleanForBrain({ type: 'transcribe', audio: 'A'.repeat(MAX_AUDIO_CHARS) })).not.toBeNull();
    expect(cleanForBrain({ type: 'transcribe', audio: 'A'.repeat(MAX_AUDIO_CHARS + 1) })).toBeNull();
  });

  it('audio is carried by a recording only', () => {
    expect(cleanForBrain({ type: 'ask', text: 'hi', audio: 'AAAA' })).toEqual({ type: 'ask', text: 'hi' });
  });

  it('the list holds the fourteen messages the brain knows', () => {
    expect([...TO_BRAIN].sort()).toEqual(['ask', 'delete_session', 'list_memories', 'list_sessions', 'look',
                                          'new_session', 'open_memory', 'open_session', 'provider', 'rename_session',
                                          'search_sessions', 'speak_answers', 'transcribe', 'warm_sessions']);
  });

  it('M42: opening a memory carries its name as text, and nothing else; look and the list carry nothing', () => {
    expect(cleanForBrain({ type: 'open_memory', name: '2026-10-07-101500-123.md', path: 'C:\\x', title: 7 }))
      .toEqual({ type: 'open_memory', name: '2026-10-07-101500-123.md' });
    expect(cleanForBrain({ type: 'look', name: { not: 'text' } })).toEqual({ type: 'look' });
    expect(cleanForBrain({ type: 'list_memories', folder: '..' })).toEqual({ type: 'list_memories' });
  });

  it('M41: a rename carries its name and title as text, and nothing else', () => {
    expect(cleanForBrain({ type: 'rename_session', name: '20261010-091500-123', title: 'Booking form', path: 'C:\\x' }))
      .toEqual({ type: 'rename_session', name: '20261010-091500-123', title: 'Booking form' });
    expect(cleanForBrain({ type: 'rename_session', name: '20261010-091500-123', title: ['x'] }))
      .toEqual({ type: 'rename_session', name: '20261010-091500-123' }); // the brain refuses a missing title
    expect(cleanForBrain({ type: 'delete_session', name: '20261010-091500-123', title: 'x' }))
      .toEqual({ type: 'delete_session', name: '20261010-091500-123', title: 'x' }); // the brain reads only the name
  });
});
