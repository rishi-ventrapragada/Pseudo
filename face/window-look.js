/**
 * M39: how Pseudo's window looks from the outside: always dark, with the title bar blended into the page.
 *
 * What it demonstrates: Electron's "overlay title bar". `titleBarStyle: 'hidden'` removes Windows' own title
 * strip, and `titleBarOverlay` has Electron draw the minimize, maximize and close buttons over the page's
 * top-right corner, in our colours. The page then marks which parts of itself drag the window (the `.drag`
 * rows in theme.css) and keeps that corner free (--controls-width).
 *
 * Why this is allowed (M38's C3 says Pseudo is an ordinary window): step 0 checked, at 125% scaling, that the
 * window keeps its caption and resize frame, is listed by pseudo_hands without an id, is refused for reads,
 * focus and actions, stays under the approval popup (3 of 3), and still drags, resizes, minimizes, maximizes,
 * snaps and closes (S3). `frame: false` stays forbidden (window-remember.test.mjs).
 *
 * (M43) The buttons are as tall as the page's top row, and that row is shorter in the compact bar (the mockup's
 * 30 px) than in the full window (44 px). window-mode.js changes the height with the mode (overlayFor).
 *
 * (M44) Pseudo's own icon, for the window and its taskbar button: pseudo.ico sits beside this file, both under
 * `npm start` and inside Pseudo.exe (package.mjs copies it). tray.js uses the same file, so it is one icon.
 */

const path = require('node:path');

const ICON = path.join(__dirname, 'pseudo.ico');
const GROUND = '#171719'; // theme.css --color-ground: the page behind the buttons
const SYMBOLS = '#c9c9d1'; // theme.css --color-ink-soft
const TOP_ROW = { full: 44, compact: 30 }; // the page's top row: h-11 in TopBar.tsx, h-[30px] in CompactBar.tsx

const WINDOW_LOOK = {
  icon: ICON, // (M44) the window's and the taskbar's icon
  backgroundColor: GROUND, // shown before the page has drawn, and while resizing
  titleBarStyle: 'hidden',
  titleBarOverlay: { color: GROUND, symbolColor: SYMBOLS, height: TOP_ROW.full },
};

/** (M43) The buttons' strip for a mode: the same colours, the height of that mode's top row. */
function overlayFor(mode) {
  return { ...WINDOW_LOOK.titleBarOverlay, height: TOP_ROW[mode] ?? TOP_ROW.full };
}

/** (M43) For `new BrowserWindow`: the look, with the buttons sized for the mode the window opens in. */
function lookFor(mode) {
  return { ...WINDOW_LOOK, titleBarOverlay: overlayFor(mode) };
}

module.exports = { GROUND, ICON, SYMBOLS, TOP_ROW, WINDOW_LOOK, lookFor, overlayFor };
