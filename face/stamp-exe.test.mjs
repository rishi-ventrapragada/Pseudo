// M44: stamp-exe.mjs writes Pseudo's icon and names into a copy of Electron's exe, held in memory: no file
// is written, and node_modules' electron.exe is only read. Parsing the 246 MB exe takes well under a second.
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { describe, expect, it } from 'vitest';
import { NAMES, readStamp, stampBuffer } from './stamp-exe.mjs';

const require = createRequire(import.meta.url);
const { SIZES } = require('./ico.js');
const electronExe = readFileSync(new URL('./node_modules/electron/dist/electron.exe', import.meta.url));
const ico = readFileSync(new URL('./pseudo.ico', import.meta.url));

describe('stamping the exe', () => {
  it("Electron's own exe says Electron, with Electron's icon (what D27 recorded as a limit)", () => {
    const before = readStamp(electronExe);
    expect(before.names.FileDescription).toBe('Electron');
    expect(before.names.ProductName).toBe('Electron');
    expect(before.iconSizes).not.toEqual(SIZES);
  });

  it('afterwards it says Pseudo, and its icon holds every size of pseudo.ico', () => {
    const after = readStamp(stampBuffer(electronExe, ico));
    expect(after.names).toEqual(NAMES);
    expect(after.names.FileDescription).toBe('Pseudo'); // Task Manager's name for the process
    expect(after.iconSizes).toEqual(SIZES);
  }, 30000);

  it("changes only the four names: the company and version stay Electron's", async () => {
    const ResEdit = await import('resedit');
    const values = (bytes) => {
      const resources = ResEdit.NtExecutableResource.from(ResEdit.NtExecutable.from(bytes));
      const [version] = ResEdit.Resource.VersionInfo.fromEntries(resources.entries);
      return version.getStringValues(version.getAllLanguagesForStringValues()[0]);
    };
    const before = values(electronExe);
    const after = values(stampBuffer(electronExe, ico));
    for (const key of Object.keys(before)) {
      expect(after[key], key).toBe(key in NAMES ? NAMES[key] : before[key]);
    }
    expect(after.CompanyName).toBe(before.CompanyName);
  }, 30000);
});
