# M33: How to package Pseudo.exe (evaluation)

## The concept in one paragraph

**Packaging** turns "a folder of source you start from a terminal" into "a program you double-click". For an Electron app that is less magic than it sounds: Electron already ships as a ready program, `electron.exe`, plus a `resources` folder. When it starts, it looks for your app in `resources/app` (a plain folder) or `resources/app.asar` (the same folder packed into one archive file). So a packaged app is Electron's own folder, with the exe renamed and your files put where it looks. Packaging **tools** do exactly that, and add conveniences: they pack the archive, stamp the exe's name and icon, and can build an installer. M33 measured three ways to do it, and one way to freeze the Python side too, against criteria fixed before anything was built.

## Web-dev analogy

- **`npm start` is `vite dev`; `Pseudo.exe` is the deployed build.** Same code, but it no longer needs your terminal or the source tree's dev tools.
- **Staging is `vite build` for the main process.** Only run-time files go in: 3 MB, against 128 installed packages. React isn't copied, because Vite already bundled it into `dist`.
- **`app.asar` is a zip of your app**, like a `.jar`. One file instead of a hundred, but a native DLL can't be loaded from inside it, so `.node` files stay outside ("unpacked").
- **`pseudo-home.json` is an environment variable baked in at build time**, like `VITE_API_URL`: the packaged app has to be told where the repo is, because it no longer sits next to it.
- **PyInstaller is like bundling Node itself into your app**: no installed Python needed, at the price of size and build time.

## What was built (file by file)

Nothing in the repo changed except the docs. Everything below is in the scratchpad, not committed.

- **`stage.mjs`:** copies the face's run-time files (five main-process files, `dist`, `koffi` and its one Windows binary) and makes one change to `brain-process.js`: the repo and Python paths come from `pseudo-home.json`.
- **`k1-build.mjs` (K1, by hand):** copies Electron's folder, renames the exe, drops Electron's demo app, copies the staged app in.
- **`k2-build.mjs` (K2):** the same through `@electron/packager`.
- **`k3-config.json` (K3):** the same through `electron-builder`.
- **`y2/pseudo_py.py` (Y2):** the one program PyInstaller freezes. It imitates `python -m module`, so the brain's own start commands keep working.
- **`m33_live.py`:** launches a candidate three times and runs the checks, on fake windows.

## Walkthrough of the key code

**1. All of K1** (`k1-build.mjs`):
```js
fs.cpSync(ELECTRON, OUT, { recursive: true });
fs.renameSync(path.join(OUT, 'electron.exe'), path.join(OUT, 'Pseudo.exe'));
fs.rmSync(path.join(OUT, 'resources', 'default_app.asar')); // Electron's demo app: never ours
fs.cpSync(path.join(HERE, 'stage', 'app'), path.join(OUT, 'resources', 'app'), { recursive: true });
```
Four file operations. The rename is what matters for Pseudo: `assistant_apps.txt` matches by **process name**, so every window of the packaged app now belongs to `Pseudo.exe`.

**2. What a tool adds** (`k2-build.mjs`):
```js
asar: { unpack: '*.node' },
win32metadata: { CompanyName: 'Pseudo', FileDescription: 'Pseudo', ProductName: 'Pseudo' },
```
- `unpack` keeps `koffi.node` outside the archive. Without it, the popup's bring-to-front grant would silently stop working.
- `win32metadata` rewrites the text stored inside the exe. K1 can't do that without a tool, so its exe is *named* `Pseudo.exe` but still *describes* itself as "Electron".

**3. Telling the app where home is** (staged `brain-process.js`):
```js
const HOME = JSON.parse(require('node:fs').readFileSync(path.join(process.resourcesPath, 'pseudo-home.json'), 'utf8'));
```
`process.resourcesPath` is the packaged app's `resources` folder. Under `npm start`, `__dirname/..` was the repo; packaged, it isn't.

**4. Imitating `-m` in a frozen exe** (`y2/pseudo_py.py`):
```python
if len(sys.argv) >= 3 and sys.argv[1] == "-m":
    runpy.run_module(module, run_name="__main__", alter_sys=True)
```
`pseudo_brain` starts `pseudo_hands` with `sys.executable -m ...`. A frozen exe has no `-m`, so the entry point provides one.

