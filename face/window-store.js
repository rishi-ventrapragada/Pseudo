/**
 * M38: the remembered window sizes, in one small JSON file in the profile folder (window-mode.json).
 *
 * What it demonstrates: a settings file is input, like anything else read from disk. It can be
 * missing (first start), half-written, or edited by hand. So reading never throws: anything
 * that isn't a JSON object is "nothing remembered", and window-mode.js falls back to the
 * defaults. Writing never throws either: on a full disk the window still works, it just forgets.
 * The numbers inside are checked later, each time they are used (fit() in window-bounds.js).
 *
 * Why a file and not the page's localStorage (where the switches are remembered): the main
 * process needs the size BEFORE the page exists, to create the window at the right place.
 */

/**
 * @param {string} file where the sizes are kept
 * @param {{ readFileSync: Function, writeFileSync: Function }} fs Node's fs (a fake in tests)
 */
function fileStore(file, fs) {
  return {
    read() {
      try {
        const data = JSON.parse(fs.readFileSync(file, 'utf8'));
        return typeof data === 'object' && data !== null ? data : null;
      } catch {
        return null;
      }
    },
    write(data) {
      try {
        fs.writeFileSync(file, JSON.stringify(data, null, 2));
      } catch {
        // a full disk or a read-only profile: not remembered this time
      }
    },
  };
}

module.exports = { fileStore };
