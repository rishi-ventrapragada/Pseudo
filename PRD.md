# Pseudo: Product Requirements Document

Owner: Sai Rishi Ventrapragada
Repo: https://github.com/rishi-ventrapragada/Pseudo
Status: Phase 1 (Foundations) - not started
Last updated: 2026-09-27

## 1. What Pseudo is

Pseudo is a personal, privacy-first AI desktop assistant for Windows. The long-term goal is an all-in-one agent that can:

1. Write and edit code on request (like Claude Code).
2. Look at the screen, understand what is going on, and answer questions about it.
3. Automate tasks the owner would otherwise do by hand (scripts first, GUI control as fallback).
4. Remember facts about the owner and past tasks, save successful runs as reusable routines, and run scheduled jobs.

The name is a nod to pseudonymization: Pseudo's defining feature is that screen content is understood and redacted locally before anything reaches a cloud model.

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

- **Brain:** Hermes Agent (Nous Research, open source, already installed on the owner's machine) handles reasoning, memory, skills, scheduling, and coding.
- **Pseudo Hands:** an MCP server exposing Windows tools (window list, UI Automation tree, local OCR, click/type) with a local privacy/redaction layer and an approval gate for risky actions.
- **Pseudo Face:** a resizable always-on-top overlay plus local voice (wake word, speech-to-text, text-to-speech).

See ARCHITECTURE.md. These later phases may change once the owner understands the foundations. Do not build any of them in Phase 1.

## 5. Phase plan

| Phase | Name | Outcome |
|---|---|---|
| **1** | **Foundations (current)** | Owner understands LLM APIs, tool calling, and the agent loop by building a mini agent from scratch. |
| 2 | First MCP server | `pseudo_hands` with `list_open_windows`, plugged into Hermes. |
| 3 | Reading and acting | UI Automation tree reader, `focus_window`, approval gate. |
| 4 | Privacy layer | Local OCR + redaction (Presidio) + blocked-apps list. |
| 5 | The face | Resizable overlay, then voice. |

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

## 7. Out of scope for Phase 1

MCP, Hermes integration, screen reading, OCR, UI automation, voice, overlay, memory database, scheduling, local models, any GUI.
