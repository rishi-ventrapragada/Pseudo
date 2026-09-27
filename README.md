# Pseudo

A personal, privacy-first AI desktop assistant for Windows. Screen content will be understood and redacted locally before anything reaches a cloud model.

Pseudo is a learning project first: each milestone is small and ends with a lesson file in `docs/learn/`.

**Status:** Phase 1 (Foundations). See [PRD.md](PRD.md) section 6 for the current milestone.

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

## Docs

| File | What it is |
|---|---|
| [PRD.md](PRD.md) | What Pseudo is, constraints, phase plan, milestone scope |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Long-term design and the Phase 1 folder structure |
| [DECISIONS.md](DECISIONS.md) | Decision log (locked, leaning, open) |
| [CLAUDE.md](CLAUDE.md) | Rules Claude Code follows in this repo |
| [docs/learn/](docs/learn/) | One lesson file per milestone |
| [docs/journal.md](docs/journal.md) | The owner's own notes |
