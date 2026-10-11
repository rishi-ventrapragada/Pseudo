/**
 * M44: makes face/pseudo.ico from the two SVGs in src/assets, with the Electron already in the repo.
 * Run it by hand when an SVG changes: `npm run icon`. The .ico is committed, so `npm start` and
 * `npm run package` never need this step.
 *
 * What it demonstrates: a browser engine is a perfectly good image tool. Windows wants square
 * PNGs at fixed sizes; we have vector drawings (SVG). A hidden, sandboxed window draws each SVG onto
 * a <canvas> at the exact size, and the canvas hands back a PNG with its see-through corners kept.
 * (The window itself is an ordinary one that is never shown: a see-through window is not needed, and
 * window-remember.test.mjs forbids one anyway.) ico.js then packs the PNGs into one .ico file.
 *
 * Each size is drawn from scratch at that size, not shrunk from a big picture, so its edges are sharp.
 * Up to 24 px the simpler drawing is used: the fine iris lines can't survive a 16 px grid.
 */

const fs = require('node:fs');
const path = require('node:path');
const { app, BrowserWindow } = require('electron');
const { SIZES, SMALL_UP_TO, packIco, pngSize } = require('./ico');

const ASSETS = path.join(__dirname, 'src', 'assets');
const DETAILED = path.join(ASSETS, 'pseudo-icon.svg');
const SMALL = path.join(ASSETS, 'pseudo-icon-small.svg');
const OUT = path.join(__dirname, 'pseudo.ico');

/** The SVG's own width and height set to `size`, so the engine draws it at that size. */
function atSize(svg, size) {
  return svg.replace(/width="\d+" height="\d+"/, `width="${size}" height="${size}"`);
}

/** Code run INSIDE the hidden page: draw the SVG on a canvas, return the PNG as base64 text. */
function drawScript(svg, size) {
  const data = `data:image/svg+xml;base64,${Buffer.from(svg).toString('base64')}`;
  return `(async () => {
    const image = new Image();
    image.src = ${JSON.stringify(data)};
    await image.decode();
    const canvas = document.createElement('canvas');
    canvas.width = ${size};
    canvas.height = ${size};
    canvas.getContext('2d').drawImage(image, 0, 0, ${size}, ${size});
    return canvas.toDataURL('image/png').split(',')[1];
  })()`;
}

async function makeIcon() {
  const drawings = { small: fs.readFileSync(SMALL, 'utf8'), detailed: fs.readFileSync(DETAILED, 'utf8') };
  const win = new BrowserWindow({ show: false, webPreferences: { sandbox: true, contextIsolation: true } });
  await win.loadURL('about:blank');
  const images = [];
  for (const size of SIZES) {
    const svg = atSize(size <= SMALL_UP_TO ? drawings.small : drawings.detailed, size);
    const png = Buffer.from(await win.webContents.executeJavaScript(drawScript(svg, size)), 'base64');
    const drawn = pngSize(png);
    if (drawn.width !== size || drawn.height !== size) throw new Error(`${size} px came out ${drawn.width} x ${drawn.height}`);
    images.push({ size, png });
  }
  win.destroy();
  fs.writeFileSync(OUT, packIco(images));
  console.log(`icon: wrote ${OUT}: ${SIZES.join(', ')} px, ${fs.statSync(OUT).size} bytes`);
}

app.whenReady()
  .then(makeIcon)
  .then(() => app.quit())
  .catch((error) => {
    console.error(`icon: ${error.message}`);
    app.exit(1);
  });
