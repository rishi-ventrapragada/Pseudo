# M16: Providers build

## The concept in one paragraph

M15 chose the providers. M16 makes `pseudo_brain` use only those. The list lives in one committed file, `providers.toml`, which is an **allowlist**: anything not on it is refused. The model client still speaks the OpenAI-compatible API (D10), so Groq and Ollama differ only in URL, key and model names. When Groq rate-limits the main model (a **429**), Pseudo announces a **fallback** to the *next model of the same provider* and continues. It never moves to another provider. **Private mode** (Ollama on this laptop) is protected in three ways:
- The file refuses any private address that isn't the loopback address `127.0.0.1` ("this machine").
- A **session** belongs to one provider for life, so a private conversation can never be sent to the cloud later.
- `pseudo_brain` starts Ollama itself, refuses to if Ollama's cloud switch isn't off, and stops it when it exits.

## Web-dev analogy

- **`providers.toml`** is like `images.remotePatterns` in `next.config.js`, or CORS allowed origins: a reviewed list in git, and anything else is refused.
- **`key_env = "LLM_API_KEY"`** is like naming `process.env.SUPABASE_KEY` in code: config names the variable, and `.env` holds the value.
- **Same-provider fallback** is like failing over to another replica in the same region, never to a different vendor.
- **A session bound to a provider** is like a Supabase row-level policy: data tagged for one owner can't be read by another.
- **`local_server.py`** is like a `dev` script that runs `supabase start` before your app and stops it when you Ctrl+C.
- **`127.0.0.1` vs `0.0.0.0`** is `next dev` (only you) vs `next dev -H 0.0.0.0` (anyone on your Wi-Fi).

## What was built (file by file)

- **New:**
  - `pseudo_brain/providers.toml`: the D16 allowlist.
  - `pseudo_brain/providers.py`: loads it and refuses bad entries.
  - `pseudo_brain/local_server.py`: private mode's own server, started and stopped by `pseudo_brain`.
- **Changed:**
  - `model.py`: a `Model` now belongs to one provider; it handles the fallback, `check()` and `connect_provider()`.
  - `loop.py`: every question starts on the main model, uses the provider's own budget, and its events name the provider.
  - `session.py`: a session keeps one provider and records who answered; file names now go to the millisecond.
  - `terminal.py`: `--provider`, `/provider`, visible switching, and unknown commands never sent.
- **Tests:**
  - `brain_fakes.py`: shared fakes; `FakeModel` is now the *real* `Model` with scripted replies;
  - new `test_brain_providers.py`, `test_brain_fallback.py`, `test_brain_local_server.py` and `test_brain_terminal.py`.
- **Docs:** D10, L8, ARCHITECTURE, the `pseudo_brain` README and `.env.example`.

## Walkthrough of the key code

**1. The allowlist** (`providers.toml`, shortened):
```toml
[providers.groq]
base_url = "https://api.groq.com/openai/v1"
key_env = "LLM_API_KEY"                                  # the NAME of the variable, never the key
models = ["openai/gpt-oss-120b", "openai/gpt-oss-20b"]  # first = main; the rest = 429 fallbacks

[providers.local]
base_url = "http://127.0.0.1:11434/v1"
models = ["granite4.1:3b"]
leaves_laptop = false
```

**2. Refusing a private provider that could leave the laptop** (`providers.py`):
```python
if url.hostname != LOCALHOST or port is None:
    raise refuse(f"a private provider must be at {LOCALHOST}:<port>, not {url.hostname}")
cloudy = [m for m in models if "cloud" in m.lower()]
```
Why `localhost` is refused: it's a *name*, and a hosts-file entry can point it anywhere. `127.0.0.1` can't be redirected. Tricks like `http://127.0.0.1@evil.com` are refused too, because Python reads their real host as `evil.com`. And `leaves_laptop = "false"` (with quotes) is refused: it's a non-empty string, which Python treats as *true*.

**3. The fallback** (`model.py`, `call_model`):
```python
except openai.RateLimitError as error:
    limited = model.name
    if model.fall_back():  # the next model of the SAME provider, announced before it's used
        on_event("fallback", {"provider": model.provider.id, "from": limited, "to": model.name})
        continue
```
A `Model` is built from **one** `Provider` and never sees another. So "never fall back to another provider" isn't a rule the code has to remember: there's nothing to fall back *to*. On the provider's last model, M14's visible wait applies.

**4. A session keeps its provider** (`loop.py`, before anything is sent):
```python
if session.provider and session.provider != provider.id:
    return fail(result, f"this session belongs to {session.provider}, not {provider.id}; ...")
```
This check lives in the loop, not in the terminal, so M17's face gets the same protection automatically.

**5. Starting Ollama safely** (`local_server.py`, `start`):
1. `cloud_is_off()`: `server.json` must say `"disable_ollama_cloud": true`; otherwise nothing starts.
2. `launch()`: runs `ollama.exe serve` with `OLLAMA_HOST=127.0.0.1:11434`, no console window, logging to `%LOCALAPPDATA%\Pseudo\local_server.log`.
3. Wait until it answers; fail visibly if it exits or takes more than 30 s.
4. `listening_on(port) - {"127.0.0.1"}` must be empty; otherwise it's stopped.

