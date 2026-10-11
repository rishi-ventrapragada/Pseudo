# M44: Icon and name

## The concept in one paragraph

Until M44, Pseudo looked like Electron from the outside. The taskbar showed Electron's icon, the tray showed a tiny "P" drawn in code, and Task Manager called the process "Electron". M44 gives Pseudo its own icon: an eye whose pupil is a camera aperture, chosen from Claude Design prototypes. The same icon now appears on the window, the taskbar, the tray and the `.exe`, and beside the name inside the window. The new idea is that **an icon and a program's name are data stored in files**, not code. An `.ico` file holds one picture per size. An `.exe` carries **resources** next to its code, including an icon and a version block of strings that Windows reads. M44 writes both by hand, with no packaging tool.

## Web-dev analogy

**`pseudo.ico`** is a favicon with `srcset`. The browser (here, Windows) picks the picture closest to the size it needs: 16 px in the tray, 40 px on a taskbar at 125%, 256 px for a large file icon.

**The exe's version block** is a `package.json` baked into the binary. `FileDescription` is like `description`, and it's what Task Manager shows. `ProductName` is like `productName`.

**`make-icon.js`** is a build script like `vite build`. It's run once when the source changes, and its output (`pseudo.ico`) is committed, the way some projects commit generated favicons.

**The two drawings** are responsive design. Below 32 px the detailed iris would turn to mush, so a simpler drawing is shown, the same way a site swaps a full logo for a logomark on mobile.

## What was built (file by file)

| File | What it does |
|---|---|
| `face/src/assets/pseudo-icon.svg` | The detailed eye (fine iris, aperture pupil), for 32 px and up. |
| `face/src/assets/pseudo-icon-small.svg` | The plain eye (white iris, round pupil), for 16 to 24 px and inside the window. |
| `face/ico.js` | The `.ico` format, written and read by hand. |
| `face/make-icon.js` | `npm run icon`: each size drawn on a canvas by the repo's Electron, packed into `pseudo.ico`. |
| `face/pseudo.ico` | The built icon: 8 sizes, 30 KB, committed (the repo's first binary file). |
| `face/window-look.js` | `ICON`: the window's (and so the taskbar's) icon. |
| `face/tray.js` | The tray uses the same `ICON`; the pixel-map "P" is gone. |
| `face/stamp-exe.mjs` | Build time: writes the icon and the names into `Pseudo.exe`, with `resedit`. |
| `face/package.mjs` | Copies `pseudo.ico` in and stamps the exe. |
| `face/src/components/Wordmark.tsx` | The eye, then "Pseudo", in the sidebar's and the bar's top rows. |

## Walkthrough of the key code

**1. A file format is bytes in an agreed order.** `ico.js` writes an `.ico` in three parts: a 6-byte header, one 16-byte entry per picture, then the pictures themselves:

```js
header.writeUInt16LE(1, 2); // 1 = icon (2 would be a cursor)
entry.writeUInt8(size >= 256 ? 0 : size, 0); // width: one byte, so 256 is written as 0
entry.writeUInt32LE(png.length, 8);
entry.writeUInt32LE(offset, 12);           // where this picture starts in the file
```

A width fits in one byte (0 to 255), so 256 has to be written as 0. Since Windows Vista, each picture can simply be a whole PNG file.

**2. A browser engine is a fine image tool.** Windows wants square PNGs at fixed sizes, and we have vector drawings. `make-icon.js` opens a hidden, sandboxed window, draws the SVG onto a `<canvas>` at exactly the size needed, and reads it back as a PNG:

```js
canvas.getContext('2d').drawImage(image, 0, 0, ${size}, ${size});
return canvas.toDataURL('image/png').split(',')[1];
```

Each size is drawn from the vector at that size, not shrunk from a big picture, so its edges stay sharp. The canvas keeps the see-through corners, so we never need a see-through window. That matters, because C3 forbids one.

**3. One icon, one place.** `window-look.js` defines the path once, and the tray asks for it:

```js
const ICON = path.join(__dirname, 'pseudo.ico');           // window-look.js
new electron.Tray(electron.nativeImage.createFromPath(ICON)); // tray.js
```

A test checks that, of the files that go into `Pseudo.exe`, only `window-look.js` names `pseudo.ico`.

**4. An exe has resources.** `stamp-exe.mjs` changes only what Windows shows about the program:

```js
ResEdit.Resource.IconGroupEntry.replaceIconsForResource(resources.entries, group.id, group.lang, icons);
for (const language of version.getAllLanguagesForStringValues()) version.setStringValues(language, NAMES);
```

