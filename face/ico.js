/**
 * M44: the Windows icon file (.ico), written and read by hand, with no package.
 *
 * What it demonstrates: a file format is just bytes in an agreed order. An .ico is
 *   a 6-byte header        (0, 1 = "an icon", how many pictures),
 *   one 16-byte entry each  (width, height, colour depth, how many bytes, where they start),
 *   then the pictures       (since Windows Vista each may simply be a whole PNG file).
 * Windows picks the picture closest to the size it needs: 16 px in the tray, 24-32 on the
 * taskbar, 256 for a large file icon. So one .ico can hold a different drawing per size,
 * which is how Pseudo's icon keeps its fine lines only where there is room for them.
 *
 * Used by make-icon.js (build time) and icon.test.mjs. Pure functions: Buffers in, Buffers out.
 */

const SIZES = [16, 20, 24, 32, 40, 48, 64, 256]; // every size Windows asks for at 100% to 200% scaling
const SMALL_UP_TO = 24; // these sizes and below use the simpler drawing (pseudo-icon-small.svg)
const HEADER = 6;
const ENTRY = 16;
const PNG_SIGNATURE = '89504e470d0a1a0a';

/**
 * @param {{ size: number, png: Buffer }[]} images square PNGs, one per size
 * @returns {Buffer} the .ico file
 */
function packIco(images) {
  const header = Buffer.alloc(HEADER);
  header.writeUInt16LE(0, 0); // reserved, always 0
  header.writeUInt16LE(1, 2); // 1 = icon (2 would be a cursor)
  header.writeUInt16LE(images.length, 4);

  let offset = HEADER + ENTRY * images.length; // the first picture starts right after the entries
  const entries = images.map(({ size, png }) => {
    const entry = Buffer.alloc(ENTRY);
    entry.writeUInt8(size >= 256 ? 0 : size, 0); // width: one byte, so 256 is written as 0
    entry.writeUInt8(size >= 256 ? 0 : size, 1); // height
    entry.writeUInt8(0, 2); // palette colours: none (full colour)
    entry.writeUInt8(0, 3); // reserved
    entry.writeUInt16LE(1, 4); // colour planes
    entry.writeUInt16LE(32, 6); // bits per pixel: 8 each for red, green, blue and see-through
    entry.writeUInt32LE(png.length, 8);
    entry.writeUInt32LE(offset, 12);
    offset += png.length;
    return entry;
  });
  return Buffer.concat([header, ...entries, ...images.map((image) => image.png)]);
}

/**
 * Reads an .ico back into its pictures (for the tests, and for checking a built icon).
 * @param {Buffer} file
 * @returns {{ size: number, png: Buffer }[]}
 */
function readIco(file) {
  if (file.length < HEADER || file.readUInt16LE(0) !== 0 || file.readUInt16LE(2) !== 1) throw new Error('not an icon file');
  const count = file.readUInt16LE(4);
  const images = [];
  for (let n = 0; n < count; n += 1) {
    const at = HEADER + ENTRY * n;
    const length = file.readUInt32LE(at + 8);
    const offset = file.readUInt32LE(at + 12);
    images.push({ size: file.readUInt8(at) || 256, png: file.subarray(offset, offset + length) });
  }
  return images;
}

/**
 * A PNG's width and height. They sit in its first chunk (IHDR), right after the 8-byte signature.
 * @param {Buffer} png
 * @returns {{ width: number, height: number }}
 */
function pngSize(png) {
  if (png.subarray(0, 8).toString('hex') !== PNG_SIGNATURE) throw new Error('not a PNG');
  return { width: png.readUInt32BE(16), height: png.readUInt32BE(20) };
}

module.exports = { SIZES, SMALL_UP_TO, packIco, pngSize, readIco };
