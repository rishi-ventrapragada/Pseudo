# M0: Project setup

## The concept in one paragraph

Before any agent code exists, the project needs a floor that doesn't move. Three things make that floor. First, a **virtual environment** (venv): a private folder holding its own copy of the Python **interpreter** (the program that runs `.py` files) and its own **packages** (installed libraries), so this project can't clash with anything else on your laptop. Second, **pinned dependencies**: `requirements.txt` names exact versions (`==1.2.3`), so every install is the same. Third, **config from environment variables**: named values like `LLM_API_KEY` that live outside the code, loaded from a `.env` file. `.gitignore` keeps the venv and the secrets out of git. `00_check_setup.py` checks all three and exits with a clear pass or fail.

## Web-dev analogy

| Python (this repo) | Web dev equivalent |
|---|---|
| `.venv/` | `node_modules/`, except it also contains its own copy of Python itself |
| `.\.venv\Scripts\Activate.ps1` | Puts `.venv\Scripts` first on your **PATH** (the list of folders the shell searches for commands), similar to how `npx` finds `node_modules/.bin` |
| `requirements.txt` with `==` | `package.json` and the lockfile rolled into one |
| `pip install -r requirements.txt` | `npm install` |
| `.env` / `.env.example` | `.env.local` / the "copy me" template in a Next.js repo |
| `python-dotenv` + `os.getenv("X")` | `require('dotenv').config()` + `process.env.X` |
| `sys.exit(1)` | `process.exit(1)`: the shell and CI read this number |

## What was built (file by file)

- **`.gitignore`**: keeps `.venv/`, `.env`, `__pycache__/`, and the contents of `playground/sandbox/` out of git.
- **`requirements.txt`**: one pinned line, `python-dotenv==1.2.3`. Later milestones add their own libraries when they first use them.
- **`.env.example`**: committed template with `LLM_BASE_URL`, `LLM_API_KEY` (placeholder), and `LLM_MODEL`, plus comments on Groq's free limits.
- **`.env`**: your private copy with the real key. Gitignored and never committed.
- **`README.md`**: what Pseudo is, the setup commands, and a map of the docs.
- **`playground/00_check_setup.py`**: the check script. It's the only real code in M0.
- **`playground/sandbox/.gitkeep`, `tests/.gitkeep`**: git doesn't track empty folders, so an empty placeholder file keeps each folder in the repo.
- **`docs/journal.md`**: your notes. Only a heading so far.
- **`pseudo_hands/README.md`**: placeholder for the Phase 2 MCP server.
- **`.venv/`**: created by `python -m venv .venv`. Never committed; anyone can rebuild it from `requirements.txt`.

Side note: when committing, git warns `LF will be replaced by CRLF`. That's git on Windows converting line endings for you, and it's harmless.

## Walkthrough of the key code

**1. Finding the repo root from any folder**
```python
PROJECT_ROOT = Path(__file__).resolve().parent.parent
```
`__file__` is this script's own path. `.parent` goes up to `playground/`, and a second `.parent` goes up to the repo root. It's like `path.join(__dirname, '..')` in Node. Because of this, `.env` is found even if you run the script from another folder.

**2. The venv check**
```python
if sys.prefix == sys.base_prefix:
    return report(False, "not in a venv. Run: .\\.venv\\Scripts\\Activate.ps1")
if Path(sys.prefix).resolve() != VENV_PATH.resolve():
    return report(False, f"in a different venv. Activate {VENV_PATH} instead")
```
`sys.base_prefix` is the Python install on your machine. `sys.prefix` is the environment actually running. They're equal for system Python and differ inside a venv. The second `if` makes sure it's *this project's* venv and not some other project's.

**3. Why the script doesn't just check whether `dotenv` imports**
```python
try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None
```
This guard gives a friendly message on a machine where dotenv isn't installed at all. But the M0 run turned something up: your system Python *already has* python-dotenv 1.2.3 installed globally. So "the import worked" says nothing about whether you're in the venv. That's why check 2 compares prefixes instead of trusting the import.

**4. Loading `.env`**
```python
load_dotenv(ENV_PATH)
```
This reads each `KEY=value` line into `os.environ`, where real environment variables live, and then `os.getenv("LLM_MODEL")` reads it back. Gotcha: by default it **won't overwrite** a variable that's already set in your shell.

**5. Proving the key exists without showing it**
```python
def describe_key(value: str | None) -> tuple[bool, str]:
    if not value:
        return False, "LLM_API_KEY is missing or empty"
    if value == KEY_PLACEHOLDER:
        return False, "LLM_API_KEY is still the placeholder. Put your real key in .env"
    return True, "LLM_API_KEY is set (value hidden)"
```
There are three possible states, and the value is never printed. Terminal output ends up in scrollback, screenshots, logs, and chat transcripts. A script can prove the key exists without revealing it.

