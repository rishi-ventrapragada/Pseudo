# M38: Compact overlay

## The concept in one paragraph

Pseudo's window now has two shapes. **Full** is the window you know. **Compact** is a small bar that stays on top of your other windows: a status line, the mic button, the question box and Ask. When you ask, the bar grows upward to show the steps, the approval banner and the answer. It is the *same window* both times: nothing is closed or recreated, only its size, its minimum size and one Windows flag ("always on top") change. The interesting part of this milestone is not the bar. It is what a window that sits on top of everything must give up, and when, so that it never gets in the way of the approval popup or steals your keyboard.

## Web-dev analogy

Think of a chat widget on a website. It can be a full page or a small floating bubble with `position: fixed; z-index: 9999`. It is the same React app in both: you add a `compact` class and CSS hides what doesn't fit. That is exactly how the page side works here (`compact.css`).

The window side has no CSS. "Always on top" is the desktop's `z-index: 9999`, and it has the same problem as on the web: two things with a huge z-index compete. Pseudo's approval popup is also "topmost". So the bar turns its own z-index off while a popup may be open.

And the remembered size is like a layout saved in `localStorage`: you must validate it when you read it back, because the screen it was saved on may be gone.

## What was built (file by file)

| File | What it does |
|---|---|
| `face/window-bounds.js` | Plain arithmetic, no Electron. Default and minimum sizes for each mode; `fit()` makes a saved rectangle safe to use; the bar grows upward with its bottom edge kept. |
| `face/window-mode.js` | The `WindowMode` class: switches full and compact on one window, decides when the bar is always on top, remembers only the sizes you set. |
| `face/window-store.js` | Reads and writes `window-mode.json` in the profile folder. Never throws. |
| `face/serve-file.js` | Moved out of `main.js` unchanged, to make room (the 200-line rule). |
| `face/src/useCompact.ts` | The page's side: asks for a mode, and says whether the bar is showing an answer. |
| `face/src/CompactToggle.tsx` | The Compact / Full window button, and Hide answer. |
| `face/src/compact.css` | Hides what a bar has no room for and lays the rest out in one row. |
| `face/src/Composer.tsx` | The question box, moved out of `App.tsx` unchanged. |

56 new tests (209 face tests in all).

## Walkthrough of the key code

**1. The page only describes; the main process decides.** The page sends one message type with two optional true/false fields:

```ts
window.pseudo.send({ type: 'window_mode', compact: on });   // the button
window.pseudo.send({ type: 'window_mode', grown });          // "an answer is showing"
```

The page never says "be 440 pixels high" or "be on top". `WindowMode.fromPage()` accepts only real booleans and turns them into a size. This is D11 again: the display says what it is showing, the rules live elsewhere.

**2. When the bar is on top.** One line holds the whole rule:

```js
applyTop() {
  const win = this.usable();
  if (win) win.setAlwaysOnTop(this.mode === 'compact' && !this.waiting && win.isVisible());
}
```

Three conditions: it is the bar, no tool is waiting, and the window is visible. `waiting` is set from the brain's own messages, which the main process already sees:

```js
if (message.type === 'event' && message.kind === 'tool_call') this.waiting = true;
else if ((message.type === 'event' && message.kind === 'tool_result') || message.type === 'turn_done') this.waiting = false;
```

A `tool_call` means an approval popup may be about to open, so the bar steps down. The page is not asked: a bug in the page can't keep the bar above a popup.

**3. Never trust a saved position.** `fit()` in `window-bounds.js`:

```js
if (!isRect(saved)) return fit(defaultBounds(mode, main), mode, areas, minHeight);
const best = areas.reduce((a, b) => (overlap(saved, b) > overlap(saved, a) ? b : a), main);
const area = overlap(saved, best) > 0 ? best : main;
```

If the saved value isn't four real numbers, use the default. Otherwise find the screen the window is mostly on; if it is on no screen at all (a monitor was unplugged), use the main one. Then the size is held between the minimum and the screen, and the window is pushed fully inside.

**4. Remember what you asked for, not what you got.** On your laptop the screens are scaled to 125%. A window asked to be 982 wide reports 983. If the code re-read its own size on every switch, the window would grow:

```js
setExact(win, want) {
  win.setBounds(want);
  const got = win.getBounds();
  const [wide, high] = [got.width - want.width, got.height - want.height];
  if ((wide || high) && Math.abs(wide) <= DRIFT && Math.abs(high) <= DRIFT) {
    win.setBounds({ ...want, width: want.width - wide, height: want.height - high });
  }
}
```

Ask; look; if it is a few pixels off, ask again with the difference taken off. And `remember()` ignores any change that small, so only *your* dragging is saved.

## What happens when you run it (annotated real output)

Step 0 tested the idea on a scratch copy before anything was built. The first run found two real problems:

```
S1 ... bar reached 480 x 132 and always on top 5 of 5 | full came back at its old size and place, not on top 0 of 5
S4 hide and show by Ctrl+Alt+Enter in bar mode ... all five 0 of 5
```

