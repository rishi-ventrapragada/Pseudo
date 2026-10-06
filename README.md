# Pseudo

A personal, privacy-first AI desktop assistant for Windows. Screen content will be understood and redacted locally before anything reaches a cloud model.

**Status:** Phases 1-4 complete. Phase 5 (Make it usable) in progress: M13 done (Hermes Desktop ruled out; Pseudo gets its own brain, D15), M14 done: try it with `python -m pseudo_brain`. M15 done (providers evaluated, D16), M16 done (providers: allowlist, same-provider fallback, private mode), M17 done (Claude desktop app ruled out, D17), M18 done: Pseudo has its own window (see below). Phase 6 (Memory): M23 done (memory search evaluated, D23), M24 done: Pseudo remembers answered tasks, with your approval (see below). Phase 7 (Voice): M25 done (voice evaluated, D24), M26 done: talk to Pseudo and hear it answer (see below). Phase 8 (Click and type control): M27 done (click and type evaluated, D25), M28 done: Pseudo can click and type, behind the approval popup (see below). M29 done (only Claude through Claude Code passed the action questions, D26), M30 done: action requests go to Claude Code (see below). M31 done (a warm Claude Code session, restarted every 6 requests, halves the wait for the popup; measured, not built yet). M32 done: one Claude Code session stays open for action requests (about 11 s to the popup instead of 17), with a switch in the window to turn it off. P8-fix done (`focus_window` refuses assistant apps, which get no window id). Phase 9 (Daily-use polish) planned; M33 (how to package Pseudo.exe, evaluate first) in progress. See [PRD.md](PRD.md) section 5 for the phase plan, section 11 for Phase 5, section 12 for Phase 6, section 13 for Phase 7, section 14 for Phase 8, section 15 for Phase 9 and section 16 for the backlog.

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

## Voice (M26)

In the face, click **Start talking** (or hold **Ctrl+Space**) and speak. Click again (or let go) when you
have finished; recording stops by itself after 30 seconds. What you said appears in the input box: read
it, fix it if needed, and press Enter. Nothing you say is ever sent as a question by itself.

- Your recording goes to Groq's `whisper-large-v3` (the provider your questions already go to) straight
  from memory, and is never saved. A silent recording never leaves the laptop. Private mode has no voice input.
- Answers are read aloud on this laptop with Windows' Ravi voice (English (India)). Untick **Speak answers**
  to mute (the face remembers it); **Stop speaking** stops the current answer.
- Needs the English (India) voice pack (Settings > Time & language > Speech > Add voices), and for your real
  microphone, Windows' microphone access for desktop apps (Settings > Privacy & security > Microphone).
- Groq keeps API data only in troubleshooting or abuse logs, for up to 30 days. Zero Data Retention, in
  Groq's console under Data Controls, turns that off.

## Click and type (M28)

Ask Pseudo to act on the window you were on ("tick Send me reminders", "type 'Design review' into Subject"). It works through Windows' accessibility interface, never your mouse or keyboard, and every action asks in the approval popup first (default no). The popup shows the app, window, control and action as Windows reports them, plus the exact text to type. At most 4 action popups every 2 minutes.

- Password fields, disabled controls, blocked apps, assistant apps and Pseudo's own windows are refused before any popup.
- Text containing a mask like [PERSON] is refused: type that value yourself.
- The popup shows names as the app reports them. A page can label a delete button "Cancel", so read what the popup says will happen.
- VS Code's and Obsidian's editors, and Obsidian's file list, can't be acted on yet.

### Who answers an action request (M30)

A request to act ("tick...", "type...", "choose...") goes to Claude Code on your Claude subscription, because no free Groq model passed M29's action questions. Everything else stays on Groq. Every answer in the face says which one answered.

- Set it up once: put your Claude account's email in `.env` as `CLAUDE_CODE_ACCOUNT` (see `.env.example`). It is compared, never printed or sent.
- Before every action request Pseudo checks that Claude Code will use that subscription login and nothing else (no API key, no other provider). If the check isn't clean, or Claude Code isn't installed, Pseudo says so and does nothing; it never falls back to Groq.
- Claude Code gets only three of Pseudo's tools (list windows, read the window, act) and none of its own. The privacy rules and the approval popup are the same as for Groq.
- Redacted screen text for these requests goes to Anthropic. In private mode nothing is routed.
- It takes about 16 to 19 seconds to reach the popup.

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
