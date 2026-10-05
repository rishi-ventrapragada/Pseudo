# M29: Fix action misses (evaluated)

## The concept in one paragraph

M28 built clicking and typing, and the build held. The weak link was the brain: `gpt-oss-120b` turned only 30 of 52 action requests into a **usable popup** (exactly one approval popup, naming the asked control, the asked action and the exact text). M29 built nothing. It measured four possible fixes against criteria written down first: a **rule** that hides `focus_window` unless you ask to switch windows, two other Groq models, and Claude Sonnet 5.5 through Claude Code. Each brain ran with and without the rule, so 8 **setups** (A0/A1, B0/B1, Q0/Q1, C0/C1). The questions that decide were a **held-out set**: 24 new questions committed before any measurement, so nothing could be tuned on them. **Result: only Claude passed every criterion** (18 of 18 held-out, both setups). The plan's tie-breaks pick C1, Claude with the rule, recorded as D26. The build is M30.

## Web-dev analogy

- **Held-out set:** a test file you write and commit before the feature exists, and never edit to make it pass. M28's own 6 questions were "spent": two tool descriptions had been tuned on them, like tests rewritten until green.
- **The rule** is conditional rendering. You don't tell the user "please don't press this button"; you don't render it. Two sentences in the tool descriptions asked the model not to call `focus_window` first, and it still did about 4 times in 10. Leaving the tool out of the request made that 0.
- **The recorder** is a mocked payment gateway. Everything real runs up to the point of charging; the mock notes "a charge would have happened" and declines.
- **Setups** are an A/B test matrix: 4 brains × rule on or off.
- **A Groq 503** is the API returning "Service Unavailable". It says nothing about your code, so you retry it instead of counting it as a failed test.
- **Claude Code's start-up** is a serverless cold start: each `claude -p` launch pays about 6 s before the first tool call.

## What was built (file by file)

- **`tests/brain_action_cases.py`** (`24e2ad8`): the questions, the expected popups, the rule (`offers_focus`) and `CRITERIA`, committed before any window opened.
- **`tests/test_brain_action_cases.py`:** checks the set sizes, that each quoted text matches its expected text, that every expected control name is in its fixture, and that no held-out question repeats an older one.
- **`tests/fixtures/m29_page.html`:** F5, a fake order page. Its text fields start filled, so "add" and "replace" give different results and only one is right.
- **`pseudo_hands/core/finding_filters.py`** + **`tests/test_redactor_m29.py`** (`93e177a`): the redactor no longer masks Pseudo's own control ids (see "Found while measuring").
- **`PRD.md`, `DECISIONS.md`, `CLAUDE.md`** (`d298a6c`): the result, D26, the D11 exception and the new Backlog line.
- **Scratchpad only, not committed:** `m29_hands.py` (the recording `pseudo_hands`), `m29_run.py` (asks every question to every setup), `m29_claude.py` (launches Claude Code, billing check first), `m29_desk.py` (opens and closes the fake windows), `m29_score.py` and `m29_report.py`.

## Walkthrough of the key code

**1. The rule** (`tests/brain_action_cases.py`):
```python
SWITCH_PHRASES = ("switch to", "switch back", "switch over", "bring up", "to the front", "in front",
                  "on top", "focus", "jump to", "take me to", "go back to", "alt tab", "alt-tab")
SEE_A_WINDOW = re.compile(r"\b(show|see|open|go to)\b.*\bwindow\b")

def offers_focus(message: str) -> bool:
    text = message.lower()
    return any(phrase in text for phrase in SWITCH_PHRASES) or bool(SEE_A_WINDOW.search(text))
```
No model is involved: it's a phrase list and one **regular expression** (a text pattern). `\b` marks a word edge, so "open" matches but "reopened" doesn't. Core never sees your message, only tool calls, so this rule has to live in the brain.

**2. Applying the rule** (`m29_run.py`):
```python
self.names = [n for n in hands.names if offer_focus or n != "focus_window"]
self.schemas = [s for s in hands.schemas if s["function"]["name"] in self.names]
```
The model only knows the tools whose **schemas** (the JSON descriptions from M2) are in the request. Drop one schema and that tool doesn't exist for this question.

**3. The recorder** (`m29_hands.py`):
```python
def recorder(_question: str) -> bool:
    state["popup"] = True      # a popup WOULD have appeared here
    return False               # answers Cancel

approval.ask = recorder
```
Core's own refusals, ids and re-checks all run. Only the last step is swapped, so no popup shows and no fake window ever changes. This works because the popup is one function in core (D13): one line replaces it for every brain.

**4. A usable popup** (`m29_score.py`):
```python
row["named_right"] = len(acts) == 1 and right(acts[0], case)
```
`right` compares the control's type and name as Windows reports them, the action, and the trimmed text. Two popups for one request aren't usable, even if one is right.

**5. Claude Code with only Pseudo's tools** (`m29_claude.py`):
```python
cmd = [CLAUDE, "-p", question, "--strict-mcp-config", "--mcp-config", str(config), "--tools", "",
       "--allowedTools", *allowed, "--system-prompt", SYSTEM_PROMPT, "--model", MODEL,
       "--max-turns", str(MAX_ITERATIONS), "--output-format", "stream-json", "--verbose",
       "--no-session-persistence"]
```
- `--strict-mcp-config` + `--mcp-config`: only our server, none from your own settings.
- `--tools ""`: no built-in tools (no file reads, no shell).
- `--system-prompt`: Pseudo's own prompt, so every brain gets the same instructions.
- `--max-turns 6`: the same cap as `pseudo_brain`'s `MAX_ITERATIONS`.

