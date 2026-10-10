// M38: the fake window, screen and store shared by window-mode.test.mjs and window-remember.test.mjs.
// The window records what was done to it and, like this laptop's 125% screen, reports itself one pixel
// bigger than it was asked to be. Test help only: it is not on package.mjs's list, so it never ships.
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const { WindowMode } = require('./window-mode.js');
const { defaultBounds } = require('./window-bounds.js');

export const AREA = { x: 0, y: 0, width: 1536, height: 816 };
export const screen = { getPrimaryDisplay: () => ({ id: 1, workArea: AREA }), getAllDisplays: () => [{ id: 1, workArea: AREA }] };
export const FULL = defaultBounds('full', AREA);
export const BAR = defaultBounds('compact', AREA);

export function fakeWindow({ visible = true, drift = 1 } = {}) {
  const win = {
    bounds: null, top: false, min: null, maximized: false, visible, handlers: {}, tops: [],
    maximizable: true, overlay: null, // (M43) the title bar's buttons
    isDestroyed: () => false,
    isVisible: () => win.visible,
    isMaximized: () => win.maximized,
    isMinimized: () => false,
    unmaximize: () => { win.maximized = false; },
    setMinimumSize: (width, height) => { win.min = [width, height]; },
    setBounds: (rect) => { win.bounds = { ...rect, width: rect.width + drift, height: rect.height + drift }; },
    getBounds: () => ({ ...win.bounds }),
    setAlwaysOnTop: (on) => { win.top = on; win.tops.push(on); },
    setMaximizable: (on) => { win.maximizable = on; },
    setTitleBarOverlay: (options) => { win.overlay = options; },
    on: (name, handler) => { win.handlers[name] = handler; },
    byUser: (rect) => { win.bounds = rect; win.handlers.resized(); }, // you dragged an edge, then let go
  };
  return win;
}

/** A WindowMode on a fake window. `saved` is what the store's file holds; `written` collects what is saved. */
export function setup(saved = null, windowOptions) {
  const written = [];
  const win = fakeWindow(windowOptions);
  const mode = new WindowMode(() => win, screen, { read: () => saved, write: (data) => written.push(data) });
  mode.attach(win);
  return { mode, win, written };
}

/** One of the brain's tool events, as the bridge sends it. */
export const tool = (kind) => ({ type: 'event', kind, data: { name: 'read_active_window' } });
