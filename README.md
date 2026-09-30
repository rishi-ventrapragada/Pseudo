# Pseudo

A personal, privacy-first AI desktop assistant for Windows. Screen content will be understood and redacted locally before anything reaches a cloud model.

**Status:** Phases 1-4 complete. Phase 5 (Make it usable) in progress: M13 done (Hermes Desktop ruled out; Pseudo gets its own brain, D15), M14 done: try it with `python -m pseudo_brain`. M15 done (providers evaluated, D16), M16 done (providers: allowlist, same-provider fallback, private mode), M17 (own face) next. See [PRD.md](PRD.md) section 5 for the phase plan, section 11 for Phase 5 and section 12 for the backlog.

## Setup (PowerShell)

```powershell
# 1. Create the virtual environment (once)
python -m venv .venv

# 2. Activate it (every new terminal). Your prompt will show (.venv)
.\.venv\Scripts\Activate.ps1

# 3. Install the pinned dependencies
pip install -r requirements.txt

# 4. Make your private config file, then open .env and fill in LLM_API_KEY
Copy-Item .env.example .env

# 5. Check everything is wired up
python playground/00_check_setup.py
```

`.env` is gitignored. Never commit it and never paste its contents anywhere.
