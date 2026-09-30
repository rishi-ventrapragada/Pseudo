# M15: Providers (evaluation)

## The concept in one paragraph

A **provider** is whoever runs the model: Groq's servers, your own laptop, or Anthropic. Until now Pseudo used one: Groq's `gpt-oss-120b`. M15 measured three alternatives before building anything: a **second Groq model** to fall back to when the first is rate limited, a **local model** through **Ollama** (a program that runs open models on your own GPU) as a "private mode" where nothing leaves the laptop, and **Claude Code** as a different brain for `pseudo_hands` over MCP. Each got the same six questions on fake windows, judged by pass rules written before measuring. The key result: because of D10 (OpenAI-compatible API) and D11 (tools behind MCP), swapping the provider or even the whole brain needed **zero changes** to `pseudo_brain` or `pseudo_hands`. What changed was only the answers' quality, speed and privacy.

## Web-dev analogy

- **Per-model rate limits** are like per-route rate limits on an API: hitting the limit on `/v1/a` doesn't block `/v1/b`. That's what makes a same-provider fallback useful.
- **Ollama** is like `supabase start`: the same API shape on `localhost`, nothing leaves your machine, but your laptop does all the work, so it's slower.
- **Cold start** is a serverless cold start: the first request loads the model from disk into the GPU; later ones are warm.
- **VRAM spill:** a model bigger than the GPU's memory (VRAM, 4 GB here) runs partly on the CPU, like an app that outgrows RAM and starts swapping.
- **Claude Code over MCP** is a different frontend pointed at the same backend: `pseudo_hands` doesn't know or care which client calls it.

## What was built (file by file)

- **In the repo:** no code. Commit `ab9fba0` renumbered the docs (M15 providers, M16 face) and added the "read the window I was on" requirement to the face. After M15, the providers build became M16 and the face moved to M17, taking that requirement with it. D16 records the results. Plus this lesson.
- **Outside the repo:**
  - Ollama 0.34.4 from its official zip in `%LOCALAPPDATA%\Programs\Ollama`: no tray app, no start-at-login entry, no auto-update. It runs only when started with `OLLAMA_HOST=127.0.0.1:11434`.
  - `~/.ollama/server.json` with `{"disable_ollama_cloud": true}`. Ollama also offers **cloud models** that run on its servers, and this setting turns them off.
  - Five models, 15.2 GB, under `~/.ollama/models`. After the evaluation the four that failed were removed; only `granite4.1:3b` (2 GB) is left.
  - A backup of `~/.claude.json`, deleted afterwards: Claude Code never recorded the test folder there.
- **In the scratchpad, not committed** (as in M11 and M13):
  - `m15_common.py`: the six questions, the pass rules, and the privacy helpers.
  - `m15_battery.py`: asks the questions through `pseudo_brain`'s real `run_turn` and the real `pseudo_hands`.
  - `m15_windows.ps1`: the two fake windows.
  - `m15_speed.py`: Ollama's own timings.
  - `m15_groq_limits.py`: the per-model limit test.
  - `m15_claude.py`: Claude Code launches, with a billing check before each one.

## Walkthrough of the key code

**1. Swapping the provider is two strings** (`m15_battery.py`):
```python
LOCAL_URL = "http://127.0.0.1:11434/v1"
model = Model(ModelSettings(LOCAL_URL, "ollama", name))
```
This is the same `Model` class and the same `run_turn` loop that talks to Groq. Ollama speaks the OpenAI-compatible API (D10), so only the base URL and the model name change. `"ollama"` is a dummy key, because Ollama doesn't check one. The script also refuses any model name containing "cloud".

**2. `focus_window` is recorded, never run** (`RecordingHands.call`):
```python
if name == "focus_window":
    self.focus_ids.append(window_id)
    return fake_denial(window_id, self.list_texts), False
```
T4 asks to bring a window to the front. No popup appears and focus never moves, but the model gets the exact "not approved" reply that `pseudo_hands` gives on a real denial. The test checks two things: that the model asked for the right window, and that it reported the refusal honestly.

**3. The guard** (`m15_common.py`):
```python
picked = pick_window()
return picked is not None and picked.handle == notes_handle
```
Before each question, the script asks M9's own `pick_window` which window it would read. If that isn't our always-on-top fake notes window, the question is skipped and nothing is sent.

