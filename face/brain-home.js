/**
 * M34: where is the repo, and so the brain's Python?
 *
 * What it demonstrates: a packaged app can't find its files the way a dev checkout does.
 * Under `npm start` this file sits in <repo>\face, so the repo is one folder up. Inside
 * Pseudo.exe it sits in <somewhere>\resources\app, and one folder up is just Electron's
 * resources folder. So the build (package.mjs) writes the repo's path into
 * resources\pseudo-home.json, and the packaged app reads it from there (D27).
 *
 * The file holds ONLY the repo's path. Which program is started in it (.venv's python.exe)
 * and with which arguments stays in code, so the file can't name another program to run.
 * If the file is missing, broken or doesn't hold an absolute path, there is no home:
 * nothing is guessed, and the face says "brain stopped", as it does when Python is missing.
 */

const fs = require('node:fs');
const path = require('node:path');

const HOME_FILE = 'pseudo-home.json';

/** The repo's path from the build's file, or null if it can't be trusted. */
function repoFromFile(file) {
  try {
    const home = JSON.parse(fs.readFileSync(file, 'utf8'));
    return typeof home.repo === 'string' && path.isAbsolute(home.repo) ? home.repo : null;
  } catch {
    return null; // no file, not JSON, or not an object
  }
}

/**
 * @param {boolean} packaged are we Pseudo.exe (Electron's app.isPackaged), not `npm start`?
 * @param {string} resourcesPath the packaged app's resources folder (process.resourcesPath)
 * @param {string} faceDir the folder of the face's main-process files (__dirname)
 * @returns {{ repo: string, python: string } | null}
 */
function brainHome(packaged, resourcesPath, faceDir) {
  const repo = packaged ? repoFromFile(path.join(resourcesPath, HOME_FILE)) : path.resolve(faceDir, '..');
  if (!repo) return null;
  return { repo, python: path.join(repo, '.venv', 'Scripts', 'python.exe') };
}

module.exports = { HOME_FILE, brainHome };
