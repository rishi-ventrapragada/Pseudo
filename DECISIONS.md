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
Keys live in `.env`, never committed. For `pseudo_brain`, endpoints and model names live in the committed allowlist `pseudo_brain/providers.toml` (D16), so every place Pseudo can send data is reviewed in git. The playground scripts still read `LLM_BASE_URL`, `LLM_API_KEY` and `LLM_MODEL` from `.env`. Code uses the OpenAI-compatible API shape.

### D11. Swappable brain (flexibility principle)
Pseudo is the whole assistant experience; the brain inside it (Hermes today) must be replaceable with minimal changes, including by the owner's own agent loop later. Concretely:
- Pseudo's tools are plain Python functions in a core module with no agent-specific code. MCP is a thin wrapper around them, never the only way to call them.
- Nothing in Pseudo imports or depends on Hermes internals. Pseudo talks to any brain only through standard interfaces: MCP for tools, the OpenAI-compatible chat API for conversation.
- The privacy layer and approval gate live inside Pseudo's tools, not in the brain, so they work no matter which brain is used.
- The Phase 1 agent loop uses the same tool-definition format, so it can later drive Pseudo's real tools directly as an alternative brain.
*Why:* the owner may change direction (own brain, different harness, local model) and doesn't want a rewrite when that happens.

### D12. Hermes Agent as the brain (was L1). SUPERSEDED by D15 (2026-09-28)
Pseudo is the senses, hands, and face; Hermes Agent (already installed) does reasoning, memory, skills, scheduling, and coding. D11 still holds: Hermes reaches Pseudo only through MCP, so it stays replaceable.
*Why:* it is already installed and covers memory, skills and scheduling, so Pseudo can focus on perception, privacy, and actions.
*Would change if:* Hermes works poorly with free models (first real test: M6). It did; see D15.

### D13. Approval prompts are native Windows popups shown by pseudo_hands
Action tools (Phase 4 onward) ask for approval through a native Windows dialog that pseudo_hands itself shows, not through the brain's chat UI or terminal. The gate lives in core next to the tool (D11), so it works with any brain.
*Why:* M6 showed a brain may auto-approve (Hermes one-shot mode) or have no human watching; a gate owned by the brain can't be relied on to exist.
*Would change if:* a standard MCP approval mechanism proves reliable across the brains Pseudo uses.

### D14. No action may touch the approval popup or pseudo_hands' own windows
No Pseudo action tool may ever interact with the approval popup or any other window owned by the pseudo_hands process: not focus, click, type, close, or anything else. The check lives in core next to each action tool (D11), with a test. focus_window enforces it from M10; future click/type tools must do the same. The only exception is the uncommitted scratchpad end-to-end test script, which clicks its own test popup and is never part of Pseudo.
*Why:* a tool that can act on the approval popup lets the assistant approve its own requests, and the gate (D13) would mean nothing.

### D15. Pseudo's brain is its own agent loop (supersedes D12)
Pseudo's brain is its own agent loop in `pseudo_brain/`, grown from the M3 loop and acting as an MCP client of `pseudo_hands`. Hermes stays installed but is no longer Pseudo's brain, and Hermes Desktop is ruled out as Pseudo's face (M13). D11 still holds: `pseudo_hands` stays a plain MCP server that any brain, Hermes included, can use.
*Why (evidence from M6-M13):*
- **Token cost.** A harness resends its system prompt and tool schemas on every call. The slim `pseudo` profile still cost about 3,000-3,600 input tokens per call (M6, M9 tuned), and a Desktop session about 16-17K (M13), against Groq's free 8,000 tokens per minute. The M3 loop used 530-610.
- **The tool_search bridge.** With any MCP tool present, Hermes hid our tool behind `tool_search`/`tool_call` by default, and the model tried to run `ls -la` in a terminal instead (M6).
- **Silent failures.** A failed one-shot turn exits 0, because the error text replaces the answer; only the usage records show it (M6, M9).
- **Hidden provider fallbacks.** Auxiliary side-calls (titles, compression) fall back to OpenRouter or Nous on a Groq capacity error, and every profile inherits the root Nous login, so profile config alone can't keep pseudo data on Groq (M13).
- **Desktop-only tools that bypass redaction.** Hermes Desktop adds 12 tools to every session. One, `read_window_below`, returns the raw title of the window behind Desktop, skipping blocked apps and the redactor, and no profile setting removes it (M13).
*Would change if:* a harness can be pinned to one provider with no fallbacks, sends only the tools it is given, reports failures honestly, and fits the free tier's per-minute budget.

