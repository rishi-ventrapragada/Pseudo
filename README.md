# Pseudo

A personal, privacy-first AI desktop assistant for Windows. Screen content will be understood and redacted locally before anything reaches a cloud model.

**Status:** Phases 1-4 complete. Phase 5 (Make it usable) in progress: M13 done (Hermes Desktop ruled out; Pseudo gets its own brain, D15), M14 done: try it with `python -m pseudo_brain`. M15 done (providers evaluated, D16), M16 done (providers: allowlist, same-provider fallback, private mode), M17 done (Claude desktop app ruled out, D17), M18 done: Pseudo has its own window (see below). Phase 6 (Memory) in progress: M23 done (memory search evaluated, D23), M24 done: Pseudo remembers answered tasks, with your approval (see below). See [PRD.md](PRD.md) section 5 for the phase plan, section 11 for Phase 5, section 12 for Phase 6 and section 13 for the backlog.

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

## Memory (M24)

After each answered question, Pseudo asks in a popup whether to save it to memory (default no).
A saved task is redacted first and stored as a markdown note in `%LOCALAPPDATA%\Pseudo\memory\tasks`,
on this laptop only. Later questions get up to 3 relevant past tasks, redacted again.
To view, edit or delete notes, open the folder `%LOCALAPPDATA%\Pseudo\memory` as a vault in Obsidian.

## The face: Pseudo's own window (M18)

Needs Node.js (24 or newer) as well as the Python setup above.

```powershell
cd face
npm install   # once: Electron, React and the build tools, into face
ode_modules (about 470 MB)
npm start     # builds the page, opens the window, and starts pseudo_brain as its child process
```

Close the window to quit: it stops `pseudo_brain`, `pseudo_hands` and private mode's Ollama with it.
If `npm start` says "Cannot find module 'electron'", your terminal has `ELECTRON_RUN_AS_NODE` set
(some editors set it): run `Remove-Item Env:ELECTRON_RUN_AS_NODE`, then `npm start` again.
