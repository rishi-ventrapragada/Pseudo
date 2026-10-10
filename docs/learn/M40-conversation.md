# M40: The conversation

## The concept in one paragraph

M40 makes the conversation say what Pseudo is doing, in plain words, and only what is true. While it works, a playful word and a timer ("Squinting at your window… 1s"). While an approval popup may be open, an amber line instead: "Waiting for your approval in the popup". The hard part was that the window could not tell those two cases apart: a read and a click both arrive as a `tool_call` event (a message the brain sends the window as things happen). So the **brain now tells the window a fact**: each `tool_call` carries `asks`, taken from the marks `pseudo_hands` already puts on its own tools. Around that: the steps are now worded for a person (`steps.ts`) with a test that no event is missing, the empty chat offers four suggestions that the brain has checked are only reads, and the privacy information moved off the main view into Settings (D28).

## Web-dev analogy

**`asks`** is an API that returns `requiresConfirmation: true` with each item, instead of the frontend guessing from the endpoint's name. The backend knows; the frontend shows. That is D11 (the face decides nothing) in one field.

**The marks** are MCP *annotations*: small hints a tool server attaches to each tool it publishes, like OpenAPI's `readOnly`. `read_only_hint=True` means "this tool only reads".

**`state.ts`** is a reducer, like `useReducer` or Redux: every message from the brain goes in, a new state comes out, and React draws from that state. `waiting` is one field in it.

**`test_face_wording.py`** is an i18n check that every key has a translation, except the "keys" are the event kinds the brain sends, and the "translations" are the `case` lines in `steps.ts`.

**The suggestions living in the brain** is server-driven UI: the server sends the buttons, because it knows which questions are safe to offer.

## What was built (file by file)

| File | What it does |
|---|---|
| `pseudo_brain/asks.py` | `WithAsks` wraps the event sink and adds `asks` to every `tool_call`; unknown tools count as asking. |
| `pseudo_brain/hands.py` | Keeps which tools `pseudo_hands` marked read-only; `asks(name)`. |
| `pseudo_brain/suggestions.py` | The four suggestions, sent in `ready`. |
| `face/src/steps.ts` | Each brain event as one step: a short label and a quieter detail. Replaces `events.ts`. |
| `face/src/state.ts` | `waiting: {name, asks}`; steps as objects; `askedAt` for the timer; the refusal fix. |
| `face/src/components/Activity.tsx` | The working word, the amber approval line, and the compact bar's top row. |
| `face/src/components/TurnView.tsx` | The answer with no badge, labelled "Pseudo's answer"; picks which line to show. |
| `face/src/Markdown.tsx` | Masked items as chips that read "name", "phone"; the redactor's label in the tooltip. |
| Settings | Each provider's privacy note and fallback; where action requests go. |
| Tests | Popup tools are never marked read-only; suggestions pass the routing rules as reads; every event has a wording; `asks` on every `tool_call` and nothing else. |

Gone: `ApprovalBanner.tsx`, `events.ts`, and the privacy note under the question box.

## Walkthrough of the key code

**1. The marks are kept, not invented.** In `hands.py`, when the tools are discovered:

```python
self.read_only = {tool.name for tool in tools if tool.annotations and tool.annotations.read_only_hint is True}

def asks(self, name: str) -> bool:
    return name not in self.read_only
```

Notice the direction: the set holds the tools that *don't* ask. A tool that isn't in it, with no mark or a name nobody knows, asks. The safe mistake is an amber line with no popup. The unsafe one is a popup with no line, so the code can only make the safe one.

**2. One wrapper covers every brain.** `asks.py`:

```python
def __call__(self, kind: str, data: dict) -> None:
    if kind == "tool_call":
        name = str(data.get("name", ""))
        data = {**data, "asks": self.hands.asks(name) if self.hands is not None else True}
    self.sink(kind, data)
```

`chat.py` wraps its `on_event` once (`self.on_event = WithAsks(on_event)`), so the Groq loop, Claude Code (launched or warm) and the memory save all pass through it. `{**data, ...}` makes a new dict instead of changing the caller's (a test checks that).

**3. The mark is a hint, not a guard.** If someone marked `act_on_control` as read-only, the popup would still appear, because it runs inside `pseudo_hands` core (D13). Only the amber line would be missing. `tests/test_approval_marks.py` stops that: every tool whose module calls `approval.ask(` must be published with `read_only_hint` False.

**4. The window keeps the fact.** In `state.ts`:

```ts
const waiting = kind === 'tool_call' ? { name: String(data.name), asks: data.asks !== false } // no mark: it asks
  : kind === 'tool_result' ? null : state.waiting;
```

A tool starts, so `waiting` is set. Its result arrives, so `waiting` is cleared. Note `asks !== false`: a missing field also means "asks". And `TurnView` picks exactly one line:

```ts
const approval = turn.running && Boolean(waiting?.asks);
const working = turn.running && !approval && turn.answer === undefined && !turn.failed;
```

