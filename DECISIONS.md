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
- Exception (D26): `pseudo_brain` may launch Claude Code for action requests.
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
- **Private mode (local):** Ollama on this laptop only (`127.0.0.1`), cloud off, model `granite4.1:3b`. Nothing leaves the laptop. Any model name containing "cloud" is refused. If it fails, it says so; it never falls back to the cloud. **Disabled since 2026-10-01 (P5-perf, D20):** Ollama was removed to free laptop resources. `providers.toml` keeps the entry with `disabled = "<reason>"`, so `/provider local` is refused with that reason. The code stays; re-enabling needs D20 changed first, Ollama reinstalled, and the `disabled` line deleted.
- **Claude Code** is not in the allowlist: it's a separate brain that reaches `pseudo_hands` over MCP (D11), launched with only Pseudo's tools (`--strict-mcp-config`, `--tools ""`) on the owner's subscription login, never an API key. Redacted screen text goes to Anthropic under the consumer terms. The owner turned "Help improve Claude" off on 2026-09-30, so Anthropic doesn't train on these chats and keeps them up to 30 days. If that setting is turned back on, Claude Code goes back to fake windows only.
*Why (M15):* `gpt-oss-20b` scored 12/12 and has its own rate-limit budget. `granite4.1:3b` scored 18/18 at about 5 s per read and 31 tokens/s, with no connections outside the laptop. `llama3.2:3b` (10/18), `lfm2.5:8b` (13/18) and two Qwen 4B models (too slow) failed. `qwen3.8-27b` passed (11/12) but is a Preview model that Groq may drop at short notice. Claude Code passed T1, T2 and T4 (6/6) and saw exactly Pseudo's 3 tools.
*Would change if:* a listed model is retired, or a better free model passes the M15 questions.

### D17. pseudo_hands is never configured in the Claude desktop app (M17)
`pseudo_hands` is never configured in the Claude desktop app (M17); Claude is used with Pseudo only through Claude Code with `--strict-mcp-config --tools ""` (D16).
*Why (M17):* the app's device link, switched on by Anthropic-side feature flags, passed `pseudo_hands`' tools to phone, claude.ai and cloud sessions (`+3 local-mcp`), and neither computer use nor the sessions-bridge flag switched it off.
*Would change if:* the app gets a local setting that stops local MCP tools reaching remote sessions, verified with the M17 log check.

### D18. The face talks to pseudo_brain only through a child-process pipe (M18)
The face talks to `pseudo_brain` only through a child-process pipe (JSON lines over stdin/stdout); nothing in Pseudo's own code listens on a network port; the only listener Pseudo starts is private mode's Ollama, on 127.0.0.1 only (D16).
*Why:* M5 and M17 showed that anything reachable gets reached (M17: local tools passed to remote sessions).
*Would change if:* a second device must talk to Pseudo, which would need its own plan.

### D19. What the redactor treats as personal (M19)
Dates are masked when they could be a birthday (a day and a month, or a year next to a birth word), and so are ages; times, weekdays, relative dates and bare numbers are not. Code-shaped words (capital letters plus digits, like M15 or CS101) are never names. (M29) Neither are Pseudo's own control ids (c169): spaCy guessed some were people, which hid those controls from the model. Presidio's weak vehicle-plate shapes (score below 0.4) are ignored; full plates are masked. Everything else still masks at any confidence (D6).
*Why:* M19 measured 41% of ordinary fake lines over-masked, 11 of 18 spans from spaCy's date guesses.
*Would change if:* a measured case shows real personal info released by one of these rules.

### D20. Pseudo is cloud-only for AI models and services (P5-perf, 2026-10-01)
Pseudo uses AI models and services only in the cloud, through the providers allowed in D16. No local models run on this laptop: no Ollama, and no local language, speech or vision models. The laptop stays free for other work. The redactor is the one exception and stays local (Presidio + spaCy, D6), because it is what protects the data going to the cloud.
Windows' own voices (including optional voice packs such as English (India)) are allowed: they're part of the OS, and M25 measured them at +54 MB with no network use. Windows' speech recognizer isn't used (M25: it failed on accuracy, RAM and privacy).
*Why:* private mode's Ollama took 3.8 GB of disk, and a model runner it left behind held about 6 GB of committed memory for a day (P5-perf). The owner wants the laptop's RAM, GPU and disk for other work.
*Would change if:* the owner gets hardware to spare, or a privacy need arises that only a local model can meet.

