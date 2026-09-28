# M6: Plug into Hermes

## The concept in one paragraph

A **harness** is the grown-up version of our M3 loop: it keeps the loop, but adds config files, a list of model **providers**, a **tool registry**, stored **sessions**, and safety settings. Hermes is ours. In M6 we didn't write any new Pseudo code. We *configured* Hermes to (1) use Groq's free `openai/gpt-oss-120b` as its brain and (2) start `pseudo_hands` as an MCP server. Then we asked "what am I working on right now?" and confirmed from Hermes' own records that it called `list_open_windows` and answered from the result, without ever reading the answer ourselves.

## Web-dev analogy

- `config.yaml` is like `vercel.json`, and the profile's `.env` is like your project's environment variables.
- `key_env: GROQ_API_KEY` is like writing `process.env.GROQ_API_KEY` in code. Config says *where* the secret lives, never *what* it is.
- A Hermes **profile** is like a separate Vercel project: its own config, env vars and data, with nothing shared with the others.
- `state.db` is like your server's request logs: it records every call, so you can check behavior without watching the screen.
- Hermes' **tool search** is like code-splitting: instead of shipping every tool schema up front, it ships a small loader and fetches schemas on demand.

## What was changed (all outside the repo) and why

| Change | Why |
|---|---|
| Backup of the default profile's `config.yaml` and `.env` | So anything can be undone. Both still match the backup byte-for-byte: **the default profile (Hermes Desktop) is untouched.** |
| New blank profile `pseudo` (`hermes profile create pseudo --no-alias --no-skills`) | Keeps `pseudo_hands` completely out of Desktop's config, so Desktop (on Nous) can never call it. |
| The profile's `config.yaml` | Groq is the only provider (`custom:groq`), `pseudo_hands` is the only MCP server, and there's no fallback provider. |
| `GROQ_API_KEY` in the profile's `.env` | Copied from the repo `.env` by a script that printed only True/False. The key never appeared anywhere. |
| `tools.tool_search.enabled: 'off'` | Shows our tool to the model directly (see the walkthrough below). |

**Note on "global" vs profile:** the first plan switched the *default* profile's model to Groq. That would have made every Hermes Desktop chat use Groq too, sharing its 8K tokens/min limit, which normal Desktop use can't fit into (see the tokens section below). That's one reason we used a separate profile instead: Desktop stays on Nous, and only runs with `-p pseudo` reach Groq.

The core of the profile config:
```yaml
model:
  default: openai/gpt-oss-120b
  provider: custom:groq            # -> the providers.groq entry below
providers:
  groq:
    api: https://api.groq.com/openai/v1
    key_env: GROQ_API_KEY          # the NAME of the variable, never the key
mcp_servers:
  pseudo_hands:
    command: 'C:\dev\Pseudo\.venv\Scripts\python.exe'
    args: ['-m', 'pseudo_hands.mcp_server']
    cwd: 'C:\dev\Pseudo'           # so `import pseudo_hands` works
    tools:
      include: [list_open_windows]
tools:
  tool_search:
    enabled: 'off'
```

## Walkthrough: what Hermes does with that

1. **Start the server.** Hermes runs `command` plus `args` in `cwd`: the same stdio process the Inspector started in M5. `hermes -p pseudo mcp test pseudo_hands` showed `Connected (11563ms)` and `Tools discovered: 1`.
2. **Register the tool** under a prefixed name. The records show `mcp__pseudo_hands__list_open_windows` (double underscores; the docs say `mcp_<server>_<tool>`, so trust the records over the docs). Hermes then converts it back into the OpenAI `{"type": "function", ...}` shape, the M3 format.
3. **Run the question** in one-shot mode:
   `hermes -p pseudo -z "what am I working on right now?" --provider custom:groq -m openai/gpt-oss-120b -t pseudo_hands`
   `-z` prints only the answer (our script held it in memory and never printed it). `-t` limits the tools.
4. **Wrap the result.** Hermes stores the tool result inside `<untrusted_tool_result>…</untrusted_tool_result>`, a label telling the model "this is data, not instructions" (a guard against prompt injection). The MCP SDK sent our list as one JSON text item per window, and Hermes joined them.

### The two things that went wrong first (and what they teach)

**1. The tool search bridge hid our tool.** With any MCP tool present, Hermes turns on **tool search** by default. Instead of `list_open_windows`, the model sees three bridge tools, `tool_search`, `tool_describe` and `tool_call`, and has to find tools itself. `gpt-oss-120b` didn't. It used `tool_call` to try **`terminal` with `ls -la`**. With one tiny tool, the bridge only adds confusion, so we turned it off for this profile.

**2. The blocked `ls -la`, and why `-t` mattered.** One-shot mode **auto-approves** tool calls: there's no human to answer y/n. Without `-t pseudo_hands`, the terminal tool would have been available, and the model's guess would have *run a shell command on your machine*, unasked. Because `-t` limited the run to our one tool, Hermes refused: `'terminal' is not a deferrable tool`. That's M3's lesson again: **when there's no approval gate, the only safety is what tools exist at all.** (In one-shot mode `-t` wants the bare server name `pseudo_hands`; `mcp-pseudo_hands` was rejected before the servers were discovered.)