A diagnostic then showed *who* had the keyboard after hiding the bar (programs by name only):

```
hide = plain: ... 0 of 5
   keyboard after hiding: a window of explorer.exe, class 'Shell_SecondaryTrayWnd'
hide = drop: hidden, the fake notes have the keyboard, shown again, still always on top: 5 of 5
```

`Shell_SecondaryTrayWnd` is the taskbar on your second screen. M37's hide is "blur, then hide", and blur hands the keyboard to the *next window in the same layer*. For an always-on-top window that layer contains the taskbar, not your notes. "drop" means: stop being on top first. That became `letGo()`.

And the size drift, with the fix:

```
back to full with 'full':    asked for (278, 38, 982, 742) | got, 5 rounds: [(278, 38, 985, 745), (278, 38, 986, 746), ...] | exact 0 of 5
back to full with 'fullfix': asked for (278, 38, 982, 742) | got, 5 rounds: [(278, 38, 982, 742), ...] | exact 5 of 5
```

The live check on the real `Pseudo.exe`:

```
C1 reads of the fake window with the bar on top: 9 of 10 | pick with the bar not focused 10 of 10
C2 popups above the bar and clickable: 12 of 12 (4 focus, 4 memory, 4 action; half after clicking the bar)
C5 a saved place of (9000, 9000): the bar opened fully on a screen True
C6 bar visible, first 10 minutes ...: CPU s in all 1.62 (I1 limit 3) | face: gpu-process 1.03 | face: main 0.42 | ...
```

Two honest notes. **C1 missed**: in one of ten reads the model called `list_open_windows` before `read_active_window`. The right window was read, but the rule says "that tool only". **C6 missed once**: four idle periods gave 3.61, 1.94, 1.62 and 1.58 CPU-seconds against a limit of 3. The 3.61 was never explained. I guessed "the first minutes after start", measured it, and the guess was wrong.

## Try this (3 small experiments that break or change something)

1. **Unplug a screen on paper.** Quit Pseudo. Open `%APPDATA%\Pseudo\window-mode.json` and set the `compact` entry's `x` and `y` to `9000`. Start Pseudo. Where does the bar open? Then change `width` to `"wide"` (a string) and start again. Which line of `fit()` handled each?
2. **Break the drift fix.** In `face/window-mode.test.mjs`, find the test "five switches there and back never change the full size by a pixel". In `window-mode.js`, make `setExact` just `win.setBounds(want);`. Run `npm test` in `face/`. Read the failure: it shows the 1-pixel growth the fake screen simulates. Undo it.
3. **Try to make the bar click-through.** Add `win.setIgnoreMouseEvents(true);` anywhere in `window-mode.js` and run `npm test`. Which test fails, and what does its message name? Undo it. Why would `pseudo_hands` treat such a window differently (hint: `is_user_window` in `windows.py`)?

## Check yourself

1. Why does the bar stop being always on top when a `tool_call` arrives, even for a tool that asks nothing?
2. Hiding the bar with Ctrl+Alt+Enter used to send your keyboard to the taskbar. Why, and what one call fixes it?
3. The page sends `grown: true`. Who decides how tall the window becomes, and why not the page?
4. Why is the window's size remembered in a file by the main process and not in the page's `localStorage` like the switches?
5. C1 scored 9 of 10 although the right window was read all ten times. Why is it still recorded as a miss?

<details>
<summary>Answers</summary>

1. The face can't know which tools ask for approval (it decides nothing, D11), so it treats every running tool as "a popup may be open". Both the popup and the bar are topmost, and two topmost windows compete. Stepping down for a few hundred milliseconds on a read costs nothing.
2. `blur()` gives the keyboard to the next window in the same layer. An always-on-top window shares its layer with the taskbar. `setAlwaysOnTop(false)` first (`letGo()`), then blur and hide; it is on top again when shown.
3. The main process (`WindowMode.setGrown` and `window-bounds.js`). The page only reports display state. Sizes, minimums, staying on screen and always-on-top are rules, and rules stay out of the page.
4. The main process needs the size *before* the page exists, to create the window in the right place. `localStorage` belongs to the page.
5. The rule was fixed before measuring: the fake word in the answer *and* `read_active_window` as the only tool. Loosening a rule after seeing the data would make every later number mean less. The cause (a model habit) is recorded next to the miss instead.

</details>

## How this connects to Pseudo's final architecture

This closes Phase 9: Pseudo is now a `Pseudo.exe` that can start with Windows, be called from any app, and stay on screen as a small bar. The three rules from the start of the phase held: Pseudo never reads or acts on its own window (the bar is listed without an id and refused as an assistant app), the approval popup stays above the face (12 of 12), and no action can touch the popup (D14). All three are enforced in `pseudo_hands` core, by program name, which is why adding a new window shape to the face needed no change there at all. Two things are left in the Backlog from this milestone: one idle CPU reading over the limit, and one run where the bar ended up with the keyboard while idle.