### D21. Names the redactor must know (M20)
Common Indian first names and surnames are masked from a committed, owner-editable list (`pseudo_hands/core/indian_names.txt`), matched only when Capitalized or in ALL CAPS. So are initials next to a listed name, and any Capitalized word right before a listed surname. spaCy still masks the names it finds; the list only adds masks. Names that are also common English or everyday words (Sunny, Ram, Raja...) and brand-name surnames (Bose, Tata...) are left out; deity and festival names are kept, so "Durga Puja" is masked, failing closed.
*Why:* M20 measured spaCy's small model catching 61% of fake Indian names in titles (first names alone: 25%), and the medium model needed 205 MB more RAM while still missing more held-out names than the list.
*Limit (M21):* the list only masks the names on it. On fresh held-out names (N4) recall is 57%, the same as spaCy alone, so the name leak is only partly fixed. A rule anchored on the list (M21's rule 4) didn't change that and wasn't shipped. *Lifted by M22 (D22):* a large list from Wikidata raised fresh held-out recall to 99% (N4 and N6).
*Would change if:* a measured model catches the held-out sets as well as the list does, within the laptop's RAM budget (D20).

### D22. A large names list from Wikidata (M22)
Besides the hand list (D21), the redactor masks about 49,000 Indian name words generated from Wikidata (`pseudo_hands/core/indian_names_large.txt`, written by `pseudo_hands/build_names_list.py`): the English labels of people with citizenship India, British Raj or Dominion of India, split into single words, minus titles, the hand list's left-out words and ordinary English words (lowercase entries of the en_GB spelling dictionary). Both lists are required; either one missing or broken fails closed. Names are matched by a set lookup, not a regex. Your own names still go in `indian_names.txt`; the large file is only ever regenerated.
*Why:* on a fresh held-out set (N6), M22 measured recall at 67% with the hand list and 99% with both, for +3 ms per title and +13 MB. Wikidata is CC0, so the list can be committed to a public repo. Rejected: the electoral-roll surname list (research-only terms), `name-dataset` (built from the 2021 Facebook leak), an unattributed Hugging Face list (no provenance). Lok Dhaba's licence couldn't be verified.
*Would change if:* recall on a future held-out set drops, or a source with a verified, redistributable licence covers rare surnames better.

### D23. Memory: a local vault, searched with SQLite FTS5 (M23; was L6)
Pseudo's memory is one markdown note per answered task in `%LOCALAPPDATA%\Pseudo\memory\tasks\` (not synced; Obsidian can open it). Only `pseudo_hands` core touches it, sandboxed to that folder. Notes are redacted before saving and again when found. Every save goes through the approval popup (default no). `pseudo_brain` reaches the vault only through two brain-only MCP tools the model never sees. Relevant memories are found with SQLite FTS5 (Porter stemming, BM25), from an index kept in memory and refreshed by modification time. At most 3 memories, 1,400 characters in all, join a question, as notes rather than instructions. (M24) Word rarity is judged against 150 fake background notes (`memory_background.txt`, never returned), so a young vault scores like the 150 notes M23 tuned the cut-off on.
From L6, still true: the vault is plain `.md` files that Obsidian can open, though Obsidian isn't needed at runtime, and it is separate from the owner's personal vault. Only `pseudo_hands` core touches the vault, sandboxed to it; `pseudo_brain` reaches it only through two brain-only MCP tools.
*Why:* M23 measured FTS5 at 83% Recall@3 on held-out questions (pure-Python BM25: 73%), at 3.3 ms and +2 MB for 1,000 notes. Only the chosen, redacted memories leave the laptop, to the provider already in use. Cloud embeddings would send every note and question to a second company (D6, D16).
*Would change if:* real use shows too many missed paraphrases, or a free embedding provider fits D16.

### D24. Voice: Groq Whisper listens, Windows' voices speak (M25)
Pseudo listens through Groq's `whisper-large-v3` (the same provider as chat, D16) and speaks with Windows' own voices through SAPI (English (India) Heera or Ravi, or Zira; the default is picked in M26); nothing spoken leaves the laptop. Push-to-talk only: the microphone is open only while you hold the button or key, for at most 30 seconds, and audio is never written to disk or saved in sessions or memory. A clip whose loudest 100 ms is below −45 dBFS is never sent. Whisper segments with `no_speech_prob` > 0.6 and `avg_logprob` < −1.0 are dropped. Whisper gets `language="en"` and never a prompt containing personal words. The transcript is treated like typed text (L8): it isn't redacted, and it's shown in the input box before it's sent.
*Why (M25):* on 156 fake clips, `whisper-large-v3` passed every criterion (WER 1.2% clean and 2.5% noisy on Indian voices, 74% of name words, 0.26 s, +8 MB, Groq only). Turbo failed on names (55%) and turned clicks into "Thank you.". Windows' recognizer failed on accuracy (63% WER), RAM (+111 MB) and privacy (it keeps files tuned to the voices it hears), and it's deprecated. Windows' voices passed (first audio in 0.045 s, 4% round-trip errors, no network). Orpheus needs console terms and is a Preview model. Redacting transcripts would hide nothing from Groq and broke 12 of 26 commands.
*Would change if:* Groq retires `whisper-large-v3`, real use shows names misheard too often, or a free cloud voice fits D16 without console terms.

### D25. How Pseudo acts on a window (M27)
Pseudo acts only through UI Automation actions (press, set text, add text, toggle, select, choose, open) on controls in the window you were on, named by short ids that only a fresh read hands out; never by mouse coordinates or keystrokes. Every action asks in the approval popup first (D13), built only from Windows' data (app, window, control type and name, action) plus the exact text to type: one action per popup, at most 4 action popups per 2 minutes, enforced in core. Refused before any popup: password fields, disabled controls, blocked apps, assistant apps, Pseudo's own windows and popup (D14), controls outside the targeted window, and ids whose control changed or is gone. Text is refused if it contains a mask label like [PERSON] (status "contains masked text: ask the user to type it"), is over 300 characters, or contains control or text-direction characters.
*Why (M27):* on fake windows, UI Automation did 15 of 16 actions on Pseudo's own forms and 15 of 18 in Brave, VS Code and Obsidian, at 8 ms median, with no wrong target in 22; mouse and keyboard fallbacks added nothing. All 12 refusal cases were refused. On six injection pages, gpt-oss-120b tried no unrequested action in 24 runs, and picked the right control in 4 of 5 requested ones.
*Limits:* the popup shows control names as the app reports them (a page can label a delete button "Cancel"); VS Code's and Obsidian's editors and Obsidian's file list expose no actions; control names are redacted like screen text, so "Mark as done" can reach the model as "[PERSON] as done".
*Would change if:* real use needs those editors (keyboard typing would need its own evaluation), or a measured case shows a wrong target.

### D26. Action requests may go to Claude Code (M29)
For requests that ask Pseudo to act on a window, `pseudo_brain` may hand the question to Claude Code (`claude -p`, Sonnet) with only Pseudo's tools (`--strict-mcp-config --tools ""`), Pseudo's own system prompt, and the billing check before every launch (D16). `focus_window` is offered only when the message asks to see or switch to a window (the M29 phrase list). Everything else stays on Groq. This is an exception to D11: `pseudo_brain` depends on one harness's command line, while `pseudo_hands` stays a plain MCP server that any brain can use. If the billing check fails or Claude Code is missing, Pseudo says so and doesn't act.
*Why (M29):* on 18 held-out action questions, Claude gave a usable popup 18 times with and without the rule; the best Groq setups gave 16 and each missed another criterion.
*Limits:* it uses the owner's subscription quota; about 19 s to the popup from a cold start; the rule misses "Can I see the test form?".
*Would change if:* a free Groq model passes M29's criteria, or the subscription ends.

## LEANING (revisit after Phase 1)

L1 moved to LOCKED as D12 (2026-09-28).

### L2. Pseudo Hands as an MCP server
Portable across agents. First tool: `list_open_windows`.

### L3. Perception order
UI Automation tree only. No OCR or vision models: none run locally (D20), and screenshots never leave the laptop (D6). A window whose tree is empty can't be read; M11 found that rare (0 of 9 windows and apps). Revisit only if a privacy-safe option fits D20.

### L4. Model tiering
Main brain on a free cloud model; cheap model for auxiliary tasks; fallback only to the next model of the same provider, on a 429, announced (D16).

### L5. Interface
Pseudo's face is our own web UI: a React window in Electron that talks to `pseudo_brain` over a child-process pipe (M18, D18). Hermes Desktop was ruled out in M13 (D15) and the Claude desktop app in M17 (D17). PySide6 is dropped.
Voice (D24, M25): Groq's Whisper listens and Windows' voices speak, push-to-talk only. M25 ruled out a wake word: a local wake model breaks D20, and streaming everything to the cloud breaks privacy. A global hotkey may come later.

L6 moved to LOCKED as D23 (2026-10-02).

### L7. Routines
Saved from a successful run, preferring scripts over recorded clicks.

### L8. What the owner types is sent to the model unredacted
Text the owner types to Pseudo goes to the current provider (D16) as typed, by design: redacting it would break tasks that need the real values, such as a name to search for or a number to fill in. Only screen content is redacted, in `pseudo_hands` core before it leaves the laptop (D6).
*Would change if:* pasted screen content in typed messages turns out to be common enough to need its own check.

## OPEN

- O1. Whether Pseudo's coding mode goes through Hermes or a separate coding agent.
- O2. Remote control from phone (relay pattern like Claude Code Remote Control) and when.
- O3. Closed by D20 (2026-10-01): no local vision models run on this laptop, so which one fits a GTX 1650 no longer matters.
