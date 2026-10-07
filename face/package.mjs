// M34: build Pseudo.exe BY HAND (D27), with no packaging tool. Run it with `npm run package`.
//
// What it demonstrates: a packaged Electron app is just Electron's own folder with
//   (1) electron.exe renamed to Pseudo.exe, and
//   (2) your app in resources/app, where Electron looks before its built-in demo app.
// Only what the face needs at RUN time goes in: the main-process files, the built page (dist) and
// koffi with its one Windows binary. React, Vite and the tests stay out: Vite already bundled
// React into dist.
//
// Python is NOT bundled. Pseudo.exe starts the brain from this repo's .venv, so the build writes
// the repo's path into resources/pseudo-home.json (read by brain-home.js). Move or rename the
// repo and you run `npm run package` again.
//
// Output: face/out/Pseudo/Pseudo.exe (gitignored). The only folder ever deleted is face/out/Pseudo.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const FACE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(FACE, '..');
const ELECTRON = path.join(FACE, 'node_modules', 'electron', 'dist');
const OUT = path.join(FACE, 'out', 'Pseudo');
const APP = path.join(OUT, 'resources', 'app');

// package-files.test.mjs checks that everything these files `require` is on these two lists.
export const FILES = ['main.js', 'preload.js', 'autostart.js', 'brain-home.js', 'brain-process.js', 'foreground.js',
                      'permissions.js', 'reveal.js', 'single-instance.js', 'taskbar-flash.js', 'to-brain.js', 'tray.js'];
export const MODULES = ['koffi', '@koromix/koffi-win32-x64']; // koffi, and its binary for 64-bit Windows

function stop(message) {
  console.error(`package: ${message}`);
  process.exit(1);
}

/** Everything the build needs must be there BEFORE the old output is removed. */
function checkInputs() {
  const python = path.join(REPO, '.venv', 'Scripts', 'python.exe');
  if (!fs.existsSync(python)) stop(`no Python at ${python}. Create the .venv first (README).`);
  if (!fs.existsSync(path.join(ELECTRON, 'electron.exe'))) stop('Electron is not installed. Run `npm install` first.');
  if (!fs.existsSync(path.join(FACE, 'dist', 'index.html'))) stop('the page is not built. Use `npm run package`.');
  for (const name of MODULES) {
    if (!fs.existsSync(path.join(FACE, 'node_modules', name))) stop(`node_modules/${name} is missing. Run \`npm install\`.`);
  }
}

function removeOldOutput() {
  if (!fs.existsSync(OUT)) return;
  // A link here would point at some other folder: never delete through it.
  if (fs.lstatSync(OUT).isSymbolicLink()) stop(`${OUT} is a link, not a folder this build made. Remove it by hand.`);
  try {
    fs.rmSync(OUT, { recursive: true });
  } catch (error) {
    stop(`can't remove the old ${OUT} (${error.code}). Is Pseudo.exe still running? Quit it and try again.`);
  }
}

function build() {
  const started = Date.now();
  checkInputs();
  removeOldOutput();

  fs.cpSync(ELECTRON, OUT, { recursive: true });
  fs.renameSync(path.join(OUT, 'electron.exe'), path.join(OUT, 'Pseudo.exe'));
  fs.rmSync(path.join(OUT, 'resources', 'default_app.asar')); // Electron's demo app: never ours

  fs.mkdirSync(APP, { recursive: true });
  for (const file of FILES) fs.copyFileSync(path.join(FACE, file), path.join(APP, file));
  fs.cpSync(path.join(FACE, 'dist'), path.join(APP, 'dist'), { recursive: true });
  for (const name of MODULES) {
    fs.cpSync(path.join(FACE, 'node_modules', name), path.join(APP, 'node_modules', name), { recursive: true });
  }

  // The app's own package.json: its name decides the profile folder (%APPDATA%\Pseudo).
  const face = JSON.parse(fs.readFileSync(path.join(FACE, 'package.json'), 'utf8'));
  fs.writeFileSync(path.join(APP, 'package.json'), JSON.stringify({
    name: 'pseudo', productName: 'Pseudo', version: face.version, private: true, main: 'main.js',
    description: "Pseudo's face", dependencies: { koffi: face.dependencies.koffi },
  }, null, 2));

  // Only the repo's path: brain-home.js works out the rest.
  fs.writeFileSync(path.join(OUT, 'resources', 'pseudo-home.json'), JSON.stringify({ repo: REPO }, null, 2));

  let bytes = 0;
  for (const entry of fs.readdirSync(OUT, { recursive: true, withFileTypes: true })) {
    if (entry.isFile()) bytes += fs.statSync(path.join(entry.parentPath, entry.name)).size;
  }
  console.log(`package: built ${path.join(OUT, 'Pseudo.exe')}`);
  console.log(`package: ${(bytes / 1048576).toFixed(0)} MB in ${((Date.now() - started) / 1000).toFixed(1)} s; the brain runs from ${REPO}`);
}

// Only when run as a script (`node package.mjs`), not when the test imports the lists.
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) build();
