"""M0 setup check: is this project wired up correctly?

What it demonstrates:
  1. Which Python is running (its version and where it lives on disk).
  2. Whether that Python is this project's virtual environment (.venv)
     or the system-wide install.
  3. Whether config loads from .env, without ever printing the secret key.

Concept it teaches: a project is reproducible when its interpreter, its
packages, and its config are isolated and explicit. Nothing here talks to
a model yet; that starts in M1.

Run it with the venv active:  python playground/00_check_setup.py
"""

import os
import sys
from pathlib import Path

# python-dotenv is installed inside .venv, not in system Python. If the import
# fails, the venv is almost certainly not active, so we report that in plain
# words later instead of crashing here with a traceback.
try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

MIN_PYTHON = (3, 11)

# This file is playground/00_check_setup.py, so parent.parent is the repo root.
# Building paths from __file__ makes the script work from any folder.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
VENV_PATH = PROJECT_ROOT / ".venv"
ENV_PATH = PROJECT_ROOT / ".env"

# Must match the value in .env.example, so we can tell "copied but not filled in".
KEY_PLACEHOLDER = "paste-your-groq-key-here"


def report(ok: bool, message: str) -> bool:
    """Print one OK/FAIL line and pass the result through."""
    print(f"  [{'OK' if ok else 'FAIL'}] {message}")
    return ok


def check_python_version() -> bool:
    print("--- CHECK 1: PYTHON VERSION ---")
    print(f"  Version:      {sys.version.split()[0]}")
    print(f"  Running from: {sys.executable}")
    ok = sys.version_info >= MIN_PYTHON
    return report(ok, f"Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]} or newer")


def check_venv() -> bool:
    print("\n--- CHECK 2: VIRTUAL ENVIRONMENT ---")
    # sys.base_prefix = the Python install the venv was created from.
    # sys.prefix      = the environment actually in use right now.
    # With system Python both point at the same folder; inside a venv they differ.
    print(f"  sys.prefix:      {sys.prefix}")
    print(f"  sys.base_prefix: {sys.base_prefix}")
    if sys.prefix == sys.base_prefix:
        return report(False, "not in a venv. Run: .\\.venv\\Scripts\\Activate.ps1")
    # Being in *a* venv isn't enough; it has to be this project's .venv.
    if Path(sys.prefix).resolve() != VENV_PATH.resolve():
        return report(False, f"in a different venv. Activate {VENV_PATH} instead")
    return report(True, "running inside this project's .venv")


def describe_key(value: str | None) -> tuple[bool, str]:
    """Say whether the key is usable, without ever revealing it."""
    if not value:
        return False, "LLM_API_KEY is missing or empty"
    if value == KEY_PLACEHOLDER:
        return False, "LLM_API_KEY is still the placeholder. Put your real key in .env"
    return True, "LLM_API_KEY is set (value hidden)"


def check_env_file() -> bool:
    print("\n--- CHECK 3: .env CONFIG ---")
    if load_dotenv is None:
        return report(False, "python-dotenv not found. Is the venv active?")
    if not ENV_PATH.is_file():
        return report(False, f"{ENV_PATH} not found. Run: Copy-Item .env.example .env")

    # load_dotenv reads KEY=value lines from the file into os.environ, the same
    # place real environment variables live. By default it does not overwrite
    # a variable that is already set in your shell.
    load_dotenv(ENV_PATH)
    print(f"  Loaded: {ENV_PATH}")

    results = []
    # Base URL and model name are not secrets, so printing them is fine.
    for name in ("LLM_BASE_URL", "LLM_MODEL"):
        value = os.getenv(name)
        results.append(report(bool(value), f"{name} = {value}" if value else f"{name} is missing"))

    # The key IS a secret: only its status is printed, never the value.
    key_ok, key_message = describe_key(os.getenv("LLM_API_KEY"))
    results.append(report(key_ok, key_message))
    return all(results)


def main() -> int:
    print("=== Pseudo M0 setup check ===\n")
    results = [check_python_version(), check_venv(), check_env_file()]
    failed = results.count(False)
    print()
    if failed == 0:
        print("=== ALL CHECKS PASSED ===")
        return 0
    print(f"=== {failed} CHECK(S) FAILED ===")
    return 1


if __name__ == "__main__":
    # The number passed to sys.exit is the exit code: 0 = success, else failure.
    # In PowerShell, read it right after with: $LASTEXITCODE
    sys.exit(main())
