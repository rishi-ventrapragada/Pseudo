# Pseudo: Architecture

Two parts: the long-term target (so every step has context) and the Phase 1 structure (what actually gets built now).

## 1. Long-term target (not Phase 1)

```
          voice / hotkey / typed prompt
                       |
             [ Pseudo Face ]  own React window in Electron (M18);
                       |       terminal first (M14); voice later
                       |  child-process pipe (stdin/stdout)
                       v
             [ pseudo_brain ]  Pseudo's own agent loop (D15, M14):
                       |        allowlisted providers (D16), same-provider fallback,
                       |        visible 429s, session history
                       |  calls tools via MCP (it is an MCP client)
                       v
             [ Pseudo Hands ]  MCP server on Windows
                       |
     window list . UI Automation tree . local OCR . click/type
                       |
     [ Privacy layer ]  blocked apps -> nothing sent
                        redactor (emails, phones, names, passwords, cards)
                       |
     [ Approval gate ]  delete/overwrite, send, submit/pay, install/run
                        native Windows popup shown by pseudo_hands (D13)
                       |
     clean text only -> cloud model (free tier)
```

Key ideas:
- The model runs remotely (Groq) or, in private mode, on this laptop (Ollama on 127.0.0.1, D16); Pseudo's code is the "hands" and "eyes" that run locally.
- Text before pixels: read the UI Automation tree (the desktop's DOM) first, local OCR/vision second. Screenshots never leave the laptop.
- Pseudo Hands is an MCP server so any MCP-capable agent can use it, not just Pseudo's own brain.
- Pseudo's brain is its own loop (D15). Hermes was the brain from M6 to M13 and stays installed, but M13 ruled out Hermes and Hermes Desktop: harness token cost, hidden provider fallbacks, and Desktop-only tools that bypass redaction.

This is a direction, not a commitment. It will be revisited after Phase 1.

### Designed for change (see DECISIONS.md D11)

```
   any brain: pseudo_brain (D15) | Hermes | Claude Code | local model
        |  MCP (tools)                  |  OpenAI-compatible API (chat)
        v                               v
   [ MCP wrapper ]  thin, swappable     [ Face ]
        |
   [ pseudo core ]  plain Python functions: perception, actions,
                    privacy layer, approval gate  <- the part that never changes
```

Every layer only knows about the standard interface below it. Swapping the brain, the provider, or the face means editing config or one adapter, not rewriting the core.

## 2. Phase 1: Foundations

Phase 1 builds a mini agent from scratch so the owner understands what Hermes, Claude Code, and every other agent do internally. The whole of Phase 1 is this loop:

```
  user task
      |
      v
  +-> send [system prompt + history + tool definitions] to model
  |       |
  |       v
  |   model reply: text answer?  --yes-->  print, done
  |       | no, it asks to call a tool
  |       v
  |   risky tool? --yes--> ask user y/n --no--> tell model "denied"
  |       |                    | yes
  |       v                    v
  |   run tool locally (sandboxed), capture result
  |       |
  +-- append tool result to history, loop  (stop at max iterations)
```

### Folder structure after Phase 1

```
Pseudo/
  CLAUDE.md, PRD.md, ARCHITECTURE.md, DECISIONS.md, README.md
  requirements.txt
  .env.example          template, committed
  .env                  real keys, NEVER committed
  .gitignore            .venv/, .env, __pycache__/, .pytest_cache/, playground/sandbox/*
  playground/
    00_check_setup.py
    01a_raw_http.py     plain HTTP call to the model
    01b_sdk.py          same call via openai SDK
    01c_memory.py       terminal chat, history on/off
    02_one_tool.py      single tool call, every step printed
    03_agent_loop.py    the loop above
    agent_tools.py      sandboxed file tools + sandbox check
    agent_tool_schemas.py their schemas: all the model ever sees of the tools
    sandbox/            the only folder the agent may touch (.gitkeep)
  tests/
    conftest.py         shared fixtures: temp sandbox, decoy outside folder, fake approvers
    test_agent_tools.py tool behavior, approval gate, schema contract
    test_sandbox.py     sandbox escape tests (../, absolute paths, Windows names, links)
  docs/
    learn/              lesson files written by Claude Code, one per milestone
  pseudo_hands/         Phase 2: see "Phase 2: pseudo_hands" below
```

### Libraries (Phase 1)

| Library | Why |
|---|---|
| httpx2 | Raw HTTP in M1a, to show a model call is just a POST request. Maintained successor to httpx, and the HTTP client the openai SDK itself uses. |
| openai | Standard SDK; works with any OpenAI-compatible endpoint (Groq, OpenRouter, Gemini's compat endpoint, Hermes' API server, Ollama). Learning it once transfers everywhere. |
| python-dotenv | Loads `.env`. |
| pytest | Tests for the tool functions in M3. |

Nothing else. No agent frameworks (LangChain etc.) in Phase 1: the point is to see the raw mechanics.

### Provider setup

- Primary: Groq free tier via its OpenAI-compatible endpoint (fast, no card needed).
- Config in `.env`: `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`. Swapping providers = editing `.env`, zero code changes. This is the same "swappable brain" idea Pseudo will use later.
- Claude Code verifies current free models and limits from official docs before M1; free tiers change often.

### Privacy in Phase 1

Only text the owner types (and files inside `playground/sandbox/`) is sent to the model. Nothing from the screen, no personal files.

## 3. Phase 2: pseudo_hands

```
pseudo_hands/
  core/                 plain Python; never imports MCP or Hermes (D11)
    windows.py          list_open_windows(): Windows API -> clean list of dicts; skips overlays (M12)
    blocked_apps.py     load the blocked list, mask blocked windows (D6)
    blocked_apps.txt    owner-editable list of .exe names
    redactor.py         redact(text): Presidio + spaCy, fail closed (M7)
    india_recognizers.py  +91 phone, Aadhaar, PAN, UPI, long-number patterns (M7)
    date_recognizers.py   birthday-shaped dates and ages by pattern; spaCy's date guesses are off (M19, D19)
    finding_filters.py    code-shaped words are never names; weak vehicle-plate shapes ignored (M19, D19)
    redaction_terms.txt   owner's private terms (gitignored; .example committed) (M7)
    allowed_names.txt   app/site names never masked (M8)
    ui_tree.py          walk a window's UI Automation tree -> raw lines (M9); skips failing controls (M12)
    active_window.py    read_active_window(): pick window, block, redact, cap (M9); retries once (M12);
                        skips the apps in assistant_apps.txt, so it reads the window you were on (M18)
    assistant_apps.txt  owner-editable list of assistant .exe names (the face, Claude, Hermes) (M18)
    window_ids.py       short ids ("w3") for listed windows, never reused (M10)
    approval.py         the approval gate: native popup, default no (D13, M10)
    focus.py            focus_window(): validate id, block, ask, act (M10)
  show_windows.py       thin CLI demo (M4)
  mcp_server.py         thin MCP wrapper (M5)
```

| Library | Why |
|---|---|
| pywin32 | Python wrappers for the Windows API (EnumWindows, window titles, process ids). |
| psutil | Turns a process id into an app name ("Code.exe"). |
| mcp | Official MCP Python SDK: MCPServer for pseudo_hands, Client for its tests. |
| presidio-analyzer / presidio-anonymizer | Microsoft's open-source PII detection and masking; runs fully locally. |
| spaCy + en_core_web_sm | The small English language model Presidio uses to spot names and places. |
| uiautomation | Thin wrapper over Windows' UI Automation API, used to read the active window's control tree (M9). |

## 4. Phase 5: pseudo_brain and the face

```
pseudo_brain/           Pseudo's own agent loop (D15, M14), grown from playground/03_agent_loop.py
  providers.toml        the D16 allowlist: each provider's URL, key VARIABLE name, models, privacy note (M16)
  providers.py          loads and checks it; refuses the rest (private = 127.0.0.1 only, no "cloud" names)
  model.py              one provider through AsyncOpenAI (D10), max_retries=0; a 429 moves to the SAME
                        provider's next model, then waits visibly; other failures -> ModelFailure
  local_server.py       private mode's own server (Ollama): started on /provider local after checking
                        cloud is off, 127.0.0.1 only, stopped when pseudo_brain exits (M16)
  hands.py              MCP CLIENT of pseudo_hands over stdio; tools discovered at startup, none named;
                        knows pseudo_hands' pid, for the face's popup permission (M18)
  chat.py               one conversation, shared by every interface: start, switch provider (closing
                        the old one's connections), new/open session, ask, stop servers (M18)
  session.py            history as whole turns, one provider per session; trimmed per request to the
                        provider's max_prompt_tokens;
                        saved to %LOCALAPPDATA%\Pseudo\sessions\ (your messages + final answers only)
  loop.py               SYSTEM_PROMPT + run_turn(): THE LOOP. Never prints: reports events via on_event
  terminal.py           thin interface: prints events, reads input, --continue, --provider, /provider,
                        /new, /quit
  bridge.py             thin interface for the face: JSON lines over stdin/stdout, no port (D18, M18)
  __main__.py           python -m pseudo_brain
face/                   Pseudo's own window (M18): Electron + React, display only (D11)
  main.js               Electron's main process: one sandboxed window, app:// pages from dist/ only,
                        relays messages between the page and the brain
  brain-process.js      starts `python -m pseudo_brain.bridge` as a child process; stops it on quit
  preload.js            the only door between page and main process: window.pseudo.send / onMessage
  foreground.js         before each tool runs, lets ONLY pseudo_hands bring its approval popup to
                        the front (AllowSetForegroundWindow, via koffi)
  taskbar-flash.js      flashes the taskbar button while a tool runs and you're in another window
  src/                  the React page: chat, live steps, Markdown answers, provider bar, sessions,
                        the approval banner
```

```
  you --> terminal.py --text--> loop.run_turn --request--> model.py --> the current provider (D16)
                  ^                   |   ^
                  +----- events ------+   | tool result (redacted in pseudo_hands core)
                                          v
                               hands.py --MCP stdio--> pseudo_hands (blocked apps, redactor, popup)
```

| Library | Why |
|---|---|
| openai (AsyncOpenAI) | The same SDK as Phase 1, async so it can share one event loop with the MCP client. |
| mcp (Client) | The MCP SDK's client side: starts pseudo_hands over stdio, lists and calls its tools. |
| anyio | Comes with mcp; runs the event loop, and `input()` in a helper thread so MCP keeps running. |
| tomllib | Built into Python 3.11+: reads `providers.toml` (M16). No new install. |
| psutil | Already used by pseudo_hands: `local_server.py` checks what listens on the server's port and stops the processes it started (M16). |

Privacy and approval don't move: blocked apps, redaction and the approval popup stay in `pseudo_hands` core (D6, D11, D13), so they hold for `pseudo_brain` exactly as they did for Hermes.
