// M36: showing the window and the lazy brain start (reveal.js). The window is a fake that records what
// was done to it, and "the brain" is a counter.
import { createRequire } from 'node:module';
import { describe, expect, it } from 'vitest';

const { Reveal } = createRequire(import.meta.url)('./reveal.js');

function fakeWindow({ minimized = false, destroyed = false, visible = true, focused = false } = {}) {
  const done = [];
  return {
    isDestroyed: () => destroyed,
    isMinimized: () => minimized,
    isVisible: () => visible,
    isFocused: () => focused,
    hide: () => done.push('hide'),
    blur: () => done.push('blur'),
    restore: () => done.push('restore'),
    show: () => done.push('show'),
    focus: () => done.push('focus'),
    done,
  };
}

function setup(win) {
  const brain = { starts: 0 };
  const holder = { win };
  const reveal = new Reveal(() => holder.win, () => { brain.starts += 1; }, () => win && win.done.push('tray made'));
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

describe('M37: hide and toggle', () => {
  it('hide makes the tray icon first, then hides, and starts no brain', () => {
    const win = fakeWindow({ focused: true });
    const { reveal, brain } = setup(win);
    expect(reveal.hide()).toBe(true);
    expect(win.done).toEqual(['tray made', 'blur', 'hide']);
    expect(brain.starts).toBe(0);
  });

  it('lets go of the keyboard BEFORE hiding: a hidden window must not keep it (M37 live check, 0 of 10 without)', () => {
    const win = fakeWindow({ focused: true });
    setup(win).reveal.hide();
    expect(win.done.indexOf('blur')).toBeGreaterThan(-1);
    expect(win.done.indexOf('blur')).toBeLessThan(win.done.indexOf('hide'));
  });

  it('toggle hides Pseudo when it is the window you are in', () => {
    const win = fakeWindow({ visible: true, focused: true });
    setup(win).reveal.toggle();
    expect(win.done).toEqual(['tray made', 'blur', 'hide']);
  });

  it('toggle brings Pseudo to you when it is hidden, behind another window, or minimized', () => {
    const hidden = fakeWindow({ visible: false });
    const first = setup(hidden);
    first.reveal.toggle();
    expect(hidden.done).toEqual(['show', 'focus']);
    expect(first.brain.starts).toBe(1); // a hidden start: the shortcut is one more way to wake it
    const behind = fakeWindow({ visible: true, focused: false });
    setup(behind).reveal.toggle();
    expect(behind.done).toEqual(['show', 'focus']);
    const small = fakeWindow({ visible: true, focused: false, minimized: true });
    setup(small).reveal.toggle();
    expect(small.done).toEqual(['restore', 'show', 'focus']);
  });

  it('no window, or a closing one: hide and toggle do nothing', () => {
    const none = setup(null);
    expect(none.reveal.hide()).toBe(false);
    expect(none.reveal.toggle()).toBe(false);
    const closing = fakeWindow({ destroyed: true, focused: true });
    const gone = setup(closing);
    expect(gone.reveal.hide()).toBe(false);
    expect(gone.reveal.toggle()).toBe(false);
    expect(closing.done).toEqual([]);
  });

  it('without a beforeHide it still hides (the default does nothing)', () => {
    const win = fakeWindow({ focused: true });
    new Reveal(() => win, () => {}).hide();
    expect(win.done).toEqual(['blur', 'hide']);
  });
});