**Bonus gotcha: exit code 0 on failure.** That first run exited 0, but its usage file said `failed: true`. When a Hermes turn fails, the error message *replaces the answer*, and one-shot mode exits 0 whenever the answer text isn't empty. **Check `failed`/`completed`, not just the exit code.**

## What happens when you run it (records only, annotated)

```
hermes exit code: 0 | seconds: 14.4
usage completed: True | failed: False                 <- check this, not just the exit code
usage input_tokens: 5916  output_tokens: 144  api_calls: 2
session billing_base_url: https://api.groq.com/openai/v1     <- only Groq was reached
tool calls requested (names only): ['mcp__pseudo_hands__list_open_windows']
windows in tool result: 6 | focused: 1 | masked: 0 | keys ok: True
notepad window in tool result: True                   <- the marker window we opened
windows from the tool result referenced in the answer: 1
answer mentions notepad (the marker): True            <- it answered FROM the tool result
```
Two API calls: (1) question plus tool schema → "call `list_open_windows`"; (2) tool result → final answer. That's the M3 loop, run by Hermes.

## Tokens: why harness size matters on free tiers

| Setup | Input tokens per call |
|---|---|
| Our M3 loop (3 small tools, short prompt) | about 530–610 (real: 529, 572, 606) |
| M6: `pseudo` profile (no skills, 1 tool) | about 3,000 (real: 5,916 over 2 calls) |
| Normal Hermes (default profile, 20 tools, skills) | about 14,000 (from `hermes prompt-size`: 22K-char prompt + 34.5 KB of tool schemas) |

Groq's free tier allows **8,000 tokens per minute** for this model. The M6 profile fits: two calls of about 3K each. A normal Hermes call does **not**: at about 14K, one request is bigger than the whole minute's budget, so Groq rejects it outright. That's the price of a full harness: a long system prompt, a skills index, and dozens of tool schemas are resent *on every call*. The M3 loop was about 25 times smaller. On free tiers, you keep harness runs small with a slim profile, few tools (`-t`) and no skills, or you use a provider with bigger limits.

(Hermes reported `estimated_cost_usd: 0.00097`. That's an estimate at paid prices; on Groq's free tier the call cost nothing.)

## Privacy ledger

- **Went to Groq:** the question, the one tool schema, the titles of your 6 non-blocked windows, and the answer. This is the known Phase 2 gap: there's no redactor until Phase 4.
- **Stayed local:** the session (question, tool result, answer) in `%HERMES_HOME%\profiles\pseudo\state.db`.
- **Never left:** blocked apps (masked in `core/`, before Hermes saw anything), your keys, and anything to Nous.
- **Never seen by Claude Code:** your titles and the answer. Every check printed counts, names or booleans.

## Try this

1. Run `hermes -p pseudo mcp test pseudo_hands` and read the connection report.
2. Temporarily set `tool_search.enabled: 'on'` in the profile, rerun, and watch the tool call become `tool_call` again (records only).
3. Run `hermes prompt-size` (default profile) and `hermes -p pseudo prompt-size`, and compare the two budgets.

## Check yourself

1. Why a separate profile instead of adding Groq to the default one?
2. What does `key_env` store, and why is that safer than putting the key in `config.yaml`?
3. Why did `-t pseudo_hands` matter more in one-shot mode than in an interactive chat?
4. The first run exited 0. How did we know it had failed?
5. Why does a normal Hermes call not fit Groq's free tier when M6's does?

<details>
<summary>Answers</summary>

1. Desktop (default profile, Nous) must never see `pseudo_hands`, and Desktop shouldn't share Groq's 8K/min limit. A profile isolates config, keys and sessions completely.
2. The *name* of an environment variable. The key lives only in `.env`, and config files can be read, shared or shown without leaking it.
3. One-shot mode auto-approves tools, so there's no y/n gate. `-t` decides which tools exist, and the model tried to run `ls -la` through the terminal tool.
4. The usage file said `failed: true` / `completed: false`. On failure, Hermes turns the error message into the "answer", so the exit code stays 0.
5. Default Hermes sends about 14K tokens per call (prompt, skills and 20 tool schemas), which is more than the 8K/min budget. The `pseudo` profile sends about 3K (no skills, one tool).

</details>

## How this connects to Pseudo's final architecture

- **D11 in practice:** we changed the brain's config, not Pseudo's code. The same `pseudo_hands` serves the Inspector, our tests and Hermes.
- **Phase 3 tools** (`focus_window`, the UI tree) get one `add_tool` line in `mcp_server.py`, plus the profile's `tools.include`. Their approval gate lives in `core/`, because one-shot runs have no human.
- **Phase 4's redactor** closes the gap in the privacy ledger: titles get cleaned in `core/` before any brain sees them.
- **Hermes Desktop as the face** (L5) can use this setup later, once a slim Desktop profile fits a free tier or another provider is chosen.
