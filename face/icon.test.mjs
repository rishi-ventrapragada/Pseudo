// M44: the icon files. ico.js writes and reads the .ico format; the committed pseudo.ico must hold every size
// Windows asks for, each a real square PNG; the two SVGs it is made from must be plain drawings that can't
// load or run anything (the page shows one of them, under its security policy).
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { describe, expect, it } from 'vitest';

const { SIZES, SMALL_UP_TO, packIco, pngSize, readIco } = createRequire(import.meta.url)('./ico.js');
const read = (file) => readFileSync(new URL(file, import.meta.url));

/** The first 24 bytes of a PNG: its signature, then an IHDR chunk saying width x height. Enough for pngSize. */
function fakePng(width, height, filler = 0) {
  const png = Buffer.alloc(32, filler);
  Buffer.from('89504e470d0a1a0a', 'hex').copy(png, 0);
  png.writeUInt32BE(13, 8);
  png.write('IHDR', 12, 'ascii');
  png.writeUInt32BE(width, 16);
  png.writeUInt32BE(height, 20);
  return png;
}

describe('ico.js', () => {
  it('packs pictures and reads them back, byte for byte, 256 px included (written as 0)', () => {
    const images = [16, 32, 256].map((size, n) => ({ size, png: fakePng(size, size, n + 1) }));
    const file = packIco(images);
    expect([...file.subarray(0, 6)]).toEqual([0, 0, 1, 0, 3, 0]); // reserved, "an icon", three pictures
    expect(file[6 + 16 * 2]).toBe(0); // the 256 px entry's width byte
    const back = readIco(file);
    expect(back.map((image) => image.size)).toEqual([16, 32, 256]);
    back.forEach((image, n) => expect(image.png.equals(images[n].png)).toBe(true));
  });

  it('refuses what is not an icon or not a PNG', () => {
    expect(() => readIco(Buffer.from('not an icon at all'))).toThrow('not an icon file');
    expect(() => pngSize(Buffer.alloc(32))).toThrow('not a PNG');
  });

  it('the simpler drawing covers the small sizes only', () => {
    expect(SIZES.filter((size) => size <= SMALL_UP_TO)).toEqual([16, 20, 24]);
  });
});

describe('the committed pseudo.ico', () => {
  const images = readIco(read('./pseudo.ico'));

  it('holds every size Windows asks for, once each', () => {
    expect(images.map((image) => image.size)).toEqual(SIZES);
  });

  it('each picture is a square PNG of exactly its size', () => {
    for (const { size, png } of images) expect(pngSize(png)).toEqual({ width: size, height: size });
  });
});

describe('the SVGs it is made from', () => {
  for (const name of ['pseudo-icon.svg', 'pseudo-icon-small.svg']) {
    const svg = read(`./src/assets/${name}`).toString('utf8');

    it(`${name} is drawn on the 32 x 32 grid`, () => {
      expect(svg).toMatch(/^<svg xmlns="http:\/\/www\.w3\.org\/2000\/svg" viewBox="0 0 32 32" width="\d+" height="\d+">/);
    });

    it(`${name} can't load or run anything`, () => {
      for (const word of ['<script', '<image', '<foreignObject', '<style', 'href', 'url(', '@import', 'on' + 'load']) {
        expect(svg.includes(word), word).toBe(false);
      }
      expect(svg.match(/https?:/g)).toEqual(['http:']); // only the xmlns, which names the format and loads nothing
    });
  }
});
