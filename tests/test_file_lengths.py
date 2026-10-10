"""M39: CLAUDE.md's "max 200 lines per file", checked instead of remembered.

Every source file git tracks (Python, the face's JavaScript and TypeScript, and its CSS) must stay at
or under 200 lines, tests included. A long file is split into smaller ones, as in M38 and M39.
"""

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LIMIT = 200
SOURCES = ("*.py", "*.js", "*.mjs", "*.ts", "*.tsx", "*.css")
NOT_YET = {"face/src/styles.css"}  # replaced by the new design later in M39; this line goes with it


def tracked_sources() -> list[str]:
    listed = subprocess.run(["git", "ls-files", "--", *SOURCES], cwd=REPO_ROOT, capture_output=True, text=True, check=True)
    return listed.stdout.split()


def test_found_the_sources() -> None:
    names = tracked_sources()
    assert "pseudo_brain/bridge.py" in names and "face/main.js" in names and "face/src/App.tsx" in names


def test_every_source_file_is_at_most_200_lines() -> None:
    too_long = {}
    for name in tracked_sources():
        if name in NOT_YET:
            continue
        lines = len((REPO_ROOT / name).read_text(encoding="utf-8").splitlines())
        if lines > LIMIT:
            too_long[name] = lines
    assert too_long == {}