## What happens when you run it (real output, annotated)

**Builds** (no windows):
```
K1 by hand             370 MB   0.6 s   +0 packages     exe says "Electron"
K2 @electron/packager  370 MB   9.7 s   +38 packages    exe says "Pseudo"
K3 electron-builder    370 MB  48.0 s   +265 packages   exe says "Pseudo"
K4 Electron Forge      (counted only)   +145 packages
Y2 PyInstaller         231 MB for Python alone, 272 s
```
The face's own files are 3 MB; the other 367 MB is Electron (Chromium). No tool can shrink that.

**Live, K1** (K2, K3 and the `npm start` baseline printed the same shape; lines shortened):
```
 launch 1: seconds to ready 12.7 | private MB {'brain': 68, 'face': 87, 'pseudo_hands': 100} total 257
 launch 1: processes left 15 s after closing the window: 0
 windows of the app belong to: ['Pseudo.exe']
 a menu bar in the window: False
 developer tools opened by Ctrl+Shift+I or F12: False
 read 1: answered True | tools ['read_active_window'] | says our fake word BLUE: True
 switch question: popup in the always-on-top layer True | above the face True | got the keyboard True
 focus_window on the face: 'assistant app' | act on the face: 'assistant app' | popups from these: 0
 listening sockets in the app's process tree: none
 outside connections, by group (addresses not shown): {'brain': 4}
```
- **"got the keyboard"** is the proof that `koffi` loaded: without the grant, the popup stays on top but doesn't take the keyboard (P7-fix).
- **Only the brain talks outside the laptop**, to Groq. The face and `pseudo_hands` made no outside connection.
- **257 MB is the same in all four runs.** Packaging changes how Pseudo starts, not what it costs.

**Y2, no windows:**
```
frozen exe (start 2): tools ['act_on_control', 'list_open_windows', 'read_active_window'] | seconds to the tool list 5.3
frozen brain, as built: exit code 1 | first protocol line starts: '{"type": "refused", "reason": "can\'t start: missing LLM_API_'
```
The frozen brain looks for `.env` next to its own code, which is now inside the frozen folder. It would need a code change to start.

## Try this

1. In `face/node_modules/electron/dist`, look at `resources/`. Which file is Electron's demo app, and what would Electron run if both it and an `app` folder were there?
2. Run `npm view electron-builder dependencies` in `face/`. Find two that only matter for macOS or Linux. Why are they installed anyway?
3. Right-click `face/node_modules/electron/dist/electron.exe`, Properties, Details. Which fields would K1 leave unchanged?

## Check yourself

1. Why are all three packaged folders 370 MB, when the face's own files are 3 MB?
2. What does renaming `electron.exe` to `Pseudo.exe` change for the self-read rule?
3. Why must `koffi.node` stay outside `app.asar`, and what would break if it didn't?
4. Y2 passed "Claude Code can still start `pseudo_hands`". Why is it out anyway?
5. All three face candidates passed every criterion. What decided between them?

<details>
<summary>Answers</summary>

1. The rest is Electron itself: Chromium and Node.js. Every Electron app carries its own copy.
2. `assistant_apps.txt` matches by process name. Every window of the packaged app belongs to `Pseudo.exe`, so one line on the list covers reading, listing, focusing and acting.
3. Windows loads a DLL from a real file on disk, not from inside an archive. Without `koffi`, the face couldn't pass its foreground right to `pseudo_hands`, and the popup wouldn't get the keyboard.
4. A build takes 272 s against a 3-minute limit, and the frozen brain can't find `.env`, so it doesn't start without changing `pseudo_brain`. It also adds 231 MB that the `.venv` already holds.
5. The tie rule fixed before measuring: fewest new packages, then smallest. K1 adds none.
</details>

## How this connects to Pseudo's final architecture

- **M34 builds the winner** as `npm run package`, and adds `Pseudo.exe` to `assistant_apps.txt`.
- **M36 (start with Windows) needs a real exe.** Under `npm start`, Windows would be told to start a bare `electron.exe`.
- **D11 holds.** Packaging touched only the face's shell. The brain, `pseudo_hands`, the redactor and the popup are the same processes running the same code, which is why the memory figures didn't move.