### D16. Allowed providers, each with a privacy note (M15)
`pseudo_brain` uses only the providers on a committed allowlist; anything else is refused.
- **Groq (main):** `openai/gpt-oss-120b`. Redacted screen text leaves the laptop. Groq doesn't train on inputs or outputs (services agreement §4.2).
- **Groq fallback:** `openai/gpt-oss-20b`, used only when the main model returns a 429, and announced before it's used. Groq's limits are per model (measured in M15). Never a fallback to another provider.
- **Private mode (local):** Ollama on this laptop only (`127.0.0.1`), cloud off, model `granite4.1:3b`. Nothing leaves the laptop. Any model name containing "cloud" is refused. If it fails, it says so; it never falls back to the cloud.
- **Claude Code** is not in the allowlist: it's a separate brain that reaches `pseudo_hands` over MCP (D11), launched with only Pseudo's tools (`--strict-mcp-config`, `--tools ""`) on the owner's subscription login, never an API key. Redacted screen text goes to Anthropic under the consumer terms. The owner turned "Help improve Claude" off on 2026-09-30, so Anthropic doesn't train on these chats and keeps them up to 30 days. If that setting is turned back on, Claude Code goes back to fake windows only.
*Why (M15):* `gpt-oss-20b` scored 12/12 and has its own rate-limit budget. `granite4.1:3b` scored 18/18 at about 5 s per read and 31 tokens/s, with no connections outside the laptop. `llama3.2:3b` (10/18), `lfm2.5:8b` (13/18) and two Qwen 4B models (too slow) failed. `qwen3.8-27b` passed (11/12) but is a Preview model that Groq may drop at short notice. Claude Code passed T1, T2 and T4 (6/6) and saw exactly Pseudo's 3 tools.
*Would change if:* a listed model is retired, or a better free model passes the M15 questions.

### D17. pseudo_hands is never configured in the Claude desktop app (M17)
`pseudo_hands` is never configured in the Claude desktop app (M17); Claude is used with Pseudo only through Claude Code with `--strict-mcp-config --tools ""` (D16).
*Why (M17):* the app's device link, switched on by Anthropic-side feature flags, passed `pseudo_hands`' tools to phone, claude.ai and cloud sessions (`+3 local-mcp`), and neither computer use nor the sessions-bridge flag switched it off.
*Would change if:* the app gets a local setting that stops local MCP tools reaching remote sessions, verified with the M17 log check.

## LEANING (revisit after Phase 1)

L1 moved to LOCKED as D12 (2026-09-28).

### L2. Pseudo Hands as an MCP server
Portable across agents. First tool: `list_open_windows`.

### L3. Perception order
UI Automation tree first, local OCR second, local vision model (OmniParser / Florence-2) last. 4GB VRAM limits model size.

### L4. Model tiering
Main brain on a free cloud model; cheap model for auxiliary tasks; fallback only to the next model of the same provider, on a 429, announced (D16).

### L5. Interface
Pseudo's face is our own web UI: a React window, wrapped with Tauri or Electron, that talks to `pseudo_brain` through a local server (M18). Hermes Desktop was ruled out in M13 (D15); M17 first evaluates the Claude desktop app as face and brain. PySide6 is dropped.
Voice via openWakeWord + faster-whisper + Piper, all local. Wake word plus push-to-talk.

### L6. Storage (memory)
Memory is a dedicated, Obsidian-compatible markdown vault: plain `.md` files that Obsidian can open, though Obsidian isn't needed at runtime. It is separate from the owner's personal vault.
- `pseudo_brain` is sandboxed to that vault: paths are resolved and anything outside it is refused, as in the M3 sandbox.
- Memory text is redacted before it is sent to the model (D6).
- Memory writes go through the approval popup at first (D13).
- SQLite only if structured task history is needed later.

### L7. Routines
Saved from a successful run, preferring scripts over recorded clicks.

### L8. What the owner types is sent to the model unredacted
Text the owner types to Pseudo goes to the current provider (D16) as typed, by design: redacting it would break tasks that need the real values, such as a name to search for or a number to fill in. Only screen content is redacted, in `pseudo_hands` core before it leaves the laptop (D6).
*Would change if:* pasted screen content in typed messages turns out to be common enough to need its own check.

## OPEN

- O1. Whether Pseudo's coding mode goes through Hermes or a separate coding agent.
- O2. Remote control from phone (relay pattern like Claude Code Remote Control) and when.
- O3. Which local vision model actually runs acceptably on a GTX 1650.