`NAMES` holds `FileDescription`, `ProductName`, `InternalName` and `OriginalFilename`. The company and the version stay Electron's, because the program inside still is Electron. The middle function takes bytes and returns bytes, so its test stamps a copy of Electron's 246 MB exe in memory and never writes a file.

**5. Decoration has no name.** In the window, the icon is an `<img>` with `alt=""`:

```tsx
<img src={icon} alt="" draggable={false} className={cn('shrink-0', look.icon)} />
<span className={look.word}>Pseudo</span>
```

The word beside it already says "Pseudo". An `alt="Pseudo"` would make screen readers say it twice. Vite copies the SVG into `dist` as a file (`assetsInlineLimit: 0`), and the page's security policy allows only its own files.

## What happens when you run it (annotated real output)

```
exe: Pseudo.exe | names Windows reads: {'FileDescription': 'Pseudo', 'ProductName': 'Pseudo', ...,
     'CompanyName': 'GitHub, Inc.'}
exe icon, large (40 px): differs from pseudo.ico by 0.0 | from Electron's icon by 60.6
```

Windows itself reads the names. It extracts the exe's icon at this 125% screen's 40 px, and that icon matches our file exactly (0.0 is the average difference per colour, out of 255).

```
window (taskbar) icon small (20 px): differs from pseudo.ico by 0.0 | from Electron's by 54.3
READS: the fake window, never Pseudo's own: 5 of 5
Start with Windows: ... off: removed True, values naming Pseudo.exe 0 | on: our value exactly True, values naming Pseudo.exe 1
```

```
tray: ... | our button found True | the hidden-icons flyout had to be opened True
tray button (50 x 50 px around our icon): blue pixels (the old P was blue) 0 | light pixels (the eye) 43
```

Two honest notes:
- **The first tray check was a script mistake.** Pressing Ctrl+Alt+Enter while another window is in front *brings Pseudo forward*. It only hides Pseudo when Pseudo is already in front.
- **Windows' saved picture of the tray icon was stale.** Windows remembers each program's tray icon in the registry, from the first time it saw it: still the old blue "P" from 7 October. So the check looked at Pseudo's own tray button instead, capturing only its pixels (Backlog).

The unsigned exe started 3 of 3 with no warning, and the M15 battery scored 12/12.

## Try this (3 small experiments that break or change something)

Run each in `face\`, then put the line back.

1. In `ico.js`, change `entry.writeUInt8(size >= 256 ? 0 : size, 0);` to `entry.writeUInt8(size, 0);`. Run `npx vitest run icon.test.mjs`. You get `RangeError: ... must be >= 0 and <= 255. Received 256`, because a width has only one byte.
2. In `stamp-exe.mjs`, delete `FileDescription: 'Pseudo', ` from `NAMES`. Run `npx vitest run stamp-exe.test.mjs`. "afterwards it says Pseudo" fails, because Task Manager would still say Electron.
3. In `src/components/Wordmark.tsx`, change `alt=""` to `alt="Pseudo"`. Run `npx vitest run src/components/Wordmark.test.tsx`. "screen readers hear the name once" fails, and so do the two tests that expect a decorative icon.

## Check yourself

1. Why does `pseudo.ico` hold eight pictures instead of one big one?
2. Why is each size drawn from the SVG at that size, instead of shrinking the 256 px picture?
3. What does Task Manager read to name a process, and where is it stored?
4. Why do the company and the version stay Electron's?
5. Why does the icon beside the name have `alt=""`?

<details>
<summary>Answers</summary>

1. Windows picks the picture closest to the size it needs (16 px in the tray, 40 px on the taskbar here, 256 px for a large icon). The small sizes even use a simpler drawing, because fine lines can't fit in 16 px.
2. Drawing the vector at the target size puts the edges on that size's pixel grid, so they stay sharp. Shrinking a big picture blurs them.
3. The exe's `FileDescription`, a string in the version block. That's one of the exe's resources, stored in the file next to its code.
4. The program inside is still Electron's binary. M44 changes only what Windows shows as Pseudo's: the icon and the names.
5. The word next to it already says "Pseudo". A named icon would make screen readers read the name twice.

</details>

## How this connects to Pseudo's final architecture

D27 packaged Pseudo by hand and listed "the exe still says Electron" as its known limit. M44 removes that limit with one build-time step, still with no packaging tool. The icon is one file, used everywhere, and the window shows it with the name. M45, the last milestone of Phase 10, rewrites the README for GitHub with screenshots made from fake data, now with Pseudo's own icon in them.
