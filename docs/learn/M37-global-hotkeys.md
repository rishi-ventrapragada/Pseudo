# M37: Global hotkeys (build)

## The concept in one paragraph

A **global shortcut** works in whatever app you are in. There are two ways to build one, and they are very different things. A **reservation** (Windows' `RegisterHotKey`, which Electron's `globalShortcut` uses) asks Windows: "when exactly this combination is pressed, tell me". The program hears about that one combination and nothing else. A **keyboard hook** receives every key pressed in every program and picks out the ones it wants, which is exactly how a keylogger works. Pseudo is a privacy tool, so it uses reservations only: **Ctrl+Alt+Enter** shows or hides it, **Ctrl+Alt+T** starts and stops talking. The cost is that a reservation fires once, on the press, so there is no "hold to talk" from other apps. The live check also taught two things no unit test could: a key you planned may already belong to another program, and a window can be invisible and still own the keyboard.

## Web-dev analogy

- **A reservation is `addEventListener` for one exact event; a hook is reading the whole event stream.** You'd never ship analytics code that records every keystroke to detect one shortcut.
- **`register()` returning false is a port already in use.** One listener per port, one program per combination; whoever starts first wins. The fix is the same too: pick another port, and say so clearly when you can't bind.
- **`toggle()` is a toggle button's handler**: one function that decides between show and hide from the current state.
- **The talk key is `button.click()` from outside the page.** The main process doesn't record anything; it tells the page "the mic button was pressed" and the existing code does the rest.
- **`to-brain.js` is request validation on the server**: rebuild the body from the fields you allow, even though your own front end sent it.
- **`default: return state` in the reducer** is the unknown-action rule every Redux reducer has; ours was missing it.

## What was built (file by file)

- **`face/hotkeys.js`** (new): reserves the two shortcuts, remembers which ones Windows granted, gives them back at quit.
- **`face/reveal.js`**: `hide()` and `toggle()`; hiding lets go of the keyboard first.
- **`face/main.js`**: wires the shortcuts, makes the tray icon the first time the window is hidden.
- **`face/to-brain.js`** (new): the page-to-brain message check, moved out of `main.js` to keep it under 200 lines.
- **`face/src/HotkeysNote.tsx`** (new), **`state.ts`**, **`protocol.ts`**, **`App.tsx`**: the shortcuts line, the talk press, and Enter no longer asking while Ctrl or Alt is held.
- **Tests:** 35 more in `face/` (153), including five that fail if a keyboard hook ever appears.

## Walkthrough of the key code

**1. A reservation that may be refused** (`hotkeys.js`):
```js
try {
  ok = this.shortcuts.register(keys, () => this.actions[id]()) === true;
} catch {
  ok = false;
}
return { id, label, ok };
```
`register` returns `false` when another program already holds the combination. That is not an error to hide: the result goes to the page, which shows "Ctrl+Alt+T is held by another program, so it is off here". The other shortcut still works.

**2. Give back only what is ours** (`hotkeys.js`):
```js
if (mine.ok) this.shortcuts.unregister(keys);
```
Electron also has `unregisterAll()`. This releases each shortcut by name, and only the ones Windows actually gave us.

**3. One function, two outcomes** (`reveal.js`):
```js
const inFront = Boolean(win) && !win.isDestroyed() && win.isVisible() && win.isFocused();
return inFront ? this.hide() : this.show();
```
If Pseudo is the window you are typing in, the shortcut hides it. In every other case (hidden, behind something, minimized) it brings Pseudo to you, and `show()` starts the brain if this Pseudo was started hidden.

**4. The line the live check wrote** (`reveal.js`):
```js
this.beforeHide();
win.blur(); // first let go of the keyboard: Windows hands it to the window underneath
win.hide();
```
With `hide()` alone, the window vanished and stayed Windows' front window, 10 times out of 10. Anything typed next would have gone into a Pseudo nobody could see. `beforeHide` is where `main.js` makes the tray icon, so a hidden Pseudo always has a visible handle.

**5. The talk key presses a button that already exists** (`main.js`, then `App.tsx`):
```js
talk: () => reveal.show() && toPage({ type: 'talk' }),
```
```tsx
useEffect(() => { // M37: Ctrl+Alt+T, pressed in any app, is one press of the mic button (start, or stop)
  if (state.talk) voice.toggle();
}, [state.talk]);
```
No new recording code. The 30-second cap, the silence rule and "nothing is sent until Enter" all live where they did, so they can't be bypassed by the new way in.

**6. A test that guards a promise** (`hotkeys.test.mjs`):
```js
const HOOKS = /SetWindowsHookEx|WH_KEYBOARD|LowLevelKeyboardProc|GetAsyncKeyState|RegisterRawInputDevices|iohook|uiohook|node-global-key-listener|keylogger/i;
```
"Pseudo installs no keyboard hook" is a sentence in the README. This test reads every source file of the face and fails if a hook API or a hook package is ever named, so the sentence stays true without anyone remembering to check.

