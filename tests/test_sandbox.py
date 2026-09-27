"""Sandbox escape tests: every trick must be refused, every honest path allowed.

What it demonstrates: a sandbox is only as good as its tests. Each case here is
a real way people break out of "only this folder" rules: ../ tricks, absolute
paths, Windows-only names, and links (symlinks, junctions, hard links) that
make a path inside the folder point at data outside it.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from agent_tools import SandboxError, list_files, resolve_in_sandbox, run_tool

HONEST_PATHS = ["notes.md", "sub/notes.md", "sub/../notes.md", "", ".", None,
                "%2e%2e/x"]  # URL-encoded "..": we never decode, so it's just an odd folder name

DOT_DOT_TRICKS = ["../secret.txt", "..\\secret.txt", "sub/../../secret.txt", "a/b/../../../x",
                  "../sandbox_evil/x"]  # a sibling folder: str.startswith(root) would WRONGLY allow it

ABSOLUTE_PATHS = ["C:\\Windows\\win.ini", "D:\\x", "/etc/passwd", "\\Windows",
                  "\\\\server\\share\\x", "\\\\?\\C:\\Windows"]

ODD_WINDOWS_NAMES = ["CON", "nul", "COM1", "aux.txt",           # devices, not files
                     "notes.md:hidden", "notes.md::$DATA",      # hidden "alternate data streams"
                     "C:secret.txt",                            # drive-relative
                     "notes.md.", "notes.md ", "....//x"]       # trailing dot / space


@pytest.mark.parametrize("path", HONEST_PATHS)
def test_honest_paths_are_allowed(sandbox: Path, path: str | None) -> None:
    assert resolve_in_sandbox(path).is_relative_to(sandbox.resolve())


def test_absolute_path_that_is_really_inside_is_allowed(sandbox: Path) -> None:
    assert resolve_in_sandbox(str(sandbox / "notes.md")) == (sandbox / "notes.md").resolve()


@pytest.mark.parametrize("path", DOT_DOT_TRICKS + ABSOLUTE_PATHS + ODD_WINDOWS_NAMES)
def test_escape_tricks_are_refused(sandbox: Path, path: str) -> None:
    with pytest.raises(SandboxError):
        resolve_in_sandbox(path)


@pytest.mark.parametrize("tool, arguments", [
    ("read_file", {"path": "../outside/secret.txt"}),
    ("list_files", {"path": ".."}),
    ("write_file", {"path": "../outside/new.txt", "content": "sneaky"}),
])
def test_tools_refuse_to_leave_before_asking_anyone(sandbox, outside, say_yes, tool, arguments) -> None:
    result = run_tool(tool, json.dumps(arguments))
    assert result.startswith("Error:") and "OUTSIDE SECRET" not in result
    assert not (outside / "new.txt").exists()
    assert say_yes.previews == []  # refused BEFORE the human was even asked


# ---------- links: a path inside the sandbox that points at data outside it ----------

def make_link(kind: str, link: Path, target: Path) -> None:
    """Create a symlink / junction / hard link, or skip the test if Windows won't allow it."""
    try:
        if kind == "symlink":
            link.symlink_to(target, target_is_directory=target.is_dir())
        elif kind == "junction":
            if sys.platform != "win32":
                pytest.skip("junctions only exist on Windows")
            subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)],
                           check=True, capture_output=True)
        else:
            link.hardlink_to(target)
    except (OSError, subprocess.CalledProcessError) as error:
        pytest.skip(f"this machine won't create a {kind}: {error}")


def test_file_symlink_to_outside_is_refused(sandbox: Path, outside: Path) -> None:
    make_link("symlink", sandbox / "link.txt", outside / "secret.txt")
    result = run_tool("read_file", '{"path": "link.txt"}')
    assert result.startswith("Error:") and "OUTSIDE SECRET" not in result


@pytest.mark.parametrize("kind", ["symlink", "junction"])
def test_folder_link_to_outside_is_refused(sandbox, outside, say_yes, kind) -> None:
    make_link(kind, sandbox / "door", outside)
    read = run_tool("read_file", '{"path": "door/secret.txt"}')
    write = run_tool("write_file", '{"path": "door/new.txt", "content": "sneaky"}')
    assert read.startswith("Error:") and "OUTSIDE SECRET" not in read
    assert write.startswith("Error:") and not (outside / "new.txt").exists()
    assert say_yes.previews == []


def test_hard_link_to_outside_file_is_refused(sandbox, outside, say_yes) -> None:
    make_link("hardlink", sandbox / "twin.txt", outside / "secret.txt")
    assert "OUTSIDE SECRET" not in run_tool("read_file", '{"path": "twin.txt"}')
    assert run_tool("write_file", '{"path": "twin.txt", "content": "changed"}').startswith("Error:")
    assert (outside / "secret.txt").read_text(encoding="utf-8") == "OUTSIDE SECRET"


def test_listing_names_an_outside_link_but_does_not_follow_it(sandbox: Path, outside: Path) -> None:
    make_link("symlink", sandbox / "door", outside)
    listing = list_files()
    assert "door  (link to outside the sandbox: not accessible)" in listing
    assert "secret.txt" not in listing