**4. Claude Code with only Pseudo's tools** (`m15_claude.py`):
```python
cmd = [CLAUDE, "-p", question, "--strict-mcp-config", "--mcp-config", str(MCP_FILE), "--tools", "", ...]
```
- `-p` is one question, non-interactive.
- `--strict-mcp-config` plus `--mcp-config` load only `pseudo_hands` and ignore every other MCP server.
- `--tools ""` removes Bash, Read and the other built-in tools. Without it, Claude could read raw window titles through PowerShell and skip the redactor: the same hole as Hermes Desktop's `read_window_below` (M13).
- It runs from an empty folder, so no CLAUDE.md loads. No Claude Code config file was edited.

**5. The billing check** (`billing()`, before every launch): API keys, auth tokens and Bedrock/Vertex/base-URL variables all take priority over the subscription login. So before each launch, the script checks that none is set anywhere (process, user and machine environment, and settings files) and that `claude auth status` reports the claude.ai login.

## What happens when you run it (real output, annotated)

**Groq limits are per model** (fake filler text; numbers only):
```
A big (~5K tokens)          openai/gpt-oss-120b  status=200 used=5726 tpm_left=2249/8000
B small (right after A)     openai/gpt-oss-20b   status=200 used=107  tpm_left=7859/8000   <- untouched
A big #2                    openai/gpt-oss-120b  status=429 retry_after=26
B small (A is rate limited) openai/gpt-oss-20b   status=200 used=114                       <- answers at once
```
Each model has its own 8K tokens/min and 1,000 requests/day.

**A bug in the test itself.** In the first run, T1 failed for `gpt-oss-120b` although its answer was right. The redactor had changed the fake window's text:
```
'Pseudo M15 target'                 -> 'Pseudo [PERSON] target'
'Notes: order 4471 ships on Monday' -> 'Notes: order [DATE_TIME] ships on [DATE_TIME]'
```
T1's rule looked for "4471", which never reaches any model, and T4's judge looked for "m15 target". Two parts of the test changed, and the intent stayed the same:
- T1 now checks the status word BLUE, which survives redaction.
- T3 and T4 find our windows by their redacted titles.

Every model was then judged by the fixed rules. Failures print only yes/no reasons, never the answer. The redactor masking "M15" and "4471" is a finding in itself; see the Backlog note below.

**The six questions** (T1 read the window · T2 read it again after BLUE→GREEN · T3 list windows · T4 focus the target, then get "not approved" · T5 who is the meeting with (masked) · T6 17×3 without tools):

