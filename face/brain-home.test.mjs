// M34: where the brain's Python is. Under `npm start` it's found from the face's own folder; inside
// Pseudo.exe it comes from pseudo-home.json, written by the build. Every folder here is a temporary one.
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

const { HOME_FILE, brainHome } = createRequire(import.meta.url)('./brain-home.js');

let resources;
beforeEach(() => {
  resources = mkdtempSync(path.join(tmpdir(), 'pseudo-home-'));
});
afterEach(() => rmSync(resources, { recursive: true, force: true })); // only the folder this test made

const write = (text) => writeFileSync(path.join(resources, HOME_FILE), text, 'utf8');

describe('brainHome', () => {
  it('npm start: the repo is the folder above face, and the file is never read', () => {
    write(JSON.stringify({ repo: 'C:\\somewhere\\else' }));
    const home = brainHome(false, resources, 'C:\\dev\\Pseudo\\face');
    expect(home).toEqual({ repo: 'C:\\dev\\Pseudo', python: 'C:\\dev\\Pseudo\\.venv\\Scripts\\python.exe' });
  });

  it('packaged: the repo comes from the file the build wrote', () => {
    write(JSON.stringify({ repo: 'D:\\code\\Pseudo' }));
    const home = brainHome(true, resources, 'C:\\out\\Pseudo\\resources\\app');
    expect(home).toEqual({ repo: 'D:\\code\\Pseudo', python: 'D:\\code\\Pseudo\\.venv\\Scripts\\python.exe' });
  });

  it('packaged: the file can not name the program or its arguments', () => {
    write(JSON.stringify({ repo: 'D:\\code\\Pseudo', python: 'C:\\evil.exe', command: 'C:\\evil.exe', args: ['x'] }));
    expect(brainHome(true, resources, 'C:\\x')).toEqual(
      { repo: 'D:\\code\\Pseudo', python: 'D:\\code\\Pseudo\\.venv\\Scripts\\python.exe' });
  });

  it('packaged: no file means no home, and nothing is guessed', () => {
    expect(brainHome(true, resources, 'C:\\dev\\Pseudo\\face')).toBeNull();
  });

  it.each([
    ['not JSON', '{ repo: '],
    ['JSON null', 'null'],
    ['a list', '["C:\\\\dev\\\\Pseudo"]'],
    ['no repo', '{}'],
    ['a repo that is not text', '{"repo": 5}'],
    ['an empty repo', '{"repo": ""}'],
    ['a relative repo', '{"repo": "..\\\\Pseudo"}'],
  ])('packaged: %s means no home', (_name, text) => {
    write(text);
    expect(brainHome(true, resources, 'C:\\dev\\Pseudo\\face')).toBeNull();
  });
});
