# M43: The compact bar, redesigned

## The concept in one paragraph

M38 built the compact bar: the same window, made small and always on top. M43 redraws it from the approved mockup. It has a 30 px top row ("Pseudo", a short note, Full window), and a question row with the mic, the look-at chip, the box and Ask. While it works, waits for your approval or answers, the bar grows upward. The new idea is **who decides the window's size**. Only the page knows how tall its content is. Only the main process may size the window, and it must keep the bar on screen, under your cap, and never remember a size you didn't set. So the page **measures and reports** a number, and the main process **decides**. The window itself also changes: Windows' buttons shrink to the 30 px row, and the bar can't be maximized.

## Web-dev analogy

**The page measuring itself** is an iframe that posts its content height to the parent page (`postMessage({ height })`), and the parent resizes the iframe. The iframe never resizes itself; it only reports.

**`ResizeObserver`** is the browser's own "tell me when this element's size changes". It's like a `useEffect` that re-runs on layout instead of on state.

**`window-top.js`** is extracting a custom hook from a component that got too long: the same logic, moved unchanged, behind a small interface.

**Device-independent pixels (DIPs)** are CSS pixels. At 125% scaling one DIP is 1.25 screen pixels, so a 480 x 84 bar covers 600 x 105 real pixels.

## What was built (file by file)

| File | What it does |
|---|---|
| `face/window-look.js` | The title bar's button height per mode: 44 px full, 30 px bar (`overlayFor`). |
| `face/window-mode.js` | Sets that height and switches maximize off in the bar (`shape`); takes the page's height (`setGrown`). |
| `face/window-top.js` | The always-on-top rules, moved out of `window-mode.js` unchanged (it would have passed 200 lines). |
| `face/window-bounds.js` | The bar's sizes (480 x 84, at least 360 x 84); `fittedHeight` and `grownFrom` for the grown bar. |
| `face/src/useCompact.ts` | `useBarFit`: measures the grown bar and sends its height. |
| `face/src/components/CompactBar.tsx` | The bar: top row, grown area, question row. |
| `face/src/components/BarTurn.tsx` | The grown area: your question, then the working word, the amber box, or the answer and steps. |
| `face/src/components/LookingAtChip.tsx` | A short form for the bar: the eye and the name only. |
| `face/src/theme.css` | `--bar-controls-width`: room for Windows' two buttons in the bar. |

## Walkthrough of the key code

**1. The page measures, the main process decides.** `useBarFit` watches the grown area and the question row:

```ts
const height = barHeight(t, c, b);               // top row + content + question row, rounded up
if (Math.abs(height - sent) < STEP) return;      // under 2 px: not worth resizing the window
sent = height;
window.pseudo.send({ type: 'window_mode', grown: true, height });
```

The page only says a number. The main process then decides what it means:

```js
setGrown(on, height = null) {
  const fitted = on && Number.isFinite(height) ? Math.round(height) : null;
  ...
}
```

`Number.isFinite` matters: the page is sandboxed and display only, so the main process checks what it sends. A height like `'300'` (a string), `NaN` or `Infinity` is ignored and the bar grows to the cap, as before M43; a test sends exactly those.

**2. Under the cap, never under the minimum, bottom edge kept.** `fittedHeight` caps the page's height at the height you last dragged the grown bar to (else 440). Then `grownFrom` grows the bar upward:

```js
const tall = Math.max(isNumber(height) ? height : GROWN.height, GROWN.minHeight);
return fit({ x: bar.x, y: bar.y + bar.height - tall, width: bar.width, height: tall }, ...);
```

The order of these two lines is the bug a test found. At first the height was raised to the minimum later, inside `fit()`, **after** the top edge (`y`) was worked out. The extra height then went downward, and the bar's bottom edge moved. Raising it first, as above, keeps the bottom where it was.

**3. Fitted heights are never saved.** M38's rule: only sizes **you** set are remembered. A height the page asked for isn't yours, so it never reaches `window-mode.json`. Only dragging the grown bar sets the cap (`grownHeight`).

**4. The title bar follows the mode.** Since M39, Electron draws Windows' minimize, maximize and close buttons over the page (the **overlay title bar**). M43 changes their height with the mode:

```js
shape() {
  win.setTitleBarOverlay(overlayFor(this.mode));    // 30 px in the bar, 44 px in the full window
  win.setMaximizable(this.mode !== 'compact');       // a maximized bar makes no sense
}
```

**5. Always on top, unchanged, in its own file.** `window-top.js` keeps M38's one rule:

```js
win.setAlwaysOnTop(this.isBar() && !this.waiting && win.isVisible());
```

On top only as the bar, only while no tool waits (its approval popup must stay above), and only while visible.

