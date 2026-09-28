# Pseudo: Product Requirements Document

Owner: Sai Rishi Ventrapragada
Repo: https://github.com/rishi-ventrapragada/Pseudo
Status: Phase 1-4 complete (M11 evaluated OCR and skipped it). Phase 5 (Make it usable) in progress: M13 done (Hermes Desktop ruled out; own brain per D15), M14 next. Open follow-ups are in section 12, Backlog.
Last updated: 2026-09-28

## 1. What Pseudo is

Pseudo is the owner's zero-budget **Agentic OS for Windows**: one assistant, living on his laptop, that:

1. **Remembers every task he has done.** Memory is stored locally; only the relevant memories, redacted, are sent to the model.
2. **Sees and reads his screen.** Everything it reads is redacted before anything leaves the laptop.
3. **Asks permission before any edit or action**, through a native popup whose default answer is no.
4. **Talks to him and listens to him**, with local voice.
5. **Can control whatever he is looking at** to help with any task: click and type, always behind the approval popup.

The name is a nod to pseudonymization: Pseudo's defining feature is that what it sees and remembers is understood and redacted locally before anything reaches a cloud model.

## 2. Why this project exists (the real goal)

The owner's background is web dev (React, Supabase, Vercel) and some app dev. Agents are new territory. **Pseudo is a learning project first and a product second.** Claude Code does the building; the owner studies what was built and why, milestone by milestone, until he can plan and extend Pseudo's architecture himself.

Every deliverable is judged on two things:
1. Does it work?
2. Can the owner explain every line of it after reading the lesson notes?

If (2) fails, the milestone is not done.

## 3. Constraints (non-negotiable)

| Constraint | Detail |
|---|---|
| Budget | Zero. Free model tiers only. No paid APIs, no credit cards. |
| Hardware | One laptop: GTX 1650 (4GB VRAM), Ryzen 5, 16GB RAM. |
| OS | Windows only for now. Commands are PowerShell. |
| Privacy | No screenshots or raw screen content ever leave the machine. Screen data is processed locally and redacted before any cloud call. Code files go to the cloud only with per-project permission. |
| Language | Python for all of Pseudo's own code. |

## 4. Long-term shape (for context only, NOT Phase 1 scope)

- **Brain:** `pseudo_brain`, Pseudo's own agent loop (D15), grown from the Phase 1 loop. It is an MCP client of Pseudo Hands and talks to a free cloud model (Groq) through the OpenAI-compatible API. Hermes Agent stays installed but is not Pseudo's brain (M13).
- **Pseudo Hands:** an MCP server exposing Windows tools (window list, UI Automation tree, local OCR, click/type) with a local privacy/redaction layer and an approval gate for risky actions.
- **Pseudo Face:** our own React desktop window (Tauri or Electron) talking to `pseudo_brain` through a local server, plus local voice later. Hermes Desktop was ruled out in M13.

See ARCHITECTURE.md. These later phases may change once the owner understands the foundations. Do not build any of them in Phase 1.

## 5. Phase plan

| Phase | Name | Outcome |
|---|---|---|
| 1 | Foundations (complete) | Owner understands LLM APIs, tool calling, and the agent loop by building a mini agent from scratch. |
| 2 | First MCP server | `pseudo_hands` with `list_open_windows`, plugged into Hermes. |
| 3 | Privacy layer | Local redaction (Presidio + Indian recognizers + owner rules), applied to window titles. |
| 4 | Reading and acting (complete) | UI Automation tree reader, `focus_window`, approval gate (native popup, D13). Local OCR evaluated in M11 and skipped for now. |
| 5 | Make it usable | Use Pseudo day to day, not just through `hermes -p pseudo` in a terminal. M13 ruled out Hermes Desktop, so Pseudo gets its own brain (`pseudo_brain`, D15, M14) and its own face (M15). |

### Roadmap toward the vision (section 1)

1. **M14: own brain.** `pseudo_brain`, Pseudo's own loop as an MCP client of `pseudo_hands` (D15).
2. **M15: own face.** A React desktop window talking to `pseudo_brain` through a local server.
3. **Memory.** The local task memory from section 1, as a dedicated markdown vault (L6).
4. **Voice.** Local listening and speaking (L5).
5. **Click and type control.** Acting on whatever is on screen, always behind the approval popup (D13, D14).

Each step gets its own plan, and its milestone numbers, when it starts.

## 6. Phase 1 scope: Foundations

Four milestones. Each lives in `playground/`, is small, and ends with a lesson file in `docs/learn/`.

### M0: Project setup
- Python virtual environment, `requirements.txt`, `.gitignore`, `.env.example`, README.
- Folder skeleton from ARCHITECTURE.md.
- **Done when:** `python playground/00_check_setup.py` prints Python version, confirms the venv is active, and confirms `.env` is readable without printing the key.