Before every launch, `billing()` checks that nothing could outrank the subscription login (an API key variable, a helper, another provider) and that the login is your account. If not, it stops and sends nothing.

## What happens when you run it (annotated real output)

One question, three brains (Day B, the rule on):
```
setup A1 | id H12 | type toggle | offered False | usable False | act_popups 0 | tools ['list_open_windows'] | tokens 2005
setup B1 | id H12 | type toggle | offered False | usable True | act_popups 1 | reads ['F5'] | tools ['list_open_windows', 'read_active_window', 'act_on_control'] | secs_to_popup 11.1 | tokens 4660
setup Q1 | id H12 | type toggle | offered False | usable True | act_popups 1 | reads ['F5'] | tools ['read_active_window', 'act_on_control'] | secs_to_popup 8.8 | tokens 3866
```
- `offered False`: the rule withheld `focus_window` ("In the order page window, tick 'Text me updates'" has "window" but none of show, see, open or go to before it).
- A1 listed the windows and stopped: `gpt-oss-120b`'s remaining miss.

The final report (shortened):
```
A0: held-out usable 10/18 | U1 MISS U2 MISS U3 MISS W1 ok N1 MISS F1 ok S1 ok T1/B1 ok
A1: held-out usable 13/18 | U1 MISS U2 MISS U3 ok W1 ok N1 MISS F1 ok S1 ok T1/B1 ok
B1: held-out usable 16/18 | U1 ok U2 MISS U3 ok W1 MISS N1 MISS F1 ok S1 ok T1/B1 MISS
Q1: held-out usable 16/18 | U1 ok U2 MISS U3 ok W1 ok N1 MISS F1 ok S1 ok T1/B1 ok
C1: held-out usable 18/18 | U1 ok U2 ok U3 ok W1 ok N1 ok F1 ok S1 ok T1/B1 ok
   switch right 3/4 | median s to popup 12.6 (raw 19.1) | launches billing-clean 36/36 | session ok 36/36
recommendation (the plan's order): C1
```
- **U3 went from MISS to ok for A1:** the rule removed every pointless focus popup (A0 had 20 on 30 action questions).
- **16 of 18 isn't a pass.** B1 and Q1 reach U1 but fail U2: "add text" was 1 of 3, because they asked to *replace* the field with the old text plus the new:
  ```
  wrong popup: Edit 'Delivery instructions' set_text 'Use the side door (fake). Call before coming'
  ```
- **N1** missed on all six Groq setups: "Which shipping speeds can I pick from?" made them open the dropdown, an action nobody asked for.
- **`raw 19.1`:** Claude passes the 15 s limit only with `pseudo_hands`' start-up taken out. M30 measures whether one warm session removes it.

The run stopping itself:
```
setup B1 | id H12 | ... | reads ['other'] | other_apps [('Discord.exe', 'not ours')]
STOP: a read found a window that isn't ours (blanked, nothing sent); stopping
```
A real app came in front mid-question. The recorder returned an empty read to the model, logged only the app's name, and the run ended. That question was set aside and asked again.

**Found while measuring:** the redactor masked some of Pseudo's own ids (`c169` became `[PERSON]`), which hid those controls from the model. It's fixed (D19). M28's Live B ran with that bug, so some of its misses may not have been the model's.

## Try this (3 small experiments)

1. In a Python shell, run `offers_focus("Can I see the test form?")` from `tests/brain_action_cases.py`. It returns `False`: that's H22, the miss. Add `"can i see"` to a copy of `SWITCH_PHRASES` and try it again. Then think about why the real list wasn't changed after measuring.
2. Run `pytest tests/test_brain_action_cases.py -q`. Then change one held-out question's expected name to a control that isn't in `m29_page.html` and run it again. Undo the change.
3. Open `tests/fixtures/m29_page.html` in a browser. Do H8 by hand ("Append 'Call before coming' to the delivery instructions"), once by adding and once by replacing everything. The field ends the same; decide which popup you'd rather approve.

## Check yourself

1. Why did removing `focus_window` from the request work when telling the model not to call it didn't?
2. Why were M28's 6 questions not allowed to decide M29?
3. B1 scored 16 of 18, the same as the pass mark. Why isn't it recommended?
4. Why does the rule live in the brain, while the approval popup lives in core?
5. Three of A1's turns ended in a Groq 503 and were asked again. Why were all three re-asked, including the one that had already produced a usable popup?

<details>
<summary>Answers</summary>

1. A model can only call tools whose schemas it was sent. An instruction is a suggestion it may ignore; a missing tool can't be called.
2. Two tool descriptions were written after seeing the model fail on them, so a good score there could just mean the wording fits those 6 questions.
3. A setup must pass every criterion. B1 misses U2 (add text 1 of 3), W1 (2 wrong popups), N1 (an action popup on a read-only question) and T1 (one question over 8,000 tokens).
4. Core only sees tool calls, never your message, so only the brain can decide from your words. Safety checks must hold for any brain (D11, D13), so they sit next to the tools.
5. Keeping the good one and re-asking the bad ones would be picking results. The rule "a turn the provider failed isn't a measurement" has to apply to every such turn.
</details>

## How this connects to Pseudo's final architecture

M29 changes one arrow in ARCHITECTURE.md's diagram. Until now every question went from `pseudo_brain` to Groq. From M30, a request to *act* may go to Claude Code instead, with only Pseudo's tools and the billing check first (D26); everything else stays on Groq. Nothing below that arrow moves: `pseudo_hands` is still a plain MCP server, and the redactor, the refusals and the approval popup still sit in core, which is why a different brain could be measured without touching them. D11 gains its first exception: `pseudo_brain` will depend on one harness's command line.