**6. Found live: no maximize button at all.** The plan expected Electron to grey out the maximize button. The live screenshots showed it isn't drawn at all, which left an empty gap of one button between Full window and minimize. The bar now keeps room for two buttons:

```css
:root { color-scheme: dark; --controls-width: 138px; --bar-controls-width: 92px; }
```

## What happens when you run it (annotated real output)

The live check ran the packaged `Pseudo.exe` with fake windows and a temporary profile:

```
C5 the bar by default: visible (600, 107) px = 480 x 84 at scale 1.25 (True) | outer rectangle (616, 115)
BAR: top row drags True | close button at 15 px True, at 37 px False (30 px buttons: True, False) | can maximize False
```

At 125%, 480 x 84 DIPs are 600 x 105 screen pixels (2 px of rounding is allowed). The **outer rectangle** is bigger because Windows counts the invisible resize border around the window. The first run measured that and failed; it was a check-script mistake. A **hit test** asks Windows "what is at this point?": at 15 px down it's the close button, at 37 px it isn't, so the buttons are 30 px tall.

```
 C1 read 1: ... fake word and read_active_window only False | tools ['read_active_window', 'list_open_windows'] | C4 answer visible and inside the bar True, True | grown to 256 px, bottom edge kept True
C1 reads of the fake window from the small bar: 8 of 10 | ... | C4 answer visible and inside the bar 10 of 10 | chip named 'Windows PowerShell' 10 of 10
```

C1 is a miss at 8 of 10. In two reads the model also listed the windows after reading the right one, and the rule counts any extra call as a miss. The bar did its part every time: the right window, the chip, the answer inside the bar, the bottom edge kept.

```
C2 popups above the bar and clickable, the amber line in the bar and no working word: 12 of 12
IDLE 4 BAR visible: 601 s, CPU s 2.05 (I1 limit 3) | in RAM peak 249 MB (I2 limit 400) | ... keyboard at the start: our fake notes, at the end: our fake notes
```

The popups were above the bar 12 of 12, and idle cost stayed within the limits in all four periods (1.09, 1.12, 1.38, 2.05). The M15 battery scored 12/12.

## Try this (3 small experiments that break or change something)

Run each in `face\`, then put the line back.

1. In `window-bounds.js`'s `grownFrom`, change `const tall = Math.max(isNumber(height) ? height : GROWN.height, GROWN.minHeight);` to `const tall = isNumber(height) ? height : GROWN.height;`. Run `npx vitest run window-mode.test.mjs`. "grows to the height its content asks for, bottom edge kept" fails: that is the bug the test found.
2. In `window-mode.js`'s `shape()`, change `win.setMaximizable(this.mode !== 'compact');` to `win.setMaximizable(true);`. Run `npx vitest run window-mode.test.mjs`. The test "the bar's buttons are as tall as its 30 px row and it cannot be maximized" fails.
3. In `src/theme.css`, change `--bar-controls-width: 92px` to `138px`. Run `npx vitest run window-look.test.mjs`: the two-buttons test fails. With `npm run package` you would also see the gap from the live check again.

## Check yourself

1. Why does the page send a height instead of resizing the window itself?
2. Why is a height the page asked for never saved, while your drag of the grown bar is?
3. Why must the minimum be applied before the top edge is worked out?
4. The bar opened 616 x 115 by Windows' outer rectangle. Why is that still a 480 x 84 bar?
5. In C1, the model read the right window and then listed the windows. Why is that a miss, when the bar did nothing wrong?

<details>
<summary>Answers</summary>

1. Only the main process may size windows (the page is sandboxed and display only), and only it knows the screen, your cap and the minimum. The page knows only its own content, so it reports, and the main process decides.
2. M38's rule: only sizes you set are remembered. A fitted height changes with every answer, so saving it would overwrite the size you chose.
3. The bar grows upward: its top is its bottom minus its height. If the height is raised after the top is set, the extra height goes downward and the bottom edge moves.
4. Since M39, Windows' outer rectangle includes an invisible resize border (8 px left, right and bottom here). The visible bar was 600 x 107 screen pixels, which is 480 x 84 DIPs at 125%, within rounding.
5. C1 is fixed in the plan, before any measurement: a read counts only if `read_active_window` was the only tool. It measures the whole question, so a model habit counts too. It is recorded, not tuned away (Backlog).

</details>

## How this connects to Pseudo's final architecture

The bar is still the same window as the full Pseudo (M38's O1), so everything the full window can do stays one click away, and the safety rules hold unchanged: the bar is an ordinary window that `pseudo_hands` never reads or acts on, and it steps down whenever a popup may wait. "The page reports, the main process decides" is D11 again, inside the face: the display measures, and the rules live where the page can't change them. M44 gives Pseudo its own icon and name; M45 rewrites the README for GitHub.
