# M42: What Pseudo sees

## The concept in one paragraph

M42 shows Pseudo's own extras in its window. A chip in the question box says which app a question would read ("Looking at Windows PowerShell"). A memory browser opens your saved notes read-only. A Status panel shows tokens, Groq's budget, the warm session's memory, and how many items were masked. All three needed new tools in `pseudo_hands`, and that raised a question first: **who may call a tool?** Until now the model was offered every tool `pseudo_hands` published, except two that the brain's code named (M24). So a new tool for the window would have reached the model by default. **D29** turns that around: `providers.toml` lists the only tools a model may be offered. Everything else is either brain-only (Pseudo calls it for itself) or offered to nobody.

## Web-dev analogy

**`model_tools`** is an OAuth scope list. A token can call only the scopes it was granted; a new endpoint isn't reachable until someone adds its scope on purpose, and that shows up in code review.

**Brain-only tools** are internal endpoints: your own frontend calls them, but they are never in the public API docs.

**The chip** is a `HEAD` request: it asks what a `GET` would return, without fetching the body.

**`masks.py`** is analytics without the personal data: you count sign-ups, you don't store the emails.

**`sees.ts`** is a Redux slice: one part of the state with its own small reducer, plugged into the main one.

## What was built (file by file)

| File | What it does |
|---|---|
| `pseudo_brain/providers.toml` | `model_tools`: the only tools a model may be offered (D29). |
| `pseudo_brain/model_tools.py` | Loads that list and refuses a bad one; names the five brain-only tools (`BRAIN_TOOLS`). |
| `pseudo_brain/hands.py` | Offers a model only the list; `brain_call()` is the one way to call a brain-only tool. |
| `pseudo_hands/core/looking_at.py` | The app a question would read now, or "private"; reads nothing from the window. |
| `pseudo_hands/core/app_names.py` | An app's own name, as Task Manager shows it. |
| `pseudo_hands/core/memory_browse.py` | Lists and opens notes read-only, redacted again, through M24's checks. |
| `pseudo_brain/masks.py` | Counts the redactor's labels in a tool result. Counts only. |
| `pseudo_brain/bridge_sees.py` | The chip and the browser over the bridge, only while nothing else runs. |
| `face/src/sees.ts` | The page's state for the chip, the browser and the Status numbers. |
| `face/src/components/` | `LookingAtChip`, `PanelSwitch`, `MemoryView`, `StatusPanel`. |

## Walkthrough of the key code

**1. Two lists that never overlap.** `model_tools.py`:

```python
BRAIN_TOOLS = ("search_memories", "save_memory", "looking_at", "list_memories", "open_memory")
...
brain_only = [tool for tool in tools if tool in BRAIN_TOOLS]
if brain_only:
    raise ProviderRefused(f"model_tools: {', '.join(brain_only)} is brain-only; no model may be offered it (D29)")
```

Pseudo refuses to start with a bad list. `Hands` checks a second time, so even a list that slipped through couldn't offer a brain-only tool:

```python
for_model = [tool for tool in tools if tool.name in offered and tool.name not in BRAIN_TOOLS]
```

This is **defense in depth**: two independent checks, so one mistake isn't enough.

**2. Looking without looking.** The chip must name the window `read_active_window` would read. Calling `read_active_window` itself would be wrong twice over: it reads the window's text, and it retires the control ids the last read gave out, which `act_on_control` needs. So `looking_at()` calls only the picking step:

```python
blocked = load_blocked_apps()
raw = pick_window()                       # the same choice read_active_window makes
if is_blocked(raw.app, blocked):          # an unknown owner counts as blocked too
    return {"app": "", "private": True, "note": ""}
return {"app": display_name(raw.process_id, raw.app), "private": False, "note": ""}
```

`display_name` reads the program file's **FileDescription**, a friendly name stored inside every Windows program. It never reads the window's title or text.

**3. A second door, no wider than the first.** The browser reuses M24's checks: the vault folder (now with no link from the Pseudo folder down), plain notes only, no hard links, at most 20,000 bytes. A note's name must be one Pseudo makes, never a path. And everything is redacted **again**, because you may have typed a name into a note in Obsidian:

```python
return {"name": name, "date": date, "title": safe(title), "question": safe(question), "answer": safe(answer), ...}
```

**4. Counting, not copying.** `masks.py` counts only the redactor's own labels, so a page's "[TODO]" isn't counted:

```python
return sum(1 for match in LABEL.finditer(text) if match.group(1) in REDACTOR_LABELS)
```

The brain can't import core (D11), so the 27 labels are written out. A test builds the redactor's analyzer and checks the two lists are equal. That test found `EMAIL` and `ID`, which nobody had listed.

