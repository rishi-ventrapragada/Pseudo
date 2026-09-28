# pseudo_hands

Pseudo's senses and hands on Windows. Phase 2 builds it one milestone at a time (see PRD.md section 8).

```
pseudo_hands/
  core/                 plain Python; never imports MCP, Hermes, or a model SDK (DECISIONS.md D11)
    windows.py          list_open_windows(): Windows API -> clean list of dicts        (M4)
    blocked_apps.py     load the blocked list, mask blocked windows (D6)              (M4)
    blocked_apps.txt    the apps YOU consider private; edit freely                    (M4)
  show_windows.py       thin terminal demo: python -m pseudo_hands.show_windows       (M4)
  mcp_server.py         thin MCP server over stdio: python -m pseudo_hands.mcp_server (M5)
```

The rule: every decision (what counts as a window, what gets masked, failing closed) lives in `core/`. Wrappers such as `show_windows.py`, and the MCP server in M5, only call core functions and pass the result on, so the privacy check holds for any caller.
