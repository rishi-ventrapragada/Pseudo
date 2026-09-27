# Pseudo: Architecture

Two parts: the long-term target (so every step has context) and the Phase 1 structure (what actually gets built now).

## 1. Long-term target (not Phase 1)

```
          voice / hotkey / typed prompt
                       |
             [ Pseudo Face ]  resizable overlay + local voice
                       |       (talks to Hermes via its local API)
                       v
             [ Hermes Agent ]  brain: reasoning, memory, skills,
                       |        scheduling, coding
                       |  calls tools via MCP
                       v
             [ Pseudo Hands ]  MCP server on Windows
                       |
     window list . UI Automation tree . local OCR . click/type
                       |
     [ Privacy layer ]  blocked apps -> nothing sent
                        redactor (emails, phones, names, passwords, cards)
                       |
     [ Approval gate ]  delete/overwrite, send, submit/pay, install/run
                       |
     clean text only -> cloud model (free tier)
```

Key ideas:
- The model always runs remotely; Pseudo's code is the "hands" and "eyes" that run locally.
- Text before pixels: read the UI Automation tree (the desktop's DOM) first, local OCR/vision second. Screenshots never leave the laptop.
- Pseudo Hands is an MCP server so any MCP-capable agent can use it, not just Hermes.

This is a direction, not a commitment. It will be revisited after Phase 1.

### Designed for change (see DECISIONS.md D11)

```
   any brain: Hermes | own loop (Phase 1) | Claude Code | local model
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
    agent_tools.py      list_files / read_file / write_file + sandbox check
    agent_tool_schemas.py the three tool schemas: all the model ever sees of the tools
    sandbox/            the only folder the agent may touch (.gitkeep)
  tests/
    conftest.py         shared fixtures: temp sandbox, decoy outside folder, fake approvers
    test_agent_tools.py tool behavior, approval gate, schema contract
    test_sandbox.py     sandbox escape tests (../, absolute paths, Windows names, links)
  docs/
    learn/              lesson files written by Claude Code, one per milestone
  pseudo_hands/         created empty with a README placeholder; used in Phase 2
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
