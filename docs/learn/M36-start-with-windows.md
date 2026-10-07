# M36: Start with Windows (build)

## The concept in one paragraph

A program "starts with Windows" because its command is on a list that Windows runs when you sign in. For an ordinary app that list is one registry key, `Run`, with one value per program. M36 adds Pseudo to it with a switch, and makes that start a quiet one: the command carries `--start-hidden`, so Pseudo opens **no window**, puts a small **tray icon** in the taskbar corner instead, and (M35's pick, D27) does **not start its brain** until you first open it. Three ideas are worth keeping: the switch shows what Windows says and never what it remembers; one function shows the window, so no way of opening Pseudo can forget to start the brain; and a hidden program needs some visible handle, or you can't reach it or stop it.

## Web-dev analogy

- **The `Run` key is a crontab with one schedule, "at sign-in".** One line per program; anyone with your account can read and edit it, and Task Manager is its admin page.
- **The switch is a controlled input bound to server state.** Ticking it sends a request; the box moves only when the answer comes back. Like a toggle that reflects the database row, not the click.
- **`--start-hidden` is a query parameter**: the same app, started in a different mode by its launcher.
- **Lazy brain start is the lazy import from M35**, now real code: `reveal.js` is the single place it happens.
- **The tray icon is a favicon with a context menu**: the only visible part of a page that isn't on screen.
- **The page forgetting Windows' answer was a classic reducer bug**: a "reset to initial state" case wiping a field that belonged to someone else.

## What was built (file by file)

- **`face/autostart.js`** (new): reads and writes the entry; says why it can't under `npm start`.
- **`face/reveal.js`** (new): shows the window and starts the brain the first time.
- **`face/tray.js`** (new): the icon, drawn from a 16 x 16 pixel map, with Show and Quit.
- **`face/single-instance.js`**: a second launch now calls `reveal.js`.
- **`face/main.js`**: reads `--start-hidden`, creates the window hidden, makes the tray, answers the switch's messages.
- **`face/src/AutostartControl.tsx`** (new), **`state.ts`**, **`protocol.ts`**, **`preload.js`**: the switch and its message.
- **`face/package.mjs`**: three more files on the build's list.
- **Tests:** 31 more in `face/` (118).

## Walkthrough of the key code

**1. The entry is read, not remembered** (`autostart.js`):
```js
const items = app.getLoginItemSettings({ name: NAME, args: [HIDDEN_ARG] }).launchItems || [];
const item = items.find((entry) => entry.name === NAME);
if (!item) return { type: 'autostart', available: true, on: false, note: '' };
if (!samePath(item.path, exe)) return { ... on: false, note: OTHER_EXE };
if (!item.enabled) return { ... on: false, note: OFF_IN_WINDOWS };
```
Four answers, all from Windows: no entry; an entry for some other Pseudo.exe (you moved the repo); an entry Windows has switched off in Task Manager; and ours, on. Nothing is stored in the page or in `localStorage`. A probe before the build showed why `launchItems` is used: Electron's simpler `openAtLogin` stayed `false` even with the entry in place.

**2. Only the real program may register** (`autostart.js`):
```js
if (app.isPackaged) app.setLoginItemSettings({ openAtLogin: on, name: NAME, args: [HIDDEN_ARG], enabled: true });
return autostartState(app, exe);
```
Under `npm start` the running program is a bare `electron.exe`; registering that would open an empty Electron window at every sign-in. And the function returns what Windows says *after* the write, not what was asked.

**3. One door for showing the window** (`reveal.js`):
```js
show() {
  const win = this.getWindow();
  if (!win || win.isDestroyed()) return false;
  if (win.isMinimized()) win.restore();
  win.show();
  win.focus();
  this.startBrain();
  return true;
}
```
The tray click and a second launch both call this. `startBrain()` does nothing the second time, so the brain is started once: if it later stops, the page offers Restart as before, and showing the window never restarts it behind your back.

**4. The hidden start** (`main.js`):
```js
if (startHidden) tray = createTray({ Tray, Menu, nativeImage }, () => reveal.show(), () => app.quit());
else reveal.startBrain(); // opened by hand: everything starts at once, as before
```
Two lines decide the whole mode. The window still exists (created with `show: false`), so the page is loaded and ready the instant you ask for it.

**5. An icon without an image file** (`tray.js`):
```js
const color = COLORS[PIXELS[Math.floor(y / scale)][Math.floor(x / scale)]];
bitmap.set(color, (y * side + x) * 4);
```
`PIXELS` is sixteen strings of sixteen characters: `.` see-through, `#` blue, `P` white. Each becomes four bytes (blue, green, red, alpha). At `scale` 2 every pixel is used four times, giving a sharp 32 x 32 icon.

**6. The bug the live check found** (`state.ts`):
```ts
case 'ready':
  return { ...initial, autostart: state.autostart, phase: 'ready', // M36: Windows' answer is kept
```
`ready` used to return `{ ...initial, ... }`. Windows answers in milliseconds, the brain eight seconds later, so the brain's "ready" wiped the answer every time and the switch never appeared. Every unit test passed; only the real app, in the real order, showed it.

## What happens when you run it (annotated real output)

```
A first open: switch found True | enabled True | on False | 'Off: Pseudo starts only when you open it.'
A switched on: box now on True | ... | new Run values ['Pseudo'] | removed 0 | our value is exactly our exe + --start-hidden True
A reopened with a new profile: switch on True
```
One value added, named `Pseudo`, nothing else touched. The reopened Pseudo had a brand-new profile, so "on" could only have come from Windows.
```
B hidden start: windows shown in 60 s 0 | CPU s in the first minute 2.12 (I5 limit 5) | brain processes 0 | pseudo_hands processes 0
B hidden and idle, 603 s ...: CPU s 2.33 (I1 limit 3) | in RAM peak 87 MB, median 75 (I2 limit 400) | windows now 0 | brain processes 0
```
Started the way Windows would start it: no window, no Python, within all three of M35's limits.
```
B show (a second launch): second exited by itself True | window shown True ... | brain ready True after 7.9 s (limit 15)
click on the icon (Show): window shown True | in front True | brain started True | brain ready True
right-click menu items ['Show', 'Quit'] | Quit: Pseudo exited True | processes left 0
```
Both ways of opening a hidden Pseudo start its brain, and Quit from the tray leaves nothing.
```
C switched off: ... | our value None | Run names exactly as before True | StartupApproved names exactly as before True
npm start (given --start-hidden too): window shown True | switch found True | enabled False | on False
```
Off removes exactly what on added. Under `npm start` the switch is disabled and the hidden flag is ignored.

## Try this (3 small experiments that break or change something)

1. **See the entry.** Tick the switch in Pseudo.exe, then run `Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run' | Select-Object Pseudo`. Untick it and run it again.
2. **Let Windows overrule Pseudo.** With the switch on, open Task Manager > Startup apps and disable Pseudo there. Click back into Pseudo's window: the box empties and the line says why. Tick it again and look at Task Manager.
3. **Start it the way Windows will.** Quit Pseudo, then run `.\face\out\Pseudo\Pseudo.exe --start-hidden`. Nothing appears; find the blue "P" under the taskbar's ^ arrow. In Task Manager > Details there is no `python.exe` for Pseudo until you click the icon.

## Check yourself

1. Where does "Start with Windows" live, and what exactly does Pseudo put there?
2. Why does the switch read Windows every time instead of remembering your choice?
3. Why is the switch disabled under `npm start`?
4. A hidden Pseudo can be opened in two ways. Why do both start the brain, and what would go wrong if each had its own code?
5. Every unit test passed, yet the switch never appeared in the real app. What was wrong, and what does that say about tests?

<details>
<summary>Answers</summary>

1. In the registry, under `HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run`: one value named `Pseudo` holding `"<path>\Pseudo.exe" --start-hidden`. Windows runs every command in that key at sign-in.
2. Because the entry can change without Pseudo: you can disable it in Task Manager, delete it, or move the repo so it points nowhere. A remembered "on" would then be a claim about your laptop that isn't true.
3. Under `npm start` the running program is `electron.exe`, not Pseudo.exe. Registering it would start a bare Electron at sign-in. So nothing is written, and the switch says why.
4. The tray click and a second launch both call `Reveal.show()`, which starts the brain if it hasn't been started. With separate code, one path could show the window and forget the brain, leaving a page stuck on "Starting the brain".
5. The page's "ready" case reset the state to its initial value, wiping Windows' answer that had arrived a few seconds earlier. Each test checked one message at a time; none sent the two in the real order. Tests prove what you thought to ask; a live check finds the question you didn't.

</details>

## How this connects to Pseudo's final architecture

This is the first milestone where Pseudo is something that is simply there: started with the laptop, out of the way, costing about 2 CPU-seconds per ten minutes and under 90 MB until you call it. None of the privacy or approval rules moved: the hidden face runs no brain and no `pseudo_hands`, so nothing reads or acts until you open it. `reveal.js` is also the hook the next milestone needs: M37's global hotkey becomes a third caller of `show()`, and its talk key a fourth. M38's compact bar will be another shape of the same window.
