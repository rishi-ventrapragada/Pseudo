/**
 * M38: where Pseudo's window may be and how big, as plain arithmetic (no Electron here).
 *
 * What it demonstrates: never trust a saved position. The place a window was last at is
 * saved to a file (window-mode.js) and read back days later. By then a second screen may be
 * unplugged or the resolution changed, and a window restored at its old coordinates would
 * open where no screen is: running, but impossible to see or reach. So every saved rectangle
 * goes through fit() before it is used: wrong values become the default, a size is held
 * between the mode's minimum and the screen, and the window is pushed fully inside a screen.
 *
 * Two modes:
 *   full     the window as before M38
 *   compact  a small bar, which GROWS upward to show the steps and the answer. Its bottom edge
 *            stays where it is, so the question box doesn't move under your cursor.
 *            (M43) The bar is the mockup's: a 30 px top row and the question row, 84 px in all. Grown, it
 *            is as tall as what it shows (fittedHeight), up to a cap: the height you last gave it.
 *
 * A rectangle is { x, y, width, height }. An "area" is a screen's work area: the screen
 * minus the taskbar. All numbers are Electron's (device-independent pixels).
 */

const SIZES = {
  full: { width: 980, height: 740, minWidth: 520, minHeight: 420 },
  compact: { width: 480, height: 84, minWidth: 360, minHeight: 84 },
};
const GROWN = { height: 440, minHeight: 160 }; // the bar while it shows a turn: the default cap, and the least
const MARGIN = 24; // the bar's default gap from the screen's corner

const isNumber = (value) => typeof value === 'number' && Number.isFinite(value);
const isRect = (rect) => Boolean(rect) && ['x', 'y', 'width', 'height'].every((key) => isNumber(rect[key]));
const clamp = (value, low, high) => Math.min(Math.max(value, low), Math.max(low, high));

/** Where a mode opens the first time: full in the middle, the bar at the bottom right. */
function defaultBounds(mode, area) {
  const { width, height } = SIZES[mode];
  if (mode === 'compact') {
    return { x: area.x + area.width - width - MARGIN, y: area.y + area.height - height - MARGIN, width, height };
  }
  return { x: area.x + Math.round((area.width - width) / 2), y: area.y + Math.round((area.height - height) / 2), width, height };
}

/** How much of `rect` lies inside `area`, in square pixels. */
function overlap(rect, area) {
  const wide = Math.min(rect.x + rect.width, area.x + area.width) - Math.max(rect.x, area.x);
  const high = Math.min(rect.y + rect.height, area.y + area.height) - Math.max(rect.y, area.y);
  return wide > 0 && high > 0 ? wide * high : 0;
}

/**
 * A saved rectangle made safe to use.
 * @param {unknown} saved what the file held (anything)
 * @param {'full' | 'compact'} mode
 * @param {object[]} areas every screen's work area, the main screen first
 * @param {number} [minHeight] the smallest height (the grown bar has its own)
 */
function fit(saved, mode, areas, minHeight = SIZES[mode].minHeight) {
  const main = areas[0];
  if (!isRect(saved)) return fit(defaultBounds(mode, main), mode, areas, minHeight);
  // The screen the window is mostly on; a window on no screen at all goes to the main one.
  const best = areas.reduce((a, b) => (overlap(saved, b) > overlap(saved, a) ? b : a), main);
  const area = overlap(saved, best) > 0 ? best : main;
  const width = clamp(Math.round(saved.width), SIZES[mode].minWidth, area.width);
  const height = clamp(Math.round(saved.height), minHeight, area.height);
  return {
    x: clamp(Math.round(saved.x), area.x, area.x + area.width - width),
    y: clamp(Math.round(saved.y), area.y, area.y + area.height - height),
    width,
    height,
  };
}

/** The bar grown to `height`: same place and width, bottom edge kept, then held on its screen.
 *  (M43) A height under the minimum is raised BEFORE the top edge is worked out: raised afterwards, by fit(),
 *  the extra height went downward and the bottom edge moved (found by window-mode.test.mjs). */
function grownFrom(bar, height, areas) {
  const tall = Math.max(isNumber(height) ? height : GROWN.height, GROWN.minHeight);
  return fit({ x: bar.x, y: bar.y + bar.height - tall, width: bar.width, height: tall }, 'compact', areas, GROWN.minHeight);
}

/** The bar a grown window shrinks back to: same place and width, bottom edge kept. */
function barFrom(grown, barHeight, areas) {
  return fit({ x: grown.x, y: grown.y + grown.height - barHeight, width: grown.width, height: barHeight }, 'compact', areas);
}

/**
 * (M43) How tall the grown bar should be: the height its content asks for, but never more than the cap (the
 * height you last dragged the grown bar to, else GROWN.height). Beyond the cap the bar's answer area scrolls.
 * grownFrom() then holds the result between GROWN.minHeight and the screen.
 */
function fittedHeight(asked, cap) {
  const most = isNumber(cap) ? cap : GROWN.height;
  return isNumber(asked) ? Math.min(asked, most) : most;
}

module.exports = { GROWN, MARGIN, SIZES, barFrom, defaultBounds, fit, fittedHeight, grownFrom };