**5. Idle reads.** While a question runs, `pseudo_hands` may be showing an approval popup, and a new call would wait behind it. So `bridge_sees.py` answers only while no job runs:

```python
if bridge.busy:
    if kind != "look":
        bridge.send("refused", reason=busy)
    return
```

`look` is skipped silently instead, because each question sends a fresh chip anyway. None of these calls sends a `tool_call` event. That event is what lets a popup come to the front and makes the compact bar give up always-on-top, and these calls show no popup.

**6. A pure reducer that needs the time.** Groq's budget is "per minute", so the panel shows the last figure for 60 seconds, then the full budget. A reducer must not call `Date.now()` (the same input must give the same output), so App passes the time in with the message, and the tests pass fixed times:

```ts
window.pseudo.onMessage((message) => dispatch({ type: 'from_brain', message, at: Date.now() }));
```

## What happens when you run it (annotated real output)

The live check ran the packaged `Pseudo.exe` with fake windows and a temporary folder of fake memories:

```
 chip 1: notes in front True | chip says 'Windows PowerShell' | wanted 'Windows PowerShell' | right True
 chip 3: blocked in front True | chip says 'a private app' | wanted 'a private app' | right True
CHIP: named 10 of 10 | private 3 of 3
```

The fake notes window is drawn by PowerShell, so its app is "Windows PowerShell". The "blocked" app was a copy of Python renamed `KeePass.exe`, which is on the blocked list.

```
 masked 3: ... my read's labels 3 | each read of the window [3] | other tools [('Listed your open windows', 1)]
          | Status says 4 = sum of all results 4 | ... | right True | steps name the matching memory True
MASKED: 3 of 3
MEMORY note: opened True | ... | fake name shown False | 'name' chip shown True | read-only line True
```

The check script read the same window itself and counted 3 labels; Pseudo's step said 3. The model also listed the open windows, whose titles had one label, so the panel says 4.

Two honest notes:
- **The first three masked runs failed because of the check script.** It read the steps before they were drawn, compared a window list with a window read, and missed the step numbers. Each was fixed, and the masked rounds were run again on their own.
- **The live check found a real bug.** A turn that hit the 6-call limit used about 6,800 of Groq's tokens, but the panel said "Tokens this chat 0", because only answered turns counted. Now the `failed` event carries the turn's tokens too.

The M15 battery scored 12/12.

## Try this (3 small experiments that break or change something)

1. In `pseudo_brain/providers.toml`, add `"looking_at"` to `model_tools`, then run `.venv\Scripts\python.exe -m pytest tests/test_tool_allowlist.py`. Four tests fail: the list is refused as naming a brain-only tool. Put it back.
2. In `pseudo_hands/core/memory_browse.py`'s `open_memory`, change `"question": safe(question)` to `"question": question`, then run `pytest tests/test_memory_browse.py`. The test with a name typed in Obsidian fails: the name would reach your window. Put it back.
3. In `face/src/sees.ts`, change `kind === 'answer' || kind === 'failed'` to `kind === 'answer'`, then run `npx vitest run src/state-m42.test.ts` in `face\`. The test fails with 0 instead of 6,300: the live check's bug. Put it back.

## Check yourself

1. Before D29, what would have happened to a new tool added to `pseudo_hands`? What happens now?
2. Why does the chip call `pick_window()` and not `read_active_window()`? Give both reasons.
3. Notes in the vault were redacted when Pseudo saved them. Why does the browser redact them again?
4. Why are the browser's messages refused while a question runs, but `look` only skipped?
5. Why does the page get the time with each message, instead of the reducer asking for it?

<details>
<summary>Answers</summary>

1. Before, it was offered to the model unless the brain's code named it. Now it reaches no model until it is added to `model_tools`, and a brain-only tool can never be added.
2. `read_active_window` reads the window's text, which the chip doesn't need, and it retires the control ids that `act_on_control` uses.
3. You can edit notes in Obsidian, and a name you type there was never redacted. Redacting on the way out protects you whatever is in the file.
4. A running question may have a popup open in `pseudo_hands`, and a call would wait behind it. A refused `look` would only show a confusing "busy" notice, and the next question sends a fresh chip anyway.
5. A reducer must be pure: the same state and message always give the same result. With the time in the message, the tests can use fixed times.

</details>

## How this connects to Pseudo's final architecture

D29 joins D16: every place Pseudo can send your words (providers) and everything a model can make Pseudo do (tools) is now one reviewed list in git. The look-at chip, the browser and the Status panel are brain-only tools, so any future window, or a terminal command, can use them without a model ever seeing them. M43 redraws the compact bar and can put the chip there. M44 replaces the "P" icon and the exe's name.
