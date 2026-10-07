/**
 * M38 (moved out of main.js, behaviour unchanged): app://pseudo/<path> -> that file inside face/dist, and nothing else.
 *
 * What it demonstrates: the same sandbox check as M3's file tools, for the page's own files.
 * The page asks for app://pseudo/assets/index.js; the path is RESOLVED first (so ../ is worked
 * out), and only then compared with the folder it must stay inside. Checking the text of the
 * path before resolving it is the classic mistake: "assets/../../main.js" looks harmless.
 *
 * There is no web server and no port (D18): Electron hands each app:// request to this
 * function, and the answer is a file read from disk or a refusal.
 */

const path = require('node:path');
const { pathToFileURL } = require('node:url');

/**
 * @param {string} requestUrl what the page asked for
 * @param {string} dist the only folder files may come from (face/dist)
 * @returns {string | null} the file to serve, or null: refused. Throws on a URL that can't be read.
 */
function fileInDist(requestUrl, dist) {
  const url = new URL(requestUrl);
  const wanted = decodeURIComponent(url.pathname === '/' ? '/index.html' : url.pathname);
  const file = path.resolve(dist, '.' + wanted);
  const inside = path.relative(dist, file);
  if (url.host !== 'pseudo' || !inside || inside.startsWith('..') || path.isAbsolute(inside)) return null;
  return file;
}

/**
 * @param {string} dist face/dist
 * @param {(fileUrl: string) => Promise<Response>} fetchFile Electron's net.fetch (a fake in tests)
 * @returns {(request: { url: string }) => Response | Promise<Response>} the handler for protocol.handle('app', ...)
 */
function serveFrom(dist, fetchFile) {
  return (request) => {
    try {
      const file = fileInDist(request.url, dist);
      if (file === null) return new Response('refused', { status: 403 });
      return fetchFile(pathToFileURL(file).toString());
    } catch {
      return new Response('bad request', { status: 400 }); // e.g. a broken %-escape in the path
    }
  };
}

module.exports = { fileInDist, serveFrom };
