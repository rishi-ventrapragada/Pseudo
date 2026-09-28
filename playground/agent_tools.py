"""M3: the agent's hands. Sandboxed file tools, locked inside playground/sandbox/.

What it demonstrates: tools are plain Python functions, and the safety rules
live HERE, inside the tools, not in the agent loop (DECISIONS.md D11). So they
hold no matter which "brain" calls them: our loop, a future MCP server, anything.

The safety layers, checked before anything touches the disk:
  1. resolve_in_sandbox(): a path is judged by where it REALLY ends up.
  2. Names Windows treats specially (CON, NUL, "file:stream", ...) are refused.
  3. Files with extra hard links are refused (their data may live elsewhere).
  4. write_file() asks `approver` first, and the default approver says NO.
"""

import difflib
import json
from collections.abc import Callable
from pathlib import Path

from agent_tool_schemas import TOOL_SCHEMAS

SANDBOX_DIR = Path(__file__).resolve().parent / "sandbox"
MAX_READ_CHARS = 4000  # about 1K tokens, so one read can't eat the 8K tokens/min budget
MAX_WRITE_CHARS = 10_000
WINDOWS_DEVICE_NAMES = {"CON", "PRN", "AUX", "NUL"} | {f"{p}{i}" for p in ("COM", "LPT") for i in range(1, 10)}
ODD_CHARACTERS = set('<>:"|?*') | {chr(code) for code in range(32)}


class ToolError(Exception):
    """A refusal or failure the model should hear about (it becomes "Error: ...")."""


class SandboxError(ToolError):
    """The path would land outside the sandbox, or isn't a plain file name."""


def deny_everything(preview: str) -> bool:
    """The SAFE DEFAULT approver: until a UI plugs in a real one, every write is refused."""
    return False


# Whoever runs the tools swaps this for a real way of asking (03_agent_loop.py
# uses the terminal). The CHECK stays inside write_file(); only the asking changes.
approver: Callable[[str], bool] = deny_everything


def is_odd_windows_name(name: str) -> bool:
    """True for names Windows treats specially: devices (CON, COM1, nul.txt),
    data streams ("notes.md:hidden"), wildcards, and trailing dots or spaces."""
    if name in ("", ".", ".."):
        return False
    if ODD_CHARACTERS & set(name) or name[-1] in ". ":
        return True
    return name.split(".")[0].strip().upper() in WINDOWS_DEVICE_NAMES


def resolve_in_sandbox(path: str | None) -> Path:
    """Turn a path from the model into a real path inside the sandbox, or refuse."""
    raw = "." if path is None else path
    if not isinstance(raw, str):
        raise SandboxError(f"path must be a string, not {type(raw).__name__}")
    if Path(raw).drive and not Path(raw).root:  # "C:notes.md", Windows' confusing drive-relative form
        raise SandboxError(f"{raw!r} is a drive-relative path; use a plain relative path")
    root = SANDBOX_DIR.resolve()
    # resolve() collapses "..", keeps absolute paths absolute, and follows
    # symlinks and junctions to where they REALLY point.
    target = (root / raw).resolve()
    # Compare whole path parts, not text: "sandbox_evil" is NOT inside "sandbox".
    if not target.is_relative_to(root):
        raise SandboxError(f"{raw!r} is outside the sandbox")
    if any(is_odd_windows_name(name) for name in target.relative_to(root).parts):
        raise SandboxError(f"{raw!r} uses a name Windows treats specially")
    return target


def refuse_hard_links(target: Path) -> None:
    """A hard link is one file with two names. If this file has another name, its
    data may live outside the sandbox, and resolve() can't tell, so refuse it."""
    if target.is_file() and target.stat().st_nlink > 1:
        raise SandboxError(f"{target.name!r} has other hard links, so it may live outside the sandbox")


def display(target: Path) -> str:
    """A short name like 'sandbox/notes.md', instead of the full disk path."""
    relative = target.relative_to(SANDBOX_DIR.resolve()).as_posix()
    return "sandbox/" if relative == "." else f"sandbox/{relative}"


def describe_entry(entry: Path) -> str:
    """One line of a folder listing. Links pointing outside are named but not followed."""
    if not entry.resolve().is_relative_to(SANDBOX_DIR.resolve()):
        return f"{entry.name}  (link to outside the sandbox: not accessible)"
    return f"{entry.name}/" if entry.is_dir() else f"{entry.name}  ({entry.stat().st_size} bytes)"


