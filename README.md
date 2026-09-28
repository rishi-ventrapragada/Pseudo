# Pseudo

A personal, privacy-first AI desktop assistant for Windows. Screen content will be understood and redacted locally before anything reaches a cloud model.

**Status:** Phases 1-3 complete. Phase 4 (Reading and acting) in progress: M9 and M10 done, M11 next. See [PRD.md](PRD.md) section 5 for the phase plan and section 10 for Phase 4.

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