`stop()` kills the model runners first, then the server. A server someone else started is used but never stopped.

## What happens when you run it (real output, annotated)

**The terminal, with commands only.** This run used the fixed terminal; the first attempt went wrong, as explained below.
```
--- PROVIDER groq (Groq): openai/gpt-oss-120b, fallback openai/gpt-oss-20b | data leaves this laptop: YES | ...
you> --- UNKNOWN COMMAND /provder: nothing was sent. Commands: /provider, /provider <id>, /new, /quit ---
you> --- REFUSED: "cloudy" is not in the allowlist (providers.toml). Allowed: groq, local. Still on groq. ---
you> --- PRIVATE SERVER for local: checking cloud is off, then starting it on 127.0.0.1:11434 ---
--- SERVER READY on 127.0.0.1:11434 in 1.3 s (started by Pseudo; stopped when Pseudo exits) ---
--- SWITCHED TO local: NEW SESSION 20260930-230137-402 (a session keeps one provider) ---
you> --- STOPPED the local server (Pseudo started it) ---          <- 0 ollama processes afterwards
```
Ollama's own log for that start: `Ollama cloud disabled: true` and `Listening on 127.0.0.1:11434`.

**A real fallback.** Fake filler text used up 120b's per-minute budget first:
```
--- SENDING TO groq · openai/gpt-oss-120b (call 1 of max 6) | 2 messages + 3 tools, ~581 tokens ---
--- RATE LIMITED (429) on openai/gpt-oss-120b: switching to openai/gpt-oss-20b (the next model of groq; ...) ---
tokens: 510 in / 28 out (estimated ~581 in) | budget left this minute: 7249 of 8000   <- 20b's OWN budget
--- ANSWER (groq · openai/gpt-oss-20b, fallback | 2 model call(s), 1172 tokens in / 141 out) ---
```
The next question ("What is 17 times 3?") started on 120b again, met the 429 again, and switched again.

**Private mode, fake window:**
```
--- ANSWER (local · granite4.1:3b | 2 model call(s), 1328 tokens in / 120 out) ---
pseudo> The active window titled "Pseudo [PERSON] notes" ... Project status: BLUE (fake) ...
--- FAILED: could not reach Private mode (Ollama) (network problem or timeout). No answer was produced. ---
[net] connections outside this laptop (python, pseudo_hands, Ollama): 0 in 142 samples
```
The `FAILED` line came after the test stopped Ollama on purpose: the question failed visibly, with no fallback. `tokens: 585 in (estimated ~581)`: the estimate is close, so the 2,500-token budget leaves room inside Ollama's 4,096-token context.

**What went wrong first.** The first terminal run was fed `/provider` through a PowerShell pipe. PowerShell adds an invisible **byte-order mark** (BOM, the bytes `EF BB BF`) at the start of piped text, so Pseudo read `﻿/provider`. That's not a known command, so it went to Groq as a *question*. The model called `list_open_windows`, and a redacted list of real window titles went to Groq. The fix has two parts:
- the BOM is removed;
- any unknown `/` command is refused locally, so a typo can never become a question.

## Try this

1. Run `python -m pseudo_brain`, then `/provider local`. Watch `SERVER READY`, then `/quit`: Task Manager shows no `ollama.exe`.
2. In `providers.toml`, change local's `base_url` to `http://localhost:11434/v1` and start Pseudo: it can't start. Then run `git checkout pseudo_brain/providers.toml`.
3. Ask something in private mode, `/provider groq`, then ask "what did I just ask you?" Groq can't know: the history stayed with the private session.

## Check yourself

1. Why is `localhost` refused for private mode, when it usually means the same as `127.0.0.1`?
2. Why does `/provider` always start a new session?
3. Why can't private mode fall back to Groq, even if the loop had a bug?
4. Why is `leaves_laptop = "false"` refused?
5. Why was stripping the BOM not enough on its own?

<details>
<summary>Answers</summary>

1. `localhost` is a name that the hosts file (or a program that edits it) can point elsewhere. `127.0.0.1` is the loopback address itself: traffic to it never leaves the machine.
2. A session's history holds your messages, answers and (in memory) redacted screen text. If it moved to another provider, a private conversation could end up in the cloud. The loop refuses a session from another provider, and a new session makes the switch explicit.
3. A `Model` is built from one `Provider` and only knows that provider's models. There's no reference to Groq anywhere in a private `Model`, and the loop also refuses a private session given to a Groq model.
4. In TOML, `"false"` in quotes is a string, and any non-empty string counts as true in Python. The file would *say* private while the code treated it the opposite way. A label that doesn't mean what it says is the one thing an allowlist can't have, so only a real `true` or `false` is accepted.
5. The BOM was one cause; the real hole was that *anything* the terminal didn't recognize became a question. A typo like `/provder` would have done the same. Refusing unknown commands closes the whole class of bug.
</details>

## How this connects to Pseudo's final architecture

- **M17's face** calls the same `connect_provider()` and shows the same events (`fallback`, `server_ready`, provider and model in every answer). The session rule lives in the loop, so the face can't break it.
- **Next after the face:** the redactor over-masks non-personal text (Backlog, high priority).
- **Claude Code** stays a separate brain over MCP (D16), not an entry in `providers.toml`.
