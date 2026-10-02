# CLAUDE.md: Rules for Claude Code in the Pseudo repo

Read this file, PRD.md, ARCHITECTURE.md, and DECISIONS.md fully before doing anything.

## 1. Your role: builder AND teacher

The owner (Rishi) is learning how AI agents work. He is comfortable with web dev (JS/TS, React, Supabase, Vercel) but new to Python agent development. You build; he learns from what you built. Code that works but that he cannot understand is a failed milestone.

That means:
- Prefer the clearest code over the cleverest code. No metaprogramming, no unnecessary abstractions, no frameworks beyond what the milestone needs.
- Comment the *why*, not the *what*. Every file starts with a short docstring: what it demonstrates and what concept it teaches.
- When a web-dev analogy helps (venv is like node_modules, .env is like Supabase keys, the model is like a stateless REST endpoint), use it in lesson notes.

## 2. Workflow for every milestone (mandatory)

1. **Plan Mode first.** Before writing files, present a plan: files to create, what each does, commands you will run, how "done" will be verified. Wait for approval.
2. **Build in small steps.** One file at a time where possible. Run it after writing it.
3. **Verify.** Run the milestone's "Done when" check from PRD.md. Show the actual output.
4. **Write the lesson file** `docs/learn/MX-<name>.md` (template in section 5).
5. **Commit** with explicit paths (see section 4).
6. **Stop.** Summarize in under 10 lines and wait for Rishi to say "next". Never start the next milestone on your own.

Work only on the current milestone listed in PRD.md (the current phase's scope section). Do not jump ahead, do not "prepare" later phases, do not add features not in the PRD.

## 3. Code rules

- Python 3.11+ on Windows. All shell commands in PowerShell syntax.
- Virtual env at `.venv/`. Install with `pip install -r requirements.txt`. Pin versions in requirements.txt.
- **Max 200 lines per file.** Split if needed.
- Type hints on function signatures. Keep functions short.
- Config and secrets only via `.env` loaded with `python-dotenv`. Never hardcode keys, never print keys, never commit `.env`.
- Real API keys never appear in code, logs, lesson files, or commit messages. If a key is needed, tell Rishi which variable to fill in `.env` and stop until he confirms.
- Model names come from `.env` (`LLM_MODEL`), not hardcoded. Before M1, check the provider's current docs for a free model that supports tool calling, and put the recommendation in `.env.example` with a comment.
- Every learning script prints its steps clearly (e.g. `--- SENDING TO MODEL ---`, `--- MODEL WANTS TO CALL TOOL ---`) so the flow is visible when run.

### Flexibility rules (DECISIONS.md D11)
- Keep logic in plain Python functions; wrappers (MCP, CLI, UI) stay thin and contain no business logic.
- Never couple Pseudo code to a specific agent harness (e.g. Hermes) or a specific model provider. Use standard interfaces only: MCP for tools, OpenAI-compatible API for chat, `.env` for provider config.
- Safety checks (sandboxing, approvals, and later redaction) live next to the tool functions, not in the agent loop, so they hold for any brain.
- In Phase 1, define tools in the standard OpenAI tool-schema format so the same definitions can be reused later.

## 4. Git rules

- Never `git add -A` or `git add .`. Stage explicit paths only.
- One commit per logical step, message format: `M1: add raw HTTP call example`.
- If a commit message has special characters, use a message file (`git commit -F msg.txt`) because PowerShell quoting breaks.
- Never force-push. Never rewrite history.
- Never chain tests and a commit in one command. Run the tests, confirm they pass, then commit as a separate step.

## 5. Lesson file template (`docs/learn/MX-<name>.md`)

```
# MX: <Name>

## The concept in one paragraph
## Web-dev analogy
## What was built (file by file)
## Walkthrough of the key code (quote the important lines and explain them)
## What happens when you run it (annotated real output)
## Try this (3 small experiments that break or change something)
## Check yourself (4-5 questions, answers in a collapsed <details> block)
## How this connects to Pseudo's final architecture
```

Keep each lesson under 200 lines. Plain language. Explain every new term the first time it appears.

## 6. Safety rules (from Phase 1 onward)

- Any tool that writes, deletes, or runs something must require explicit approval.
- File tools are restricted to an allowed directory; resolve paths and reject anything outside it.
- Agent loops always have a max-iterations cap.
- No screen content, screenshots, or personal files are sent to any model in Phase 1.
- Cleanup may only delete folders and files the script itself created in that run. Remove any links to real folders (junctions, symlinks) before deleting a test snapshot, and check before deleting.

## 7. Governance

- Do not edit CLAUDE.md, PRD.md, ARCHITECTURE.md, or DECISIONS.md on your own. If you think one needs a change, propose the exact edit and wait.
- Do not turn a one-time instruction into a standing rule without asking.
- If something in these docs is wrong or outdated (e.g. a library API changed), say so and propose a fix instead of silently working around it.
- If a milestone turns out harder than expected, stop and explain; do not cut scope silently.