def list_files(path: str | None = None) -> str:
    """List one folder inside the sandbox (not recursive)."""
    folder = resolve_in_sandbox(path)
    if not folder.is_dir():
        raise ToolError(f"{path!r} is not a folder in the sandbox")
    entries = sorted(folder.iterdir(), key=lambda entry: entry.name.lower())
    if not entries:
        return f"{display(folder)} is empty."
    return f"Contents of {display(folder)}:\n" + "\n".join(describe_entry(e) for e in entries)


def read_file(path: str) -> str:
    """Return a text file's contents (cut off after MAX_READ_CHARS)."""
    target = resolve_in_sandbox(path)
    if not target.is_file():
        raise ToolError(f"{path!r} is not a file in the sandbox")
    refuse_hard_links(target)
    try:
        text = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise ToolError(f"{path!r} is not a UTF-8 text file") from None
    if len(text) > MAX_READ_CHARS:
        return text[:MAX_READ_CHARS] + f"\n[cut off: first {MAX_READ_CHARS} of {len(text)} characters]"
    return text or "(the file is empty)"


def count_words(path: str) -> str:
    """Count the words in a text file (read-only, so no approval gate)."""
    target = resolve_in_sandbox(path)
    if not target.is_file():
        raise ToolError(f"{path!r} is not a file in the sandbox")
    refuse_hard_links(target)
    try:
        text = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise ToolError(f"{path!r} is not a UTF-8 text file") from None
    word_count = len(text.split())  # split() with no argument splits on any run of whitespace
    return f"{display(target)} has {word_count} words."


def build_preview(where: str, old: str | None, new: str) -> str:
    """What the human sees before saying yes or no: full text if new, a diff if not."""
    if old is None:
        return f"write_file wants to CREATE {where} ({len(new)} characters):\n{new}"
    diff = difflib.unified_diff(old.splitlines(), new.splitlines(), "now", "proposed", lineterm="")
    changes = "\n".join(diff) or "(no changes: the content is identical)"
    return f"write_file wants to OVERWRITE {where} ({len(old)} -> {len(new)} characters). Changes:\n{changes}"


def write_file(path: str, content: str) -> str:
    """Create or replace a text file in the sandbox, only if the approver says yes."""
    target = resolve_in_sandbox(path)  # 1. where would it land? (may refuse)
    if not isinstance(content, str):  # 2. is it a sane write?
        raise ToolError("content must be a string")
    if len(content) > MAX_WRITE_CHARS:
        raise ToolError(f"content is {len(content)} characters; the limit is {MAX_WRITE_CHARS}")
    if target.is_dir():
        raise ToolError(f"{path!r} is a folder, not a file")
    refuse_hard_links(target)
    try:
        old = target.read_text(encoding="utf-8") if target.exists() else None
    except UnicodeDecodeError:
        raise ToolError(f"{path!r} exists and is not UTF-8 text; refusing to replace it") from None

    preview = build_preview(display(target), old, content)  # 3. exactly what would change
    if not approver(preview):  # 4. THE APPROVAL GATE: the human decides
        return f"Denied: the user did not approve writing {path}. Nothing was written."
    target.parent.mkdir(parents=True, exist_ok=True)  # 5. only now touch the disk
    target.write_text(content, encoding="utf-8")
    return f"{'Overwrote' if old is not None else 'Created'} {display(target)} ({len(content)} characters)."


# The name the model asks for -> the Python function we run, plus the parameter
# names each schema allows (anything else the model sends is refused).
TOOL_FUNCTIONS = {"list_files": list_files, "read_file": read_file, "count_words": count_words,
                  "write_file": write_file}
ALLOWED_ARGUMENTS = {s["function"]["name"]: set(s["function"]["parameters"]["properties"]) for s in TOOL_SCHEMAS}


def run_tool(name: str, arguments: str) -> str:
    """The one entry point for any brain: tool name + JSON arguments -> result text.
    Every problem comes back as an "Error: ..." string the model can read."""
    function = TOOL_FUNCTIONS.get(name)
    if function is None:
        return f"Error: there is no tool called {name!r}."
    try:
        kwargs = json.loads(arguments or "{}")
    except json.JSONDecodeError as error:
        return f"Error: the arguments were not valid JSON ({error})."
    if not isinstance(kwargs, dict):
        return "Error: the arguments must be a JSON object."
    unknown = sorted(set(kwargs) - ALLOWED_ARGUMENTS[name])
    if unknown:  # e.g. a sneaky {"root": "C:/"}: only the schema's own parameters get through
        return f"Error: unknown argument(s) {unknown} for {name}."
    try:
        return function(**kwargs)
    except (ToolError, OSError) as error:
        return f"Error: {error}"
    except TypeError as error:  # e.g. a required argument is missing
        return f"Error: bad arguments for {name}: {error}"
