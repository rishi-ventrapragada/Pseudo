# pseudo_brain

Pseudo's brain: its own agent loop (DECISIONS.md D15). It takes your question, asks a model, lets the model call `pseudo_hands`' tools, and reports every step.

- **Allowed providers only** (`providers.toml`, D16). Today that's Groq. If a model hits its rate limit, it moves to the same provider's next model, and says so. The old private mode (Ollama on the laptop) is disabled: Pseudo is cloud-only for models (D20).
- **Allowed tools only** (`providers.toml`'s `model_tools`, D29). A model is offered only the tools on that list; Pseudo's own helper tools (memory, the look-at chip, the memory browser) are never offered to a model.
- **Click and type requests go to Claude Code** on your Claude subscription, after a check that nothing else would be billed (D26). A warm Claude Code session is kept for these, and restarted after 6 requests.
- **What you type is sent as typed** (L8); what Pseudo reads from your screen was redacted by `pseudo_hands` first.
- **Chats are saved on the laptop** in `%LOCALAPPDATA%\Pseudo\sessions` (your messages and the answers). Before a question, up to 3 relevant saved memories join it, redacted again.
- **A failure is reported as a failure,** never dressed up as an answer. A question stops after 6 model calls.

```
python -m pseudo_brain                    chat in the terminal (Groq)
python -m pseudo_brain --continue         continue the latest saved chat
```

Pseudo's window (`face/`) starts `python -m pseudo_brain.bridge` itself and talks to it over the child process's stdin and stdout, with no network port (D18).

Every file, with what it does and the milestone that added it: [ARCHITECTURE.md](../ARCHITECTURE.md), section 4.
