// M36: showing the window and the lazy brain start (reveal.js). The window is a fake that records what
// was done to it, and "the brain" is a counter.
import { createRequire } from 'node:module';
import { describe, expect, it } from 'vitest';

const { Reveal } = createRequire(import.meta.url)('./reveal.js');

function fakeWindow({ minimized = false, destroyed = false } = {}) {
  const done = [];
  return {
    isDestroyed: () => destroyed,
    isMinimized: () => minimized,
    restore: () => done.push('restore'),
    show: () => done.push('show'),
    focus: () => done.push('focus'),
    done,
  };
}

function setup(win) {
  const brain = { starts: 0 };
  const holder = { win };
  const reveal = new Reveal(() => holder.win, () => { brain.starts += 1; });
  return { reveal, brain, holder };
}

describe('Reveal', () => {
  it('a hidden start: nothing starts the brain until the window is shown', () => {
    const { reveal, brain } = setup(fakeWindow());
    expect(brain.starts).toBe(0);
    expect(reveal.show()).toBe(true);
    expect(brain.starts).toBe(1);
  });

  it('shows and focuses the window, restoring it first if minimized', () => {
    const plain = fakeWindow();
    setup(plain).reveal.show();
    expect(plain.done).toEqual(['show', 'focus']);
    const small = fakeWindow({ minimized: true });
    setup(small).reveal.show();
    expect(small.done).toEqual(['restore', 'show', 'focus']);
  });

  it('the brain is started once, however often the window is shown', () => {
    const { reveal, brain } = setup(fakeWindow());
    reveal.show();
    reveal.show();
    reveal.show();
    expect(brain.starts).toBe(1);
  });

  it('opened by hand: the brain starts at launch, and showing the window never starts a second one', () => {
    const { reveal, brain } = setup(fakeWindow());
    reveal.startBrain();
    reveal.show();
    expect(brain.starts).toBe(1);
  });

  it('no window yet, or a closing one: nothing is shown and no brain is started', () => {
    const none = setup(null);
    expect(none.reveal.show()).toBe(false);
    expect(none.brain.starts).toBe(0);
    const closing = fakeWindow({ destroyed: true });
    const gone = setup(closing);
    expect(gone.reveal.show()).toBe(false);
    expect(closing.done).toEqual([]);
    expect(gone.brain.starts).toBe(0);
  });

  it('the window is looked up at the time of the show, not before', () => {
    const { reveal, brain, holder } = setup(null);
    reveal.show();
    holder.win = fakeWindow();
    expect(reveal.show()).toBe(true);
    expect(holder.win.done).toEqual(['show', 'focus']);
    expect(brain.starts).toBe(1);
  });
});