**5. A refusal no longer wipes the wait.** Before M40, any `refused` message cleared `waiting`. So a refused side request (a provider switch, say) while a popup waited made the line vanish with the popup still open. Now:

```ts
if (questionRunning(state)) return { ...state, notice: message.reason };
```

**6. Python checks the TypeScript.** `test_face_wording.py` finds every `on_event("kind"` in `pseudo_brain/*.py` and looks for `case 'kind'` in `steps.ts`, as plain text. No browser, no build. Add an event to the brain without a wording and the test names it.

## What happens when you run it (annotated real output)

The live check, on `Pseudo.exe` with fake windows. Reads, checked every 0.25 s from sending to the answer:

```
 read 1: ... tools ['read_active_window'] | approval line seen in 0 of 12 samples | working word seen in 12 | answer without a provider label True
B: reads that never showed the approval line (and D: no label): 3 of 3
C: suggestion clicked True | answered True | asked once True | by None | routed False | no provider label True
```

Popups (focus, memory, and two tick requests through Claude Code; Cancel only):

```
 focus round 1, focus popup: {'approval_line': True, 'working_word': False, 'popup_topmost': True, 'above_face': True, 'clickable': True, ...}
A: approval line shown, no working word, popup above and clickable: 6 of 6 | E: the steps say who answered: [None, None, None, None]
```

That `None` (also in C's `by None`) was **my check script's mistake, not Pseudo's**. The page draws "Answered" and its detail as two pieces of text, so the script read them back with double spaces, and its pattern wanted one:

```
E: the steps say who answered: groq · openai/gpt-oss-120b | around it: 'Answered  ·  groq · openai/gpt-oss-120b, 2 call(s)'
action: ... E: the steps say who answered: Claude Code · claude-sonnet-5-5 (your subscription)
```

The very first run crashed for a similar reason: the steps button has `aria-expanded`, so Windows' UI Automation offers it as *expand/collapse*, not *invoke*. That is the same accessibility tree `pseudo_hands` reads in other apps. How a page is marked up decides how automation sees it, Pseudo's own included.

The steps of one answer, as the window shows them (from the screenshot):

```
1 Searched your memory · there is no memory folder yet
2 Asked groq · openai/gpt-oss-120b · call 1 of 6, about 820 tokens
4 Read the window you were on
8 Answered · groq · openai/gpt-oss-120b, 2 call(s), 1,644 tokens in, 103 out
9 Offered this task to memory · the popup asks you first; no answer means no
10 Not saved to memory · you didn't approve it, so nothing was saved
```

The M15 battery scored 12/12.

## Try this (3 small experiments that break or change something)

1. In `face/src/steps.ts`, delete the `case 'warm':` block and run `.venv\Scripts\python.exe -m pytest tests/test_face_wording.py`. It fails and names `warm`. Put it back.
2. In `pseudo_brain/suggestions.py`, add `"Tick the box on this form"` and run `pytest tests/test_brain_suggestions.py`. The routing rules call it an action request, so it would go to Claude Code. Remove it.
3. In `pseudo_brain/asks.py`, change the last `True` to `False` and run `pytest tests/test_brain_asks.py`. "Before a question every tool counts as asking" fails. Put it back.

## Check yourself

1. Why does the brain send `asks`, instead of the window deciding from the tool's name?
2. Why does a tool with no mark count as asking?
3. If `act_on_control` were wrongly marked read-only, what would still protect you, and which test catches the mark?
4. Before M40, how could a refused side request hide the approval line while a popup was open?
5. The live check first said "who answered: None" for every round. How do you know it wasn't Pseudo?

<details>
<summary>Answers</summary>

1. The face decides nothing (D11). `pseudo_hands` already marks its own tools, so the brain passes that fact on. A new tool needs no change in the window.
2. Getting it wrong that way shows an amber line with no popup, which is harmless. The other way, a popup waits with nothing on screen saying so.
3. The popup itself, which runs in `pseudo_hands` core whatever the mark says (D13). `tests/test_approval_marks.py` fails for any tool whose module calls `approval.ask(` but is marked read-only.
4. Every `refused` message cleared `waiting`. A refused provider switch, for example, arrived while the question still ran, and the line went away with the popup still up.
5. The screenshot showed the right text, and after the script's pattern allowed the double spaces, it read "groq · openai/gpt-oss-120b" and "Claude Code · claude-sonnet-5-5 (your subscription)". A checker that finds nothing should be checked first.

</details>

## How this connects to Pseudo's final architecture

The window now speaks plain words, but every safety rule stayed where it was: the popup lives in core (D13), the window only describes (D11), and who answered is still recorded in every saved session, just one click away (D28). M41 puts each provider's privacy note in the sidebar's provider picker too. M42 adds the look-at chip and shows which memories joined a question, as new steps. M43 rebuilds the compact bar so it grows upward for the same three states, using `Activity.tsx`'s parts. Because `asks` comes from MCP marks, any future tool or brain gets the right line without touching the face.