**6. Exit codes**
```python
sys.exit(main())
```
`main()` returns 0 when everything passed and 1 when anything failed. In PowerShell, `$LASTEXITCODE` shows it. Scripts and CI use this number to decide whether a step succeeded.

## What happens when you run it (annotated real output)

Passing run, with the venv active:
```
--- CHECK 1: PYTHON VERSION ---
  Version:      3.13.3
  Running from: C:\dev\Pseudo\.venv\Scripts\python.exe      <- the venv's python, not the system one
  [OK] Python 3.11 or newer

--- CHECK 2: VIRTUAL ENVIRONMENT ---
  sys.prefix:      C:\dev\Pseudo\.venv                      <- environment in use
  sys.base_prefix: C:\Users\iicra\AppData\Local\Programs\Python\Python313  <- the install it came from
  [OK] running inside this project's .venv                   <- they differ, so we're in the venv

--- CHECK 3: .env CONFIG ---
  Loaded: C:\dev\Pseudo\.env
  [OK] LLM_BASE_URL = https://api.groq.com/openai/v1         <- not secret, safe to print
  [OK] LLM_MODEL = openai/gpt-oss-120b
  [OK] LLM_API_KEY is set (value hidden)                     <- status only, never the key

=== ALL CHECKS PASSED ===
exit code: 0
```

Failing run with system Python (`python` before activating):
```
  sys.prefix:      C:\Users\iicra\AppData\Local\Programs\Python\Python313
  sys.base_prefix: C:\Users\iicra\AppData\Local\Programs\Python\Python313   <- identical
  [FAIL] not in a venv. Run: .\.venv\Scripts\Activate.ps1
```
Failing run before the real key was pasted in:
```
  [FAIL] LLM_API_KEY is still the placeholder. Put your real key in .env
=== 1 CHECK(S) FAILED ===
exit code: 1
```

## Try this

1. **Leave the venv.** Run `deactivate`, then `python playground/00_check_setup.py`. Check 2 fails. Check 3 still loads `.env`, because your system Python has dotenv installed globally, which shows the import alone proves nothing. Afterwards, run `.\.venv\Scripts\Activate.ps1` to go back.
2. **Hide the config.** Run `Rename-Item .env .env.bak`, rerun the script, and read the fix message. Then check `$LASTEXITCODE` (it should be `1`). Rename it back with `Rename-Item .env.bak .env`.
3. **Swap the model with zero code changes.** In `.env`, set `LLM_MODEL=openai/gpt-oss-20b` and rerun. The printed model changes and no Python file changed. Changing brains is a config edit. Set it back to `openai/gpt-oss-120b` when you're done.

## Check yourself

1. What two things does `.venv` isolate from the rest of your machine?
2. Why is `.env.example` committed but `.env` isn't?
3. Your system Python can import `dotenv` too. So why is "can I import dotenv?" a bad test for "is the venv active?", and what does the script compare instead?
4. Why pin `python-dotenv==1.2.3` instead of writing just `python-dotenv`?
5. The script confirms the key exists without printing it. Where could a printed key end up?

<details>
<summary>Answers</summary>

1. The Python interpreter being used, and the installed packages. Packages installed in the venv don't leak out, and global packages aren't used inside it.
2. `.env.example` is a template with no secrets. It tells anyone cloning the repo which variables they need. `.env` holds the real key, and once a key is committed it's in git history for good, even if you delete the file later.
3. A package can be installed in more than one Python (here, system Python has it too), so a successful import doesn't tell you *which* Python is running. The script compares `sys.prefix` (the environment in use) with `sys.base_prefix` (the base install). If they differ, you're in a venv.
4. Unpinned installs get whatever version is newest that day, so two installs a month apart can behave differently. Pinning makes today's working setup reproducible, just like a lockfile.
5. In terminal scrollback, screenshots, shared logs, CI output, and chat transcripts with an AI. Any of those could leak it.

</details>

## How this connects to Pseudo's final architecture

- **Swappable brain (D10/D11):** `LLM_BASE_URL`, `LLM_API_KEY`, and `LLM_MODEL` are the whole provider config. Moving from Groq to OpenRouter, Hermes' API server, or a local Ollama means editing these three lines, never the code. Experiment 3 showed this in miniature.
- **Privacy habits:** "report the status, never the secret" is the smallest version of the rule behind Phase 4's redaction layer, where sensitive data is described or masked but never sent out.
- **`playground/sandbox/`:** M3's file tools will be locked to this folder, and `.gitignore` already keeps anything the agent writes out of git.
- **`tests/`:** M3's pytest tests go here. **`pseudo_hands/`:** Phase 2's MCP server.
