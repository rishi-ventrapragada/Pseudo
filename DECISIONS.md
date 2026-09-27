# Pseudo: Decision Log

Format: each decision has a status (LOCKED, LEANING, OPEN), the reason, and what would change it. Claude Code must not change entries on its own; propose edits instead.

## LOCKED

### D1. Name: Pseudo
For the owner's personal project only (not the team's SIH submission). Nod to pseudonymization.

### D2. Learning-first build
Claude Code builds; the owner learns from each milestone via lesson files before moving on. A milestone isn't done until the owner can explain it.
*Why:* the owner is new to agents and doesn't want to follow a plan he doesn't understand.

### D3. Zero budget
Free model tiers only. No paid APIs.
*Would change if:* the owner decides to spend money later.

### D4. Windows only (for now)
*Why:* it's the owner's only machine; cross-platform abstraction adds work with no benefit yet.

### D5. Python for Pseudo's own code
*Why:* the agent/automation ecosystem (MCP SDK, pywinauto, OCR, Presidio, faster-whisper) is Python-first, and Hermes is Python.

### D6. Privacy Level 2
No screenshots or raw screen content leave the laptop. Perception is local (UI tree, OCR, small local vision), and a local redactor masks personal info before any cloud call. Blocked apps send nothing. When the redactor is unsure, it masks.
Code files go to the cloud only with per-project permission, remembered per folder.
*Why:* free cloud tiers may use inputs for training; the owner does not want his screen in that data.

### D7. Approval required for risky actions
Deleting/overwriting files, sending messages/emails, submitting forms or payments, installing software or running commands.

### D8. Phase 1 = foundations, not MCP
First build a mini agent from scratch (LLM call, tool calling, agent loop) before touching MCP or Hermes.
*Why:* understanding the loop makes everything later readable instead of magic.

### D9. No agent frameworks in Phase 1
Raw `httpx2` and `openai` SDK only.

### D10. Provider-agnostic config
Model endpoint, key, and name live in `.env`. Code uses the OpenAI-compatible API shape.

### D11. Swappable brain (flexibility principle)
Pseudo is the whole assistant experience; the brain inside it (Hermes today) must be replaceable with minimal changes, including by the owner's own agent loop later. Concretely:
- Pseudo's tools are plain Python functions in a core module with no agent-specific code. MCP is a thin wrapper around them, never the only way to call them.
- Nothing in Pseudo imports or depends on Hermes internals. Pseudo talks to any brain only through standard interfaces: MCP for tools, the OpenAI-compatible chat API for conversation.
- The privacy layer and approval gate live inside Pseudo's tools, not in the brain, so they work no matter which brain is used.
- The Phase 1 agent loop uses the same tool-definition format, so it can later drive Pseudo's real tools directly as an alternative brain.
*Why:* the owner may change direction (own brain, different harness, local model) and doesn't want a rewrite when that happens.

## LEANING (revisit after Phase 1)

### L1. Hermes Agent as the brain
Pseudo becomes the senses, hands, and face; Hermes does reasoning, memory, skills, scheduling, coding. Already installed.
*Open question:* how well Hermes works with free models; test before committing.

### L2. Pseudo Hands as an MCP server
Portable across agents. First tool: `list_open_windows`.

### L3. Perception order
UI Automation tree first, local OCR second, local vision model (OmniParser / Florence-2) last. 4GB VRAM limits model size.

### L4. Model tiering
Main brain on a free cloud model; cheap model for auxiliary tasks; fallback chain across providers (Groq, OpenRouter free, Gemini free for non-screen tasks only).

### L5. Interface
Resizable overlay (PySide6) with collapsed / compact / expanded states; voice via openWakeWord + faster-whisper + Piper, all local. Wake word plus push-to-talk.

### L6. Storage
SQLite for memory and routines (may be replaced by Hermes' own memory if L1 holds).

### L7. Routines
Saved from a successful run, preferring scripts over recorded clicks.

## OPEN

- O1. Whether Pseudo's coding mode goes through Hermes or a separate coding agent.
- O2. Remote control from phone (relay pattern like Claude Code Remote Control) and when.
- O3. Which local vision model actually runs acceptably on a GTX 1650.
