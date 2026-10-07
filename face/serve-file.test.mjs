// M38: the page's files come from face/dist and nowhere else (serve-file.js). The code moved out of main.js
// unchanged; it had no tests of its own there, because main.js needs Electron to load.
import { createRequire } from 'node:module';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { describe, expect, it } from 'vitest';

const { fileInDist, serveFrom } = createRequire(import.meta.url)('./serve-file.js');
const DIST = path.resolve('fake-face', 'dist');

describe('fileInDist', () => {
  it('serves index.html for the bare address, and files inside dist', () => {
    expect(fileInDist('app://pseudo/', DIST)).toBe(path.join(DIST, 'index.html'));
    expect(fileInDist('app://pseudo/index.html', DIST)).toBe(path.join(DIST, 'index.html'));
    expect(fileInDist('app://pseudo/assets/index-abc.js', DIST)).toBe(path.join(DIST, 'assets', 'index-abc.js'));
  });

  it('refuses anything that resolves outside dist, however it is spelled', () => {
    for (const url of ['app://pseudo/..%2Fmain.js', 'app://pseudo/assets/..%2F..%2Fmain.js',
                       'app://pseudo/..%5C..%5Cmain.js', 'app://pseudo/C:%5CWindows%5Cwin.ini']) {
      expect(fileInDist(url, DIST), url).toBeNull();
    }
  });

  it('plain ../ never gets that far: the URL itself folds it away, and the file stays inside dist', () => {
    expect(fileInDist('app://pseudo/../../main.js', DIST)).toBe(path.join(DIST, 'main.js'));
    expect(fileInDist('app://pseudo/%2e%2e/%2e%2e/main.js', DIST)).toBe(path.join(DIST, 'main.js'));
  });

  it('refuses another host', () => {
    expect(fileInDist('app://other/index.html', DIST)).toBeNull();
  });
});

describe('serveFrom', () => {
  const fetched = [];
  const serve = serveFrom(DIST, (fileUrl) => { fetched.push(fileUrl); return new Response('the file'); });

  it('fetches the file from disk as a file:// address', async () => {
    const response = await serve({ url: 'app://pseudo/index.html' });
    expect(await response.text()).toBe('the file');
    expect(fetched).toEqual([pathToFileURL(path.join(DIST, 'index.html')).toString()]);
  });

  it('answers 403 for a refused path and 400 for a broken one, fetching nothing', async () => {
    fetched.length = 0;
    expect((await serve({ url: 'app://pseudo/..%2Fmain.js' })).status).toBe(403);
    expect((await serve({ url: 'app://pseudo/%E0%A4%A' })).status).toBe(400);
    expect((await serve({ url: 'not a url' })).status).toBe(400);
    expect(fetched).toEqual([]);
  });
});