### M1: Talk to a model
- `01a_raw_http.py`: call a free model with a plain HTTP request (httpx2), no SDK, so the owner sees it is just an API.
- `01b_sdk.py`: same call through the `openai` SDK pointed at an OpenAI-compatible free provider.
- `01c_memory.py`: a terminal chat that keeps history in a Python list, plus a flag to disable history so the owner sees the model forget.
- **Done when:** all three run; the owner can explain why the model "forgets" without the history list.

### M2: Tool calling
- `02_one_tool.py`: define one tool (`get_current_time`), send it with a question, show the model's tool-call request, run the function locally, send the result back, print the final answer.
- Print every raw request/response step in readable form so nothing is hidden.
- **Done when:** the owner can explain that the model never runs code; the program does.

### M3: Mini agent loop
- `03_agent_loop.py`: a while-loop agent with three tools: `list_files`, `read_file`, `write_file`.
- All file tools are locked to `playground/sandbox/` (path escape attempts are refused).
- `write_file` requires a y/n approval in the terminal (Pseudo's first safety gate).
- Hard cap on loop iterations.
- Tool functions split into `playground/agent_tools.py` with pytest tests in `tests/`.
- **Done when:** asked "create a notes.md with three study tips, then add a fourth", the agent completes it through multiple tool calls with approvals, and tests pass.

### Phase 1 exit criteria
- All four milestones done, committed, and each has a lesson file.
- Owner can draw the agent loop from memory.

Extra: count_words tool added as a learning exercise (Sept 28).

## 7. Out of scope for Phase 1

MCP, Hermes integration, screen reading, OCR, UI automation, voice, overlay, memory database, scheduling, local models, any GUI.

## 8. Phase 2 scope: First MCP server

Three milestones. Core code lives in `pseudo_hands/core/` (plain Python, no MCP); wrappers stay thin (D11). Each milestone ends with a lesson file.

### M4: list_open_windows in the core
- `pseudo_hands/core/windows.py`: `list_open_windows()` returns the visible top-level windows (title, app, focused) via the Windows API. Plain Python, no MCP.
- `pseudo_hands/core/blocked_apps.py` + `blocked_apps.txt`: windows of listed apps come back as "[restricted app]" (D6), so no sensitive titles reach the cloud even before the redactor (Phase 3).
- pytest tests with fake window data, plus one smoke test against the real Windows API.
- **Done when:** `python -m pseudo_hands.show_windows` lists the open windows with the focused one marked and blocked apps masked, tests pass, and the owner can explain why blocking is decided by process name, not window title.

### M5: Thin MCP server
- `pseudo_hands/mcp_server.py` exposes `list_open_windows` over MCP with no logic of its own.
- **Done when:** the MCP Inspector lists the tool, and calling it returns the same result as the core function, blocked apps still masked.

### M6: Plug into Hermes
- Connect `pseudo_hands` to the installed Hermes Agent with a free Groq model. Claude Code edits Hermes config itself, after a backup and plan approval.
- **Done when:** asked "what am I working on right now?", Hermes calls `list_open_windows` and answers from the result.

Closed in M8: titles are redacted in core before any brain sees them.

Out of scope for Phase 2: UI Automation tree, focus_window, click/type, OCR, Presidio redaction, own UI, voice, memory, scheduling.

## 9. Phase 3 scope: Privacy layer

Built before any tool reads window contents (D6): nothing is read that can't be redacted first.

### M7: Local redactor
- `pseudo_hands/core/redactor.py` + `india_recognizers.py`: `redact(text)` masks personal info locally with Presidio (spaCy model on this laptop), custom recognizers for Indian formats (+91 phones, Aadhaar, PAN, UPI IDs), and the owner's own terms list.
- Fail closed: any detection is masked regardless of confidence; Indian formats match by shape, not checksum; any error raises instead of returning unredacted text.
- Tested only on fake text. No network needed at runtime.
- **Done when:** tests pass on fake data, `python -m pseudo_hands.show_redaction` shows fake titles before/after with timings, and the owner can explain why the redactor fails closed.

### M8: Redact window titles
- Apply the redactor inside `list_open_windows()` (core), closing the Phase 2 browser-title gap.
- **Done when:** verified through MCP and the Hermes `pseudo` profile using counts only (no real titles printed).

Out of scope for Phase 3: reading window contents (UI Automation, OCR), actions, approval popups (Phase 4).

## 10. Phase 4 scope: Reading and acting

Everything read goes through the blocked-apps mask and redact() before it leaves core (D6).
Every action goes through a native approval popup owned by pseudo_hands (D13).

### M9: read_active_window
- Read the active window's UI Automation tree (visible text, control names and types), redacted with redact() before returning, capped in size so calls stay under Groq's 8K tokens/min.
- Blocked apps return nothing: their tree is never even read. Password fields are never read.
- **Done when:** tests pass on fake trees, and a fake-content Notepad window reads back as a redacted outline through core, MCP and the Hermes pseudo profile, verified with fake data and counts only.

### M10: Approval popup + focus_window
- A native Windows approval popup in core (D13), default deny: closing it or timing out means no.
- `focus_window(window_id)` as the first action tool, always behind the popup. `list_open_windows` gives each window a short id (titles are redacted, so a title can't be the key); blocked apps get none.
- **Done when:** approve, deny and timeout are tested on fake windows, and denial leaves focus unchanged.

### M11: OCR fallback (evaluate first)
- Local OCR for windows whose UI tree is empty, redacted the same way.
- Start by measuring how often M9 finds an empty tree; build only if it's needed.
- Evaluated 2026-09-28: 0/3 open windows and 0/6 other apps needed OCR; skipped. Revisit for DaVinci Resolve or games.

### M12: Harden the readers
- The UI tree walk skips a control that fails to read (and everything inside it) and keeps going, instead of losing the whole read. The note says how many controls were skipped.
- If a read fails, or finds nothing inside the window, on the first attempt, read_active_window waits briefly and retries once (the Chromium/Electron cold start).
- Invisible and click-through overlays (WS_EX_TRANSPARENT, or a tool window that can never be activated) are not user windows: not listed, no ids, never read or focused.
- **Done when:** tests pass on fake trees and fake windows, and the M11 counts-only method shows claude.exe readable, a freshly launched Obsidian readable on the first call, and the overlays gone from list_open_windows.

Out of scope for Phase 4: typing, clicking (beyond focus), voice, own UI.

## 11. Phase 5 scope: Make it usable

Goal: use Pseudo day to day, not just through `hermes -p pseudo` in a terminal. The rules so far still hold: pseudo data reaches only Groq, redacted (D6), and every action goes through the native approval popup (D13).

### M13: Can Hermes Desktop be the face? (evaluate first)
- Using only records, counts and fake-data windows, find out: whether Desktop can run the `pseudo` profile (profile rail or Bot Mode) and how; what Desktop adds on top of the profile (system prompt, tools, skills) and the real token cost per question; whether anything in Desktop could send pseudo data to a provider other than Groq (auxiliary tasks, titles, fallbacks, bot messaging, voice); and whether the approval popup works with Desktop as the face.
- No Hermes config changes during the evaluation. Any fix is proposed as an exact diff, with a backup, for approval.
- **Done when:** each question has a measured answer, and there is a recommendation (Desktop, with any profile changes listed, or an own face), decided by criteria written down before measuring.
- **Result (2026-09-28): Hermes Desktop is ruled out as the face.** Desktop can run the `pseudo` profile, but:
  - every Desktop session gets 12 Desktop-only tools, and one of them, `read_window_below`, returns the raw title of the window behind Desktop, skipping blocked apps and the redactor. No profile setting removes it (accepted as a hard failure);
  - a Desktop question would cost about 16-17K input tokens per call, and Groq allows 8K per minute;
  - auxiliary side-calls can fall back to Nous, whose login every profile inherits from the root.
  These findings led to D15. The `pseudo` profile was hardened (Pseudo's tools only, no auto-titles, no Bot Mode protocol), and its `pseudo_hands` server is now **disabled** (`enabled: false`), so no Pseudo data reaches Hermes until the profile is retired.

### M14: pseudo_brain, Pseudo's own loop
- `pseudo_brain/`: the M3 loop grown into Pseudo's brain (D15). It is an MCP client of `pseudo_hands` (the same stdio server Hermes used) and talks to Groq through the OpenAI-compatible API (D10).
- Groq only: no fallback provider and no hidden side-calls. A 429 is shown to the user, with the wait, and retried visibly; a failed turn is reported as a failure, never as an answer.
- Session history: kept during a conversation and saved locally, so a session can be continued.
- Terminal interface first.
- **Done when:** asked about a fake window, `pseudo_brain` calls `pseudo_hands` over MCP and answers; a 429 is shown and handled visibly; a saved session continues; all verified with fake data and counts only.

### M15: Pseudo's own face
- A React desktop window (Tauri or Electron, chosen in M15's plan) that talks to `pseudo_brain` through a local server. The window only displays; all logic stays in `pseudo_brain` and `pseudo_hands` (D11).
- **Done when:** the M14 checks pass through the window, and `focus_window` still asks through the native approval popup (D13).

## 12. Backlog

Found while building; not scheduled. Each needs a plan and approval before work starts.

- **Thinner first reads.** A freshly opened Chromium/Electron window's first read is thinner than later ones (M12: Obsidian gave 65 content chars on its first read vs 290 warm in M11). M12's retry only fires when a read fails or finds nothing inside the window, so a thin-but-not-empty first read isn't retried.
- **Depth limit misses deep apps.** The UI tree walk stops at depth 12, which misses most of the content in deeply nested apps like Claude desktop (30 controls at depth 12 vs 109 at depth 30).
- **OCR revisit: DaVinci Resolve.** In M11 it exposed only 44 content chars (53 controls), just above the 40-char line. Revisit OCR if Pseudo needs to read Resolve (or games).
