# M34: Pseudo.exe (build)

## The concept in one paragraph

M33 chose how to package Pseudo; M34 builds it. Three ideas are new. **A build script** is a program whose output is another program: `npm run package` copies Electron's folder, renames the exe and puts the face's files where Electron looks. **A baked-in path:** the packaged app no longer sits next to the repo, so the build writes down where the repo is, and the app reads that at start-up. **A single-instance lock:** the first Pseudo to start takes a lock; a second launch can't get it, so it quits and the first one shows its window. Python is not inside Pseudo.exe. The exe is the window only, and it starts the brain from the repo's `.venv` exactly as `npm start` does (D27).

## Web-dev analogy

- **`npm run package` is your deploy step.** `npm start` is the dev server; `face/out/Pseudo` is the build output folder, gitignored like `dist/` or `.next/`.
- **`pseudo-home.json` is a build-time environment variable**, like `VITE_API_URL`: a value the built app can't work out by itself, written in at build time. Move the repo and you rebuild, the same as changing the API URL.
- **The file list in `package.mjs` is the `files` field of a `package.json`**: only what's listed ships. Forget a file and it works locally and breaks in production. That is why a test checks the list.
- **The single-instance lock is a lock file**, like the one a dev server leaves so a second `npm run dev` says "port already in use". Here the second copy also tells the first one to come forward.
- **The profile folder is `localStorage` per origin.** `npm start` and Pseudo.exe have different app names, so each has its own saved switches.

## What was built (file by file)

- **`face/brain-home.js`** (new): `brainHome(packaged, resourcesPath, faceDir)` answers "where is the repo, and its Python?".
- **`face/brain-process.js`**: takes that answer as a third argument, where it used to work the path out from its own folder. With no answer it reports "brain stopped".
- **`face/single-instance.js`** (new): `onlyOne(app, getWindow)` takes the lock and listens for a second launch.
- **`face/main.js`**: three small changes. It passes `brainHome(...)` to the brain, calls `onlyOne`, and does nothing more if it isn't the first.
- **`face/package.mjs`** (new): the build. `face/package.json` gains the `package` script.
- **`pseudo_hands/core/assistant_apps.txt`**: one new line, `Pseudo.exe`.
- **`.gitignore`**: `face/out/`.
- **Tests:** `brain-home.test.mjs` (11), `single-instance.test.mjs` (6), `package-files.test.mjs` (4), and one more in `tests/test_assistant_apps.py`.

## Walkthrough of the key code

**1. Two ways to find the repo** (`brain-home.js`):
```js
const repo = packaged ? repoFromFile(path.join(resourcesPath, HOME_FILE)) : path.resolve(faceDir, '..');
if (!repo) return null;
return { repo, python: path.join(repo, '.venv', 'Scripts', 'python.exe') };
```
`packaged` is Electron's `app.isPackaged`: true when the exe isn't called `electron.exe`. Under `npm start` the repo is one folder up, as before. Packaged, it comes from the file. Notice what the file does **not** decide: the program (`python.exe` in `.venv`) and its arguments (`-m pseudo_brain.bridge`) stay in code. M33's scratch version kept the whole command in the file; a file that says "run this" is a way to make Pseudo run something else.

**2. Fail closed, again** (`brain-home.js`):
```js
return typeof home.repo === 'string' && path.isAbsolute(home.repo) ? home.repo : null;
```
No file, broken JSON, a number, a relative path: all become `null`. Nothing is guessed. `brain-process.js` then reports the same thing it reports for a missing Python:
```js
if (!this.home) {
  setImmediate(() => this.onExit(null));
  return;
}
```
`setImmediate` means "after the current code finishes". A real failed start is also reported a moment later, so both cases reach the page the same way.

**3. The lock** (`single-instance.js`):
```js
if (!app.requestSingleInstanceLock()) return false;
app.on('second-instance', () => {
  const win = getWindow();
  if (!win || win.isDestroyed()) return;
  if (win.isMinimized()) win.restore();
  win.show();
  win.focus();
});
return true;
```
One function, two roles. In the **second** Pseudo, the first line returns `false` and `main.js` quits before it opens a window or starts a brain. In the **first**, the listener runs each time someone starts another. `getWindow` is a function, not a window, because the window doesn't exist yet when the lock is taken.

**4. The build, in four steps** (`package.mjs`):
```js
fs.cpSync(ELECTRON, OUT, { recursive: true });
fs.renameSync(path.join(OUT, 'electron.exe'), path.join(OUT, 'Pseudo.exe'));
fs.rmSync(path.join(OUT, 'resources', 'default_app.asar')); // Electron's demo app: never ours
...
fs.writeFileSync(path.join(OUT, 'resources', 'pseudo-home.json'), JSON.stringify({ repo: REPO }, null, 2));
```
Before any of it, `checkInputs()` makes sure Python, Electron, the built page and `koffi` are there, so a failed build never leaves you with the old exe deleted and no new one. The only folder the script ever deletes is `face/out/Pseudo`, and not if it turns out to be a link.