## What happens when you run it (annotated real output)

Before any window opened, Windows was asked for the planned keys:
```
Space=TAKEN T=free
```
Ctrl+Alt+Space belongs to the Claude desktop app on this laptop. The show-or-hide key became Ctrl+Alt+Enter.
```
H1 show: in front within 0.5 s 10 of 10 | ms slowest 11 median 5 | hide: Pseudo hidden and the SAME fake window has the keyboard 0 of 10
```
The first live run. Showing was instant; hiding left the keyboard with the hidden window every time.
```
H1 show: in front within 0.5 s 10 of 10 | ms slowest 22 median 16 | hide: Pseudo hidden and the SAME fake window has the keyboard 10 of 10
H2 reads of the fake window after a shortcut show: 10 of 10
H4 popups left on top and unanswered through hide and show: 6 of 6
```
After `blur()` then `hide()`. Pseudo still never reads its own window, and the approval popup can't be dismissed or buried by the shortcut.
```
H3 from the fake window: pressed True | Pseudo in front after 13 ms | recording started True | second press True | in the input box: 8 of 8 words | exact True | questions asked by itself 0
H3 left running: recording started True | stopped by itself True after 31 s (the cap is 30) | questions asked by itself 0
```
The talk key from another window: the words arrive in the box and nothing is sent.
```
H6 another program holds Ctrl+Alt+T (HELD): Pseudo's line: 'Ctrl+Alt+Enter shows or hides Pseudo from any app · Ctrl+Alt+T is held by another program, so it is off here'
H6 while Pseudo runs: Enter=TAKEN T=TAKEN
H6 after Pseudo quit and the helper let go: Enter=free T=free
```
A taken key is reported, and both are released when Pseudo quits.
```
H5 hidden start, idle 603 s ...: CPU s 1.81 (I1 limit 3) | in RAM peak 81 MB (I2 limit 400) | windows 0 | brain processes 0
```
Holding two reservations costs nothing measurable: the same as M36's idle Pseudo.

## Try this (3 small experiments that break or change something)

1. **Lose the race on purpose.** Quit Pseudo. In PowerShell run `python -c "import ctypes, time; print(ctypes.windll.user32.RegisterHotKey(None, 1, 3, 0x54)); time.sleep(60)"` (it prints 1: Ctrl+Alt+T is now held by that Python for a minute). Start Pseudo.exe and read the line at the bottom of its window.
2. **Bring the bug back.** In `face/reveal.js` remove the `win.blur();` line, run `npm run package`, and start Pseudo.exe. Click into Notepad, press Ctrl+Alt+Enter twice (show, then hide), then type. Nothing appears in Notepad. Show Pseudo again and look in its box. Put the line back.
3. **Break the promise.** Add the line `const hook = 'SetWindowsHookEx';` to any file in `face/`, and run `npm test`. Read which test fails and what it says.

## Check yourself

1. What is the difference between reserving a shortcut and installing a keyboard hook, and why does it matter for Pseudo?
2. Why is there no hold-to-talk from other apps?
3. Why did the show-or-hide key change from Ctrl+Alt+Space to Ctrl+Alt+Enter, and what does Pseudo do when a key is taken?
4. `hide()` alone made the window disappear. What was still wrong, and how was it found?
5. Why does a hidden Pseudo always get a tray icon, even though it has a shortcut?

<details>
<summary>Answers</summary>

1. A reservation makes Windows tell the program about one exact combination. A hook hands the program every key pressed in every app. Pseudo's whole point is that nothing personal leaves your control, so it must not even be able to see what you type elsewhere; a test fails if hook code appears.
2. A reservation fires once, when the keys go down. Knowing when a key is released in another app needs a hook. So talking from elsewhere is press to start, press to stop.
3. Windows refused Ctrl+Alt+Space because the Claude desktop app had already reserved it; only one program can hold a combination. When a key is taken, Pseudo leaves that shortcut off, shows which one in its window, and the other keeps working.
4. The hidden window was still Windows' front window, so the keyboard stayed with it: typing went into a box nobody could see, and Enter could have sent it. Only the live check showed it (0 of 10); the unit tests used a fake window that can't know who has the keyboard. The fix is to give up the keyboard (`blur`) before hiding.
5. Because the shortcut can fail to register. Without the icon, a Pseudo hidden by one shortcut press and unable to be shown by the next would be running with no way to reach or quit it.

</details>

## How this connects to Pseudo's final architecture

The top line of ARCHITECTURE's diagram reads "voice / hotkey / typed prompt". With M37 all three exist: you can call Pseudo and talk to it without touching the mouse or leaving the app you are in. Nothing below that line changed: the shortcuts live in the face, which still only displays; the brain decides, and `pseudo_hands` still refuses to read, focus or act on Pseudo's own window however it was brought up. `reveal.js` now has four callers (launch, tray, second launch, shortcut), and M38's compact bar will be a second shape for the same window, shown and hidden by the same key.
