# pseudo_hands

Pseudo's senses and hands on Windows. Phase 2 builds it one milestone at a time (see PRD.md section 8).

```
pseudo_hands/
  core/                 plain Python; never imports MCP, Hermes, or a model SDK (DECISIONS.md D11)
    windows.py          list_open_windows(): Windows API -> clean list of dicts        (M4; M12 skips overlays)
    blocked_apps.py     load the blocked list, mask blocked windows (D6)              (M4)
    blocked_apps.txt    the apps YOU consider private; edit freely                    (M4)
    redactor.py         redact(text): Presidio + spaCy, fails closed                  (M7)
    india_recognizers.py  +91 phone, Aadhaar, PAN, UPI, long-number shapes          (M7)
    redaction_terms.txt   your private terms (gitignored; see the .example)         (M7)
    allowed_names.txt   app/site names never masked; no personal names             (M8)
    ui_tree.py          walk one window's UI Automation tree -> raw lines          (M9; M12 skips failing controls)
    active_window.py    read_active_window(): pick, block, redact, cap             (M9; M12 retries once)
    indian_places.txt   Indian states and cities, masked as [LOCATION]             (M9)
    window_ids.py       short ids ("w3") for listed windows, never reused          (M10)
    approval.py         the approval gate: native popup, default no (D13)          (M10)
    focus.py            focus_window(): validate id, block, ask, act               (M10)
  show_windows.py       thin terminal demo: python -m pseudo_hands.show_windows       (M4)
  mcp_server.py         thin MCP server over stdio: python -m pseudo_hands.mcp_server (M5)
  show_redaction.py     thin demo on fake titles: python -m pseudo_hands.show_redaction (M7)
  show_active_window.py  thin demo: python -m pseudo_hands.show_active_window         (M9)
```

The rule: every decision (what counts as a window, what gets masked, failing closed) lives in `core/`. Wrappers such as `show_windows.py`, and the MCP server in M5, only call core functions and pass the result on, so the privacy check holds for any caller.
