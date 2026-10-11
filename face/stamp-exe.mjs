// M44: writes Pseudo's icon and name into Pseudo.exe at build time (package.mjs), with resedit (D27).
//
// What it demonstrates: an .exe carries "resources" beside its code. Two of them matter here:
//   - the icon group: the pictures Explorer, Alt+Tab and the taskbar show for the file;
//   - the version block: the strings Windows shows about the program. Task Manager's name for a
//     process is its FileDescription; the file's Properties also show ProductName.
// Electron's exe says "Electron" in both (D27's old limit). This swaps the icon for pseudo.ico and
// rewrites those four strings, nothing else: CompanyName, copyright and version stay Electron's,
// because the program itself still is Electron's.
//
// Pure in the middle: stampBuffer() takes the exe's bytes and returns new bytes, so the test needs no
// files; stampExe() is the thin wrapper that reads and writes. Never run on node_modules' electron.exe:
// package.mjs runs it on its own copy in face/out.
import fs from 'node:fs';
import * as ResEdit from 'resedit';

export const NAMES = { FileDescription: 'Pseudo', ProductName: 'Pseudo', InternalName: 'Pseudo', OriginalFilename: 'Pseudo.exe' };

/**
 * @param {Buffer} exeBytes Electron's exe. A signed exe is refused (resedit's default): ours never is (D27).
 * @param {Buffer} icoBytes pseudo.ico
 * @returns {Buffer} the same exe with Pseudo's icon and names
 */
export function stampBuffer(exeBytes, icoBytes) {
  const exe = ResEdit.NtExecutable.from(exeBytes);
  const resources = ResEdit.NtExecutableResource.from(exe);

  const [group] = ResEdit.Resource.IconGroupEntry.fromEntries(resources.entries); // Electron's one icon group
  if (!group) throw new Error('the exe has no icon to replace');
  const icons = ResEdit.Data.IconFile.from(icoBytes).icons.map((item) => item.data);
  ResEdit.Resource.IconGroupEntry.replaceIconsForResource(resources.entries, group.id, group.lang, icons);

  const [version] = ResEdit.Resource.VersionInfo.fromEntries(resources.entries);
  if (!version) throw new Error('the exe has no version block');
  for (const language of version.getAllLanguagesForStringValues()) version.setStringValues(language, NAMES);
  version.outputToResourceEntries(resources.entries);

  resources.outputResource(exe);
  return Buffer.from(exe.generate());
}

/**
 * What an exe says about itself: its names, and the sizes in its icon. For the test and the live check.
 * @param {Buffer} exeBytes
 * @returns {{ names: Record<string, string>, iconSizes: number[] }}
 */
export function readStamp(exeBytes) {
  const resources = ResEdit.NtExecutableResource.from(ResEdit.NtExecutable.from(exeBytes));
  const [version] = ResEdit.Resource.VersionInfo.fromEntries(resources.entries);
  const values = version.getStringValues(version.getAllLanguagesForStringValues()[0]);
  const names = Object.fromEntries(Object.keys(NAMES).map((key) => [key, values[key]]));
  const [group] = ResEdit.Resource.IconGroupEntry.fromEntries(resources.entries);
  return { names, iconSizes: group.icons.map((icon) => icon.width || 256) }; // 256 is stored as 0
}

/** Stamps the exe at `exePath` in place. */
export function stampExe(exePath, icoPath) {
  fs.writeFileSync(exePath, stampBuffer(fs.readFileSync(exePath), fs.readFileSync(icoPath)));
}
