# pseudo_brain

Pseudo's own brain (D15, M14): the Phase 1 agent loop grown up. It is an MCP client of
`pseudo_hands`, talks only to the providers in its allowlist (`providers.toml`, D16, M16),
and keeps a trimmed session history.

```
python -m pseudo_brain                    a new session on the default provider (Groq)
python -m pseudo_brain --provider local   private mode: Ollama on this laptop; nothing leaves it
python -m pseudo_brain --continue         continue the latest saved session, on its own provider
```

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
  hands.py         MCP client of pseudo_hands over stdio; tools discovered at startup
  session.py       whole-turn history, one provider per session, trimmed per request;
                   saves your messages + answers only
  loop.py          SYSTEM_PROMPT + run_turn(): the loop; reports events, never prints
  terminal.py      the terminal interface (the only file that prints)
  __main__.py      `python -m pseudo_brain`
```

The rules: every privacy and approval decision stays in `pseudo_hands` core (D6, D13).
Tool results are kept in memory only, never printed or saved. What you type is sent to
the current provider as typed (L8). A session keeps one provider for life, and private
mode never falls back to the cloud. A failure is always reported as a failure, never as
an answer.