| Model | Where | Score | Read question (whole turn) | Failures |
|---|---|---|---|---|
| `gpt-oss-120b` (today's) | Groq | **12/12** | ~2.7 s | none |
| `gpt-oss-20b` | Groq | **12/12** | ~1.2 s | none |
| `qwen3.8-27b` (Preview) | Groq | 11/12 | ~0.8 s | T4 once: answered without calling a tool |
| `granite4.1:3b` | laptop | **18/18** | ~5 s (cold 15 s) | none |
| `lfm2.5:8b` | laptop | 13/18 | ~11.5 s (cold 30 s) | T2 0/3: stale answer from history; T4 1/3; leaks `<think>` text |
| `llama3.2:3b` | laptop | 10/18 | ~4.4 s (cold 13.5 s) | T6 0/3: writes a fake `multiply` call as text; T4 0/3: guesses or picks the wrong id |
| Claude Code (Opus 5.5) | Anthropic | T1/T2/T4 **6/6** | ~13 s | none |

- `qwen3.5:4b` and `qwen3:4b` were dropped after the speed test: 7 tokens/s, and over a minute per question.
- During the local questions, the watcher took 805 samples of Ollama's connections and found **0** going outside this laptop.

**Local speed** (Ollama's own timings, warm): `granite4.1:3b` generates 31 tokens/s, with 85% of it on the GPU (2.7 GB loaded). Its cold start is 9-15 s, but the very first run after the download took 85 s once.

**Claude Code probe:**
```
billing check: CLEAN | outranking credentials set: none | login: claude.ai / firstParty / plan pro
session sees: model=claude-opus-5-5 | apiKeySource=none
  tools: ['mcp__pseudo_hands__focus_window', 'mcp__pseudo_hands__list_open_windows', 'mcp__pseudo_hands__read_active_window']
```
`apiKeySource=none` means the subscription was used, not an API key.

**Claude Code's T4 ran last,** after the owner turned "Help improve Claude" off, because it sends the redacted list of real window titles to Anthropic. `focus_window` isn't in `--allowedTools`, so Claude Code's own permission system refuses it before it reaches `pseudo_hands`:
```
T4 PASS tools=['list_open_windows', 'focus_window'] secs=20.0 denied=['mcp__pseudo_hands__focus_window']
```
That refusal says the permission "hasn't been granted", so for Claude Code the "says not approved" check also accepts "permission" and "grant".

## The criteria and the recommendation

| Criterion (set before measuring) | Result |
|---|---|
| Groq fallback passes (≥ 11/12) and has its own budget | `gpt-oss-20b` ✔ · `qwen3.8-27b` ✔ (but Preview, and ~40% more input tokens per call) |
| A local model passes (≥ 16/18, no invented tools, no cap hits) | `granite4.1:3b` ✔ · `lfm2.5:8b` ✘ · `llama3.2:3b` ✘ |
| Local: read ≤ 20 s warm, ≤ 60 s cold, ≥ 10 tokens/s, no outside connections | granite ✔ (the one-time 85 s first run is the exception) |
| Claude Code: exactly 3 tools, only `pseudo_hands`, billing clean every launch | ✔ (7/7 launches) |
| Claude Code: T1, T2, T4 | ✔ 4/4 and 2/2 |

**Recommendation (approved by Rishi as D16):**
1. **Groq fallback:** `gpt-oss-20b`, used only on a 429 and announced before it's used. Not `qwen3.8-27b`: Groq can drop Preview models at short notice.
2. **Private mode:** Ollama with `granite4.1:3b`, on `127.0.0.1` only, with cloud off. It never falls back to the cloud.
3. **Claude Code:** it works as a separate brain for `pseudo_hands` over MCP, not as a provider in the list. Real windows are allowed only while "Help improve Claude" stays off (turned off 2026-09-30); D6 keeps screen data away from any provider that may train on it.

## Try this

1. In `.env`, change `LLM_MODEL` to `openai/gpt-oss-20b` and ask `python -m pseudo_brain` about a window. Switching the model is one line; change it back afterwards.
2. In the venv, run `python -c "from pseudo_hands.core.redactor import redact; print(redact('Pseudo M15 notes'))"`. Then try `'Pseudo notes'` and `'Invoice 4471'`, and see which words the redactor treats as names or dates.
3. Start Ollama with `$env:OLLAMA_HOST="127.0.0.1:11434"; & "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" serve`. In a second terminal, run `& "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" run granite4.1:3b "What is 17 times 3?" --verbose` twice: the first run shows the cold load, and `eval rate` shows tokens/s. Press Ctrl+C in the first terminal to stop Ollama.

## Check yourself

1. Why did T1 fail for every model at first, and why was that a bug in the test rather than in the models?
2. Why does a fallback to `gpt-oss-20b` help when `gpt-oss-120b` is rate limited?
3. `granite4.1:3b` and `llama3.2:3b` are about the same size and speed. Why is one 18/18 and the other 10/18?
4. What could go wrong if Claude Code ran without `--tools ""`?
5. Why must private mode never fall back to Groq when Ollama fails?

<details>
<summary>Answers</summary>

1. The redactor masks "4471" as `[DATE_TIME]` before the text leaves `pseudo_hands`. No model ever saw the number, so no model could say it. The pass rule checked for something the privacy layer (correctly) hides.
2. Groq's limits are per model (measured): 120b's 429 doesn't touch 20b's 8K tokens/min, so 20b answers at once.
3. Size isn't the whole story: how well a model calls tools depends on how it was trained, and that varies more than size. llama3.2 wrote a tool call as plain text instead of answering, and guessed window ids without listing the windows first. Only a test on Pseudo's own questions shows this; the "tools" badge on a model page doesn't.
4. Claude would get Bash and Read, and could read raw window titles or files around `pseudo_hands`. Blocked apps and the redactor would be skipped, which D6 forbids.
5. Private mode is a promise that nothing leaves the laptop. A silent fallback would break that promise exactly when it matters. It must fail visibly instead (D15's honesty rule).
</details>

## How this connects to Pseudo's final architecture

- **M16 builds it:** a committed allowlist, `pseudo_brain/providers.toml`, with each provider's URL, the *name* of its key variable in `.env`, its models and a privacy note. It adds a same-provider fallback on 429, private mode through Ollama, and the provider shown with every answer.
- **Backlog notes:** the redactor over-masks non-personal text ("M15" becomes `[PERSON]`, order numbers become `[DATE_TIME]`). Ollama's default context is 4,096 tokens per call, while `pseudo_brain` allows up to about 3,000 estimated input tokens per call, so the private-mode build must check that margin.
- **D11 held:** three providers and two brains used the same `pseudo_hands` with no changes. M17's face will show which provider answered.