**5. Why the rename matters to the privacy rules** (`assistant_apps.txt`):
```
electron.exe   # Pseudo's own face while it runs from `npm start` (M18)
Pseudo.exe     # Pseudo's own face as the packaged app, built by `npm run package` (M34)
```
Pseudo decides "that's my own window" by **process name**. Without the second line, the packaged Pseudo would read its own chat when you ask "what's on my screen?", and could be asked to click its own buttons.

## What happens when you run it (annotated real output)

The build:
```
package: built C:\dev\Pseudo\face\out\Pseudo\Pseudo.exe
package: 370 MB in 1.1 s; the brain runs from C:\dev\Pseudo
```
367 of the 370 MB are Electron and Chromium. The face's own files are 3 MB.

The live check, on the packaged app with fake windows:
```
main: window True | ready True after 8.2 s
 windows of the app belong to: ['Pseudo.exe']
 reads of the fake window, never its own: 3 of 3
 focus_window: ... popup 1 of 1 on top and above the face | clicked ['Cancel']
 action (cancel): by claude-code ... billing clean True | effect unchanged: True
 action (ok): by claude-code ... clicked ['OK'] | effect as asked: True | nothing else changed True
 popups in all: 9 | 9 of 9 on top and above the face
```
Everything that worked under `npm start` works from the exe: the self-read rule, the popup on top, Claude Code for actions.
```
 second launch (first one behind our fake window): second exited by itself True (code 0) |
   first window in front and not minimized True | ... Pseudo.exe main processes now 1
 second launch (first one minimized): second exited by itself True (code 0) | first window in front ... True
main: processes left 15 s after closing the window: 0
```
The second Pseudo never became a second Pseudo.
```
 button: ... in the input box: 8 of 8 words | exact True | questions asked by itself 0
 Ctrl+Space: ... in the input box: 8 of 8 words | exact True | questions asked by itself 0
home (a folder with no Python): says the brain stopped True | Python processes started 0
home (no home file): says the brain stopped True | Python processes started 0
total: 12/12 | answered by: ['openai/gpt-oss-120b'] | fallbacks: 0
```
The fake microphone works in the exe, a wrong home file starts nothing, and the M15 battery still scores 12/12.

## Try this (3 small experiments that break or change something)

1. **Break the home file.** Run `npm run package`, open `face\out\Pseudo\resources\pseudo-home.json` and change the path to `C:\nowhere`. Start Pseudo.exe: "Pseudo's brain stopped." Press Restart: the same. Run `npm run package` again to repair it.
2. **Start it twice.** Start Pseudo.exe, minimize it, start it again. Then, in `main.js`, comment out the `if (!first) app.quit();` line and its guard, rebuild, and try again: two windows, two brains in Task Manager. Put the lines back.
3. **Forget a file.** Remove `'single-instance.js'` from `FILES` in `package.mjs` and run `npm test` in `face`: `package-files.test.mjs` fails and names the file. That failure is cheaper than a Pseudo.exe that crashes at start.

## Check yourself

1. Why does Pseudo.exe need `pseudo-home.json` when `npm start` doesn't?
2. The home file holds only a path. What would be the risk if it also held the command to run?
3. What happens, step by step, when you double-click Pseudo.exe while it is already running?
4. Why did `Pseudo.exe` have to be added to `assistant_apps.txt`?
5. You change a Python file in `pseudo_brain`. Do you need to run `npm run package` again? What about a file in `face/src`?

<details>
<summary>Answers</summary>

1. Under `npm start` the face's files sit in `<repo>\face`, so the repo is one folder up. Inside the exe they sit in `resources\app`, and one folder up is Electron's resources folder. The app has to be told where the repo is.
2. Anyone (or anything) able to edit that file could make Pseudo start a different program every time it opens. With only a path, the worst a bad file can do is point at a folder with no `.venv`, and then nothing starts.
3. The second process asks for the lock and doesn't get it, so `onlyOne` returns false and it quits without a window or a brain. Electron sends the first process a `second-instance` event; it restores its window if minimized, shows it and focuses it.
4. Pseudo recognises its own window by process name. The packaged face runs as `Pseudo.exe`, not `electron.exe`, so without the line it would read and could act on its own window.
5. Python: no. The exe starts Python from the repo's `.venv`, so it runs whatever is in the repo now. `face/src`: yes. The page is built into `dist` and copied into the exe's folder, so the exe keeps the old page until you rebuild.

</details>

## How this connects to Pseudo's final architecture

Pseudo.exe is the face from ARCHITECTURE's diagram in the form you can leave running: the same display-only window (D11), the same child-process pipe to the brain (D18), the same rules in `pseudo_hands`. Nothing about privacy or approval moved into the exe. The rest of Phase 9 builds on it: M35 measures what it costs to leave running, M36 starts it with Windows (which needs a real exe to register), M37 adds global hotkeys and M38 a compact bar. The single-instance lock matters most for M36 and M37: a Pseudo started at sign-in plus one you double-click must still be one Pseudo.
