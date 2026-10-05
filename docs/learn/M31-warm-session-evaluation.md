# M31: A warm Claude Code session (evaluated)

## The concept in one paragraph

Since M30, a request to act on a window starts Claude Code, waits for it and its own `pseudo_hands` to load, gets the answer, and stops both. That is a **cold** launch: about 20 s to the popup. A **warm** session keeps one Claude Code process open and writes each new request to it, so only the first request pays the start-up. M30 tried that and found the catch: a session remembers everything, so every request re-sends all the earlier ones. By the 18th request the **input** (everything sent to the model) was 7 times the 1st. M31 built nothing. It measured the obvious fix, **restart the session every 6 requests**, on 18 new questions against five criteria written down first. **Result: all five pass.** Warm takes 10.4 s to the popup against 20.3 s cold, at about the same quota. The build would be its own milestone.

## Web-dev analogy

- **Cold vs warm** is a serverless function. A cold start boots the runtime and loads your code before it handles the request; a warm instance is already loaded and answers at once.
- **The growing input** is a chat thread where every message re-posts the whole thread. The model is a stateless endpoint (M1): Claude Code "remembers" only by sending the history again each time.
- **Restart every 6** is recycling a worker process after N requests so its memory use can't grow without limit.
- **The prompt cache** is a CDN for the start of your request. The provider keeps the part it has seen before (here for an hour) and charges about a tenth for reading it again. That is why twice the input didn't cost twice as much.
- **The held-out set** is a test file committed before the feature exists and never edited to pass (as in M29).
- **The 1,200-character cut** is a response size limit: anything after it simply isn't there for the model.

## What was built (file by file)

- **`tests/warm_session_cases.py`** (`e784955`): the 18 questions in asked order, the session size, and `CRITERIA`. Committed before anything was measured.
- **`tests/test_warm_session_cases.py`:** checks the set against the plan (3 per action type, one of each type per session), that every asked control is in its fake window, that no question repeats an older one, and that the criteria match PRD.
- **`tests/fixtures/m31_page.html`:** F6, a fake room-booking page. Shortened once (`1882ff8`) before any model saw it; see "Found before measuring".
- **`PRD.md`, `README.md`** (`255de75`, `60b0b4f`): the measuring rules, fixed first, and then the result.
- **Scratchpad only, not committed:** `m31_warm.py` (one warm session), `m31_run.py` (warm, then cold), `m31_structure.py` (the check before measuring), `m31_score.py`, `m31_report.py`, and copies of M29's recorder and window helper with F6 added. Nothing in `pseudo_brain/`, `pseudo_hands/` or `face/` changed.

## Walkthrough of the key code

**1. The order is part of the test** (`tests/warm_session_cases.py`):
```python
SESSION_SIZE = 6  # the candidate: a session is stopped after this many requests, and a new one started
ROTATE_BY = 2  # session k starts ROTATE_BY * (k - 1) places further along ACTION_TYPES

def type_order(session_number: int) -> list[str]:
    shift = ROTATE_BY * (session_number - 1) % len(ACTION_TYPES)
    return list(ACTION_TYPES[shift:] + ACTION_TYPES[:shift])
```
The 6th request of a session has the largest input. If "choose" always sat there, a miss could be blamed on either the action type or the place. Rotating the order by 2 per session puts a different type in each place. The ids say where a request sits: `S2-4` is the 4th request of session 2.

**2. A warm session is the same command plus one flag** (`m31_warm.py`):
```python
command = claude_code.command_line(claude_billing.program(the_brain), the_brain, write_config(log, windows), SYSTEM_PROMPT)
at = command.index("--max-turns")
del command[at:at + 2]
self.proc = subprocess.Popen([*command, "--input-format", "stream-json"], ...)
```
`command_line` is the product's own function from M30, so warm and cold get the same tools, prompt and model. `--input-format stream-json` makes Claude Code read requests from its **stdin** (the pipe a parent process writes into) one JSON line at a time, instead of taking one question and exiting. `--max-turns` is removed because it would count across the whole session; the harness counts tool calls per request itself.

**3. Sending one request:**
```python
line = {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": text}]}}
self.proc.stdin.write(json.dumps(line) + "\n")
self.proc.stdin.flush()
```
Then it reads output lines until one has `"type": "result"`. This is the face-to-brain pipe from M18 again: JSON lines over stdin and stdout, no network port.

**4. What W-T counts** (`m31_warm.py`):
```python
out["input_total"] = out["input_tokens"] + out["cache_creation_input_tokens"] + out["cache_read_input_tokens"]
```
Fresh input, input written to the cache, and input read from the cache. A request here makes 3 model calls (decide to read, decide to act, answer), and each call sends the whole history, so one request's input is about 3 times the session's size at that moment.

**5. The price figure is a running total:**
```python
price = round(total - session.cost_so_far, 7)
```
Claude Code reports `total_cost_usd` for the session so far, so one request's share is the difference from the request before. Nothing is charged on Pro; the figure is only a way to weigh the four kinds of tokens as one number.

## What happens when you run it (annotated real output)

