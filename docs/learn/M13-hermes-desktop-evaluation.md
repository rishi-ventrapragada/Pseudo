# M13: Can Hermes Desktop be the face? (evaluation)

## The concept in one paragraph

M13 asked whether Pseudo could be used day to day through **Hermes Desktop**, Hermes' graphical app, instead of `hermes -p pseudo` in a terminal. Instead of trusting the docs, we **audited** Desktop: we read its source (it's installed from Git, so the code is on this laptop), and we read its **records** (the `state.db` database, the logs, and Hermes' own status commands). We looked only at counts, names and sizes, never at chat text or window titles.

A **gate** was set before measuring: if any automatic route could send Pseudo's data to a provider other than Groq, there would be no live runs. The gate failed. The audit also found a Desktop-only tool that reads window titles **around** Pseudo's privacy layer. So Desktop was ruled out, and a new locked decision, **D15**, makes Pseudo's brain its own agent loop.

## Web-dev analogy

- Auditing Desktop is like checking what a third-party npm package does before shipping it: which network calls it makes and which permissions it asks for. You read its code, not its README.
- The **auxiliary fallback** is a CDN failover. When your primary origin errors, the CDN silently serves from another provider. That's fine for images, but not for private data.
- **Root `auth.json` inheritance** is like `~/.npmrc`: every project on the machine reads your home-directory credentials, even ones you never configured.
- `read_window_below` is like a browser extension with the `tabs` permission: it can read every tab's title, and your own site's privacy code never runs in between.

## What was built (file by file)

- **In the repo:** no code. The PRD records the M13 result and adds M14/M15, `DECISIONS.md` adds **D15** (D12 superseded), and ARCHITECTURE and README follow it.
- **Outside the repo:** the `pseudo` profile was hardened, after a backup to `backups-pseudo\pre-M13-<time>\`:
  ```yaml
  agent:
    bot_mode_protocol: false        # no Bot Chat protocol or message_agent tool
  platform_toolsets:
    cli: [pseudo_hands]             # Pseudo's tools only
  auxiliary:
    title_generation:
      enabled: false                # no auto-titles (an auxiliary call that can fall back)
  ```
- **In the scratchpad, not committed:** `m13_safe.py` (runs a Hermes command and masks keys, tokens and **emails** in its output), plus small scripts for prompt sizes, Desktop's extras, the fallback chain and the fix check.

## Walkthrough of the key code (Hermes' own source)

**1. Desktop starts one backend per profile** (`apps/desktop/electron/main.ts`):
```ts
const backendArgs = ['--profile', profile, 'serve', '--host', '127.0.0.1', '--port', '0']
```
So Desktop can run `pseudo`: it appears in the sidebar and in Bot Mode (a "Bot" *is* a profile).

**2. Desktop-only tools are added after every filter** (`tui_gateway/server.py`):
```python
return sorted(enabled | _gui_surface_toolsets(session_platform)) if enabled else None
```
`enabled` is the profile's toolsets, with `platform_toolsets` and `agent.disabled_toolsets` already applied. The `|` (set union) adds `desktop_ui` and `project` *afterwards*, so **no profile setting can remove them**.

**3. `read_window_below`**, one of those 11 `desktop_ui` tools, describes itself as "Identify the app window directly behind the Hermes desktop window (what the user is working in) … Metadata only; never captures pixels." "Metadata" means the **app name and raw title**. No blocked-apps check, no redactor. A WhatsApp chat title would reach the model as-is.

**4. The auxiliary fallback chain** (`agent/auxiliary_client.py`):
```python
("openrouter", _try_openrouter), ("nous", _try_nous),
("local/custom", _try_custom_endpoint), ("api-key", _resolve_api_key_provider),
```
Titles and compression are **auxiliary** tasks: small side-calls Hermes makes on its own. On a Groq **capacity error** (a 429), they walk this chain. Even a task pinned to one provider gets a second pass through it. Copilot was skipped (no known model for it); Nous was not.

**5. Why removing the Nous login didn't work** (`hermes_cli/auth.py`):
```python
"""Provider state; in profile mode falls back to the global-root ``auth.json`` per provider (same
shadowing as ``read_credential_pool``), so profile workers see globally-authed providers."""
```
`pseudo` never needed its own Nous login: it reads `default`'s from the root, provider by provider, with no switch to turn that off.

## What happens when you run it (real output, annotated)

**Records.** Every model call `pseudo` ever made, by task and provider:
```
('',                 'custom', 'https://api.groq.com/openai/v1',  … 31 calls)
('title_generation', 'custom', 'https://api.groq.com/openai/v1/', … 16 calls)
```
Groq only, so nothing had leaked **yet**. A risk is a route that exists, not only one that has been used.

**Desktop was already on `pseudo`.** `active-profile.json` said `profile = pseudo`, and a `serve --profile pseudo` backend was running with 2 `pseudo_hands` servers, plus one empty "Bot Chat" (0 tokens).

**Fixed cost per call, measured offline with `hermes -p pseudo prompt-size`:**
```
system_prompt.chars: 16783 | tools.count: 22 | tools.json_bytes: 45662     <- ~15.6K tokens
toolsets: computer_use, file, terminal, delegation, skills, memory, session_search,
          browser-use, code_execution, web, tts, clarify, image_gen, todo, vision
```
Desktop adds the long desktop hint (1,929 chars) and `desktop_ui` + `project` (12 tools, 11,740 bytes), so a Desktop question comes to about **16-17K tokens**. Groq's free tier allows **8K per minute**.

**Credentials `pseudo` can use** (masked by `m13_safe.py`):
```
copilot (1 credentials):  #1  gh auth token   api_key gh_cli
nous (1 credentials):     #1  [masked] oauth  device_code
```

**The fix, and what it showed:**
```
hermes -p pseudo auth remove nous 1   ->  Removed nous credential #1 ([masked])
hermes -p pseudo auth list            ->  nous (1 credentials) ... still there: re-read from the root
after the config change: system_prompt.chars 8116 | built-in tools 0 | pseudo_hands: Tools discovered: 3
```

## The gate, the criteria, and the decision

The criteria were written before measuring, as in M11:
- **H1:** a non-Groq route that profile config can't close.
- **H2:** the popup fails.
- **H3:** over 6,000 tokens per call even when trimmed.

What we found:
- **Gate G1 failed** (Nous was reachable), so the live runs never happened, and H2 stayed unmeasured.
- **H3 failed on an estimate:** about 6.6K per call, because the Desktop-only tools can't be removed.
- **`read_window_below`** sends data to Groq, not to a new provider, so H1 as written didn't cover it. Rishi accepted it as a hard failure anyway: it skips blocked apps and redaction, which D6 forbids for **any** provider.

The result is **D15**: Pseudo's brain becomes its own loop.

## Try this

1. Run `hermes -p pseudo prompt-size` and then `hermes prompt-size` (the default profile). Both run offline. Compare the tool counts: that's the harness cost D15 is about.
2. Run `hermes -p pseudo auth list`. Nous still appears, though you never logged in to Nous inside `pseudo`: that's the root fallback. (It prints your account email, to your own terminal only.)
3. Open `%LOCALAPPDATA%\hermes\hermes-agent\tools\read_window_tool.py` and look for the line where the title would be redacted or a blocked app masked. It isn't there. Compare with `pseudo_hands/core/windows.py`.

## Check yourself

1. The records showed no call ever went to Nous. Why was Nous still treated as a real risk?
2. Why couldn't `platform_toolsets` or `agent.disabled_toolsets` remove `read_window_below`?
3. Why did `hermes -p pseudo auth remove nous 1` not remove Nous?
4. Why did the plan stop before the live runs, even though they used fake windows?
5. After D15, why doesn't `pseudo_hands` need to change at all?

<details>
<summary>Answers</summary>

1. Records show what *happened*; the audit asks what *can* happen. The fallback only fires on a Groq capacity error, and M9 showed those happen. One unlucky 429 during a title call would have sent the conversation to Nous.
2. Both settings shape the profile's toolset list, and Desktop adds its surface toolsets to that list *afterwards* (`enabled | _gui_surface_toolsets(...)`). The agent is also built without a `disabled_toolsets` argument.
3. The pool row is rebuilt from the Nous login state, and in profile mode Hermes reads that state from the root `auth.json` when the profile has none. `default` is signed in, so `pseudo` sees it too.
4. Live runs create real sessions, and a Desktop session's first exchange includes `list_open_windows` output: your redacted but *real* window titles. With a Nous route open, a 429 during title generation could have sent that to Nous. The gate prevented producing evidence by leaking.
5. D11: every privacy rule (blocked apps, redaction, the approval popup) already lives in `pseudo_hands` core, behind a standard MCP interface. Changing the brain changes the MCP *client*, not the server.
</details>

## How this connects to Pseudo's final architecture

- **M14** turns the M3 loop into `pseudo_brain`: an **MCP client** of the same `pseudo_hands` server Hermes used, calling Groq directly with no fallbacks, handling 429s visibly and saving session history.
- **M15** adds a React window (Tauri or Electron) on top, through a local server.
- The `pseudo` profile was hardened first (Pseudo's tools only, no auto-titles, no Bot Mode protocol). The Nous route through the root login couldn't be closed from inside the profile, so the `pseudo_hands` server was then **disabled** in the `pseudo` profile (`enabled: false`, after a backup). `hermes -p pseudo mcp list` shows it `✗ disabled`, so no Pseudo data can reach Hermes at all until the profile is retired.
