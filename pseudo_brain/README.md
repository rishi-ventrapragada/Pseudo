# pseudo_brain

Pseudo's own brain (D15, M14): the Phase 1 agent loop grown up. It is an MCP client of
`pseudo_hands`, talks only to the providers in its allowlist (`providers.toml`, D16, M16),
and keeps a trimmed session history.

```
python -m pseudo_brain                    a new session on the default provider (Groq)
python -m pseudo_brain --provider local   private mode: Ollama on this laptop; nothing leaves it
python -m pseudo_brain --continue         continue the latest saved session, on its own provider
```

The face (`face/`, M18) starts `python -m pseudo_brain.bridge` itself; see the main README.

In the chat: `/provider` lists the allowed providers with their privacy notes, `/provider <id>`
switches (and starts a new session), `/new` starts a fresh session, `/quit` quits.

```
pseudo_brain/
  providers.toml   the allowlist (D16): URLs, key VARIABLE names, models, privacy notes
  providers.py     loads and checks the allowlist; refuses everything else
  model.py         one provider (AsyncOpenAI): a 429 moves to the same provider's next model,
                   then waits visibly; honest failures (ModelFailure)
  local_server.py  private mode's own server: started on /provider local, 127.0.0.1 only,
                   cloud-off checked, stopped when pseudo_brain exits
  hands.py         MCP client of pseudo_hands over stdio; tools discovered at startup;
                   the two memory tools are hidden from the model (M24)
  session.py       whole-turn history, one provider per session, trimmed per request;
                   saves your messages + answers only
  loop.py          SYSTEM_PROMPT + run_turn(): the loop; reports events, never prints
  chat.py          one conversation, shared by the terminal and the face: provider, session,
                   switching (closes the old provider's connections), servers to stop (M18);
                   memory: search before each question, offer each answered task after (M24)
  terminal.py      the terminal interface (the only file that prints)
  bridge.py        the face's interface: JSON lines over stdin/stdout, no port (D18, M18)
  __main__.py      `python -m pseudo_brain`
```

The rules: every privacy and approval decision stays in `pseudo_hands` core (D6, D13).
Tool results are kept in memory only, never printed or saved. What you type is sent to
the current provider as typed (L8). A session keeps one provider for life, and private
mode never falls back to the cloud. A failure is always reported as a failure, never as
an answer.

Memory (M24, D23): before each question Pseudo finds up to 3 relevant past tasks (redacted,
1,400 characters at most) and adds them to that question only. After each ANSWERED question it
offers the task to memory, and `pseudo_hands` asks you in the approval popup first. Notes live in
`%LOCALAPPDATA%\Pseudo\memory\tasks`; open `%LOCALAPPDATA%\Pseudo\memory` in Obsidian to view, edit or delete them.