Session 1's first and last request, then the same last request cold:
```
phase warm | id S1-1 | type press | usable True | tools ['read_active_window', 'act_on_control'] | own_read True | secs_to_popup 13.4 | input_total 7132 | cache_creation_input_tokens 1248 | cache_read_input_tokens 5878 | price 0.0079096 | meter_5h 0.56
phase warm | id S1-6 | type choose | usable True | tools ['read_active_window', 'act_on_control'] | own_read True | secs_to_popup 11.4 | input_total 19649 | cache_creation_input_tokens 848 | cache_read_input_tokens 18795 | price 0.009233
phase cold | id S1-6 | type choose | usable True | tools ['read_active_window', 'act_on_control'] | own_read True | secs_to_popup 19.4 | input_total 7166 | cache_creation_input_tokens 1276 | cache_read_input_tokens 5884 | price 0.0082928
```
- **`secs_to_popup 13.4`, then `11.4`:** the first request was sent 6.6 s after its session started, a little before `pseudo_hands` was ready, so it waited. Later requests don't.
- **`input_total` 7,132 to 19,649:** 2.76 times, under the limit of 3.
- **`cache_read` 18,795:** nearly all of that growth is read from the cache, which is why the price rose only from 0.0079 to 0.0092.
- **`own_read True`:** the 6th request still read the window itself before acting, although it had five older reads of similar pages in its history.

The report:
```
W-S  raw median to the popup 10.35 s (min 6.5, max 13.4; limit 15): PASS
W-U  usable popups 18 of 18 (need 17 of 18): PASS
W-R  own fresh read before acting 18 of 18 (need 18 of 18): PASS | attempts to act before that read (reported): 0
W-T  input never over 3 times the session's first: PASS
       session 3: [7123, 9780, 12394, 14895, 17557, 20147] -> times the first [1.0, 1.37, 1.74, 2.09, 2.46, 2.83] | tool calls [2, 2, 2, 2, 2, 2]
W-B  billing clean and the session as D26 says 18 of 18 (need 18 of 18): PASS
cold usable 18 of 18 | raw median to the popup 20.3 s (min 15.6, max 20.9)
price for all requests: warm 0.150087 | cold 0.133602 | warm / cold 1.12
```
- **2.83 is close to 3.** Every request made exactly 2 tool calls. One extra call late in a session would have crossed the limit.
- **`warm / cold 1.12` overstates the gap.** Warm ran first, and three cold launches (S1-1, S2-1, S3-1) sent exactly what a warm session's first request had sent minutes earlier, so their prompts were already cached and cost about 0.003. On the other 15 requests warm cost 1.5% more.
- **The meter:** your 5-hour limit moved from 56% to 57% over the 18 warm requests and from 57% to 58% over the 18 cold ones. It reports whole percents, so it can't tell the two apart.

**Found before measuring.** The structure check reads each fake window through core with no model, and it stopped the run:
```
F6: controls read 400 | 1182 chars | truncated True | ids inside the cut 12
   ComboBox    'Building': MISSING
   ComboBox    'Seats': MISSING
   RadioButton 'Group room': MISSING
STRUCTURE CHECK FAILED
```
Each line of a read is indented by its depth (18 spaces on this page), and the heading was read twice. Three asked controls fell past the cut, so they had no id and no model could have acted on them. The page was shortened and committed again; no question changed. The second check read F6 eight times in one process, because ids are never reused and grow longer during a session (`c160`, later `c1047`), which moves the cut.

## Try this (3 small experiments)

1. In a Python shell inside `tests/`, run `from warm_session_cases import type_order; [type_order(n) for n in (1, 2, 3)]`. Which type is last in each session? Change `ROTATE_BY` to 3 in a copy and look again: why is 3 a worse choice for three sessions?
2. Run `pytest tests/test_warm_session_cases.py -q`. Then change the text of `S2-4` from `"Six"` to `"Seven"` (question and expected text) and run it again. Which test fails, and what would the measurement have recorded without it? Undo the change.
3. Open `tests/fixtures/m31_page.html` in a browser and add `<h1>Booking</h1>` back as the first line of the body. Count the characters that one heading would add to a read: 18 spaces + `Text: Booking`, then 20 spaces + `Text: Booking` again. Undo it.

## Check yourself

1. Why does a warm session's input grow with every request, when the model itself remembers nothing?
2. Twice the input tokens cost about the same. Why?
3. Why couldn't M29's 18 questions be used to test "restart every 6"?
4. W-T passed at 2.83 times. What single thing in a real session would push a request over 3?
5. Why did the warm phase running first make three cold launches cheaper, and why only those three?

<details>
<summary>Answers</summary>

1. Claude Code keeps the session's history and sends all of it with every model call. The memory is in the request, not in the model (M1).
2. Almost all the extra input is the unchanged start of the request, which the provider has cached. Reading from the cache is priced at about a tenth of fresh input.
3. The number 6 was read off those questions' token counts. A number chosen on a set will look right on that set whether or not it holds elsewhere.
4. An extra tool call. Each call re-sends the whole history, so 4 model calls instead of 3 late in a session is about a third more input for that request.
5. The cache matches a request from its first character. A cold launch sends prompt, tools, question; only a warm session's first request starts the same way, so only those three questions were already cached. Later warm requests have older requests in front of the question.
</details>

## How this connects to Pseudo's final architecture

Nothing in ARCHITECTURE.md changes yet: M30's routing arrow still ends in one `claude -p` launch per action request. M31 says what a build may change behind that arrow, and what it must keep. The billing check still runs before every request (0.6 s). Claude Code still gets only the three action-brain tools. Every request still reads the window itself, and the redactor, the refusals and the approval popup stay in `pseudo_hands` core (D11, D13), which is why a session could be kept open without touching them. What a build has to weigh is new: an open session holds 310 to 440 MB (D20 wants the laptop free, hence the 10-minute idle rule), a new session needs 7 to 8 s before it is ready (hence the cold launch as the fallback), and the 3-times limit leaves little room for a request that needs an extra tool call.
