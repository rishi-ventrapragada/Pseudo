# M39: Design system and app shell

## The concept in one paragraph

Pseudo got a new face: a dark sidebar, a centred conversation, a rounded question box with the mic inside, and a Settings dialog for the switches you change once a month. Underneath, three ideas did the work. **Design tokens**: every colour, font and size comes from one file (`theme.css`), named by what it is for (`ground`, `ink`, `muted`, `wait`), and Tailwind turns each name into classes. **A probe before the build**: the page's security policy refuses some things popular libraries do, so a scratch copy tested every candidate first, and the build used only what passed. **A blended title bar**: Windows' title strip is gone and Electron draws the minimize, maximize and close buttons over the page, but only after the probe proved Pseudo is still an ordinary window to `pseudo_hands` and to Windows.

## Web-dev analogy

**Tokens** are your Tailwind config's `theme.extend.colors`, or CSS variables in `:root`, the way most design systems ship. Here they live in CSS (`@theme` in Tailwind v4), and Tailwind's own palette is switched off, like deleting `colors` from the config: `bg-red-500` simply doesn't exist, so nobody can add a colour the mockup didn't have.

**The security policy** is the same Content-Security-Policy header you'd set on a site, here as a `<meta>` tag: `default-src 'self'`. It is why a "just add a library" plan needed checking. Radix's Dialog adds a `<style>` tag at run time to stop the page scrolling, and the policy refuses inline styles, the same way it refuses inline scripts.

**The blended title bar** is the desktop version of a full-bleed header. VS Code, Slack and Discord all do it. On the web you'd never think about it. On a desktop it decides whether Windows still treats you as a normal window.

## What was built (file by file)

