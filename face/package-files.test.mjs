// M34: Pseudo.exe gets only the files on package.mjs's lists. A new main-process file that main.js
// requires but the build forgets would work under `npm start` and crash only inside Pseudo.exe
// (the same kind of gap as M32's three message lists). These tests read each listed file and check
// that everything it requires is listed too. Importing package.mjs builds nothing.
import { existsSync, readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { FILES, MODULES } from './package.mjs';

const read = (name) => readFileSync(new URL(name, import.meta.url), 'utf8');
const required = (name) => [...read(`./${name}`).matchAll(/require\('([^']+)'\)/g)].map((match) => match[1]);

describe('the files that go into Pseudo.exe', () => {
  it('every listed file exists', () => {
    for (const file of FILES) expect(existsSync(new URL(`./${file}`, import.meta.url)), file).toBe(true);
  });

  it('every local file a listed file requires is listed', () => {
    const local = FILES.flatMap((file) => required(file).filter((name) => name.startsWith('.')));
    expect(local.length).toBeGreaterThan(4); // the search found main.js's own requires
    for (const name of local) expect(FILES, name).toContain(`${name.slice(2)}.js`);
  });

  it('every package a listed file requires is listed (Node and Electron come with Pseudo.exe)', () => {
    const packages = FILES.flatMap((file) => required(file))
      .filter((name) => !name.startsWith('.') && !name.startsWith('node:') && name !== 'electron');
    expect(packages).toContain('koffi');
    for (const name of packages) expect(MODULES, name).toContain(name);
  });

  it('npm run package builds the page first', () => {
    expect(JSON.parse(read('./package.json')).scripts.package).toBe('npm run build && node package.mjs');
  });
});
