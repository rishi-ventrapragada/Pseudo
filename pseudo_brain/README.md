# pseudo_brain

Pseudo's own brain (D15, M14): the Phase 1 agent loop grown up. It is an MCP client of
`pseudo_hands`, talks only to Groq, and keeps a trimmed session history.

```
python -m pseudo_brain               start a new session
python -m pseudo_brain --continue    continue the latest saved session
```

```
pseudo_brain/
  model.py      Groq (AsyncOpenAI), visible 429 waits, honest failures (ModelFailure)
  hands.py      MCP client of pseudo_hands over stdio; tools discovered at startup
  session.py    whole-turn history, trimmed per request; saves your messages + answers only
  loop.py       SYSTEM_PROMPT + run_turn(): the loop; reports events, never prints
  terminal.py   the terminal interface (the only file that prints)
  __main__.py   `python -m pseudo_brain`
```

The rules: every privacy and approval decision stays in `pseudo_hands` core (D6, D13).
Tool results are kept in memory only, never printed or saved. What you type is sent to
Groq as typed (L8). A failure is always reported as a failure, never as an answer.