| File | What it does |
|---|---|
| `face/src/theme.css` | Tailwind, the bundled Geist fonts, the tokens, the focus ring, reduced motion, drag rows, scrollbars. |
| `face/src/answer.css` | Markdown spacing (Tailwind's reset removes it) and the masked-item chips. |
| `face/src/lib/cn.ts` | Five lines that join class names (shadcn uses two packages for this). |
| `face/src/components/ui/` | `Button`, `Tip` (tooltip), `Switch`, `Disclosure` (show/hide), `Dialog` (the native `<dialog>`). |
| `face/src/components/` | `Sidebar`, `SessionList`, `TopBar`, `Conversation`, `TurnView`, `BottomArea`, `MicButton`, `SettingsDialog`, `SettingRow`, `Stopped`, `CompactBar`. |
| `face/window-look.js` | Always dark; `titleBarStyle: 'hidden'` with Electron's overlay buttons, in the token colours. |
| `face/src/App.tsx` | Now only wires state to the parts. Its logic is unchanged. |
| Tests | 200-line limit for every source file; C3's scan of every folder; contrast for 38 colour pairs; every button named; the compact bar's render test. |

Gone: `styles.css`, `banner.css`, `compact.css`, `Sessions.tsx`, `VoiceControls.tsx`.

## Walkthrough of the key code

**1. A token becomes classes.** In `theme.css`:

```css
@theme static {
  --color-*: initial;          /* Tailwind's own palette: off */
  --color-ground: #171719;     /* the conversation */
  --color-wait: #f5c26b;       /* amber: an approval popup is waiting */
}
```

`--color-ground` gives `bg-ground`, `text-ground` and `border-ground`. `static` writes every token out as a real CSS variable too, so plain CSS (`answer.css`) and JavaScript (`window-look.js`) use the same values. A test checks `window-look.js`'s colours against `theme.css`, so they can't drift.

**2. A dialog without the library.** The probe showed Radix's Dialog breaks the policy. The browser's own `<dialog>` element does everything it did, with no injected style:

```tsx
useEffect(() => {
  if (open && !dialog.open) dialog.showModal();   // the rest of the page becomes unreachable
  if (!open && dialog.open) dialog.close();
}, [open]);
```

`showModal()` keeps Tab inside the dialog, closes on Esc and dims the page behind (`backdrop:bg-black/55`). The `useEffect` is the bridge between React's "state" and a browser element you open by calling a method.

**3. The title bar is three lines, and the rest is proof.**

```js
backgroundColor: GROUND,
titleBarStyle: 'hidden',
titleBarOverlay: { color: GROUND, symbolColor: SYMBOLS, height: 44 },
```

The page marks where the window drags (`.drag { -webkit-app-region: drag; }`) and keeps 138 px free at the top right (three 46 px buttons). One catch, found after the first live look: Electron decides "drag or click" from those rows alone, even under a dialog drawn on top. So `body:has(dialog[open]) .drag` turns dragging off while a dialog is open.

**4. The rule test changed shape, not strength.** C3 used to forbid any frameless window. Now it scans every folder and allows exactly one: `titleBarStyle: 'hidden'` with `titleBarOverlay`, in `window-look.js` only. `frame: false` is still forbidden.

**5. Contrast is arithmetic, so it's a test.** Each colour gets a luminance from 0 to 1, and the ratio is `(lighter + 0.05) / (darker + 0.05)`. WCAG AA needs 4.5:1 for normal text. The test checks every text token on every background it is used on.

## What happens when you run it (annotated real output)

Step 0, third run (the first two had mistakes in my probe, not in the window):

```
S2 Dialog: violations 1 ['style-src-elem']        <- Radix's injected <style>: refused
S2 native <dialog>: violations 0 []               <- what Settings now uses
S2 DropdownMenu modal=false: violations 0 []      <- non-modal menus are fine
S3 scale 1.25 | listed 1 time(s), without an id True | overlay style False
S3 focus popups above our window: 3 of 3
S3 close button {'ours': True, 'hit': 20} -> every process ended True   <- 20 = Windows' "close button"
S4 Geist: the probe text is drawn in "Geist Variable"
```

The live check on `Pseudo.exe`:

```
READS of the fake window, never Pseudo's own: 5 of 5
action round 1: ... routed True | billing clean False | ... FAILED       <- first run: NOT CLEAN
ACTION popups above the face and clickable: 2 of 2                       <- after .env was fixed
IDLE 2 VISIBLE, not focused: 600 s, CPU s 2.28 (I1 limit 3) | in RAM peak 234 MB (I2 limit 400)
```

The refused run is the interesting one. Claude Code was logged into a different account from the one in `.env`, so the billing check said NOT CLEAN and **nothing was sent**: no popup, form unchanged. A safety check doing its job looks exactly like a failure until you read why.

## Try this (3 small experiments that break or change something)

1. In `theme.css`, change `--color-faint` to `#5a5a60` and run `npx vitest run a11y-theme.test.mjs`. Several pairs fail AA. Put it back.
2. In `components/ui/Dialog.tsx`, temporarily import Radix's Dialog instead, build, and open the page with the console visible: you'll see the "Refused to apply inline style" line. (Scratch copy only.)
3. Remove `body:has(dialog[open]) .drag ...` from `theme.css`, make the window short, open Settings, and try clicking its X while it sits over the top row: the window moves instead.

## Check yourself

1. Why is Tailwind's own palette switched off?
2. What does the page's security policy refuse that Radix's Dialog needs?
3. What did step 0 have to prove before the title bar could be blended, and why does it matter for Pseudo?
4. Why does a test compare `window-look.js` with `theme.css`?
5. The first action rounds failed. Why is that a pass for safety, and what fixed it?

<details>
<summary>Answers</summary>

1. So only the mockup's colours exist. `bg-red-500` isn't a class, so red can't sneak in where the rules say only Delete and recording may be red.
2. A `<style>` tag added at run time (to stop the page scrolling). `default-src 'self'` allows only our own files.
3. That Pseudo is still listed without an id, refused for reads, focus and actions, not an overlay, under the approval popup, and still drags, resizes, snaps and closes. `pseudo_hands` decides what it may touch by looking at windows, so the face must stay an ordinary one.
4. Electron paints the window before the page draws, and behind the overlay buttons. If those colours drifted from the page's, you'd see a flash or a seam.
5. Claude Code was logged into an account that wasn't the one in `.env`, so the billing check refused and sent nothing. The owner corrected `.env`; the check then passed and both popups were judged.

</details>

## How this connects to Pseudo's final architecture

M39 is the frame every Phase 10 milestone fills. M40 replaces the status line with the working word and makes the banner amber only when a popup really waits. It also moves the privacy information into Settings or the sidebar. M41 fills the sidebar's chats with search, rename and delete. M42 adds the look-at chip, the memory browser and the status panel. M43 redesigns the compact bar on these parts. The rules didn't move: the face still only describes (D11), the popup still sits above it (D13), and Pseudo still never reads itself.
