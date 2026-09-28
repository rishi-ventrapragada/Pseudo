"""Tool behavior tests: the approval gate, reading, listing, the run_tool()
dispatcher, and the schema <-> Python signature contract.

What it demonstrates: every safety promise in agent_tools.py is checked by a
test, so breaking one (even by accident, even months later) turns a test red.
"""

import inspect
from pathlib import Path

import pytest

import agent_tools
from agent_tool_schemas import TOOL_SCHEMAS
from agent_tools import ToolError, SandboxError, count_words, list_files, read_file, run_tool, write_file


# ---------- the approval gate ----------

def test_default_approver_denies_every_write(sandbox: Path) -> None:
    # No fixture swapped the approver, so this is the real default: deny_everything.
    result = write_file("notes.md", "hello")
    assert result.startswith("Denied") and not (sandbox / "notes.md").exists()


def test_approved_write_creates_the_file_and_its_folders(sandbox: Path, say_yes) -> None:
    result = write_file("drafts/notes.md", "hello")
    assert result.startswith("Created")
    assert (sandbox / "drafts" / "notes.md").read_text(encoding="utf-8") == "hello"
    assert "CREATE sandbox/drafts/notes.md" in say_yes.previews[0]
    assert "hello" in say_yes.previews[0]


def test_denied_write_changes_nothing(sandbox: Path, say_no) -> None:
    (sandbox / "notes.md").write_text("original", encoding="utf-8")
    assert write_file("notes.md", "replaced").startswith("Denied")
    assert (sandbox / "notes.md").read_text(encoding="utf-8") == "original"


def test_overwrite_preview_shows_a_diff(sandbox: Path, say_yes) -> None:
    (sandbox / "notes.md").write_text("1. tip one\n", encoding="utf-8")
    assert write_file("notes.md", "1. tip one\n2. tip two\n").startswith("Overwrote")
    preview = say_yes.previews[0]
    assert "OVERWRITE sandbox/notes.md" in preview and "+2. tip two" in preview


def test_bad_writes_are_refused_before_asking(sandbox: Path, say_yes) -> None:
    (sandbox / "folder").mkdir()
    (sandbox / "photo.bin").write_bytes(b"\xff\xfe\x00binary")
    for path, content in [("big.md", "x" * (agent_tools.MAX_WRITE_CHARS + 1)),
                          ("folder", "x"), ("photo.bin", "text")]:
        with pytest.raises(ToolError):
            write_file(path, content)
    assert say_yes.previews == []


# ---------- reading and listing ----------

def test_read_file_returns_the_text(sandbox: Path) -> None:
    (sandbox / "notes.md").write_text("# Tips\n1. Sleep", encoding="utf-8")
    assert read_file("notes.md") == "# Tips\n1. Sleep"


def test_read_file_cuts_off_long_files(sandbox: Path) -> None:
    (sandbox / "long.md").write_text("a" * 5000, encoding="utf-8")
    text = read_file("long.md")
    assert text.startswith("a" * agent_tools.MAX_READ_CHARS) and "[cut off" in text


@pytest.mark.parametrize("path", ["missing.md", "folder", "photo.bin"])
def test_read_file_refuses_non_text(sandbox: Path, path: str) -> None:
    (sandbox / "folder").mkdir()
    (sandbox / "photo.bin").write_bytes(b"\xff\xfe\x00binary")
    with pytest.raises(ToolError):
        read_file(path)


def test_list_files_shows_folders_and_sizes(sandbox: Path) -> None:
    (sandbox / "drafts").mkdir()
    (sandbox / "notes.md").write_text("12345", encoding="utf-8")
    assert list_files() == "Contents of sandbox/:\ndrafts/\nnotes.md  (5 bytes)"
    assert list_files("drafts") == "sandbox/drafts is empty."
    with pytest.raises(ToolError):
        list_files("notes.md")  # a file, not a folder


# ---------- count_words ----------

def test_count_words_counts_across_any_whitespace(sandbox: Path) -> None:
    (sandbox / "notes.md").write_text("# Tips\n1. Sleep  well\n\n\tdrink water", encoding="utf-8")
    assert count_words("notes.md") == "sandbox/notes.md has 7 words."


def test_count_words_refuses_paths_outside_the_sandbox(sandbox: Path, outside: Path) -> None:
    for path in ["../outside/secret.txt", str(outside / "secret.txt")]:
        with pytest.raises(SandboxError):
            count_words(path)


def test_count_words_handles_a_missing_file(sandbox: Path) -> None:
    with pytest.raises(ToolError, match="not a file"):
        count_words("missing.md")
    assert run_tool("count_words", '{"path": "missing.md"}').startswith("Error:")


# ---------- run_tool(): the dispatcher every brain goes through ----------

@pytest.mark.parametrize("name, arguments, expected", [
    ("delete_everything", "{}", "no tool called"),
    ("read_file", "not json", "not valid JSON"),
    ("read_file", "[1, 2]", "must be a JSON object"),
    ("read_file", '{"path": "a.md", "root": "C:/"}', "unknown argument"),
    ("write_file", '{"path": "a.md"}', "bad arguments"),  # "content" is missing
    ("read_file", '{"path": 42}', "must be a string"),
    ("read_file", '{"path": "../outside.txt"}', "outside the sandbox"),
])
def test_run_tool_turns_problems_into_error_text(sandbox: Path, name: str, arguments: str,
                                                 expected: str) -> None:
    result = run_tool(name, arguments)
    assert result.startswith("Error:") and expected in result


def test_run_tool_accepts_null_for_optional_arguments(sandbox: Path) -> None:
    # The M2 bug in reverse: the model sends null for "no folder", and that must work.
    assert run_tool("list_files", '{"path": null}') == "sandbox/ is empty."
    assert run_tool("list_files", "{}") == "sandbox/ is empty."


# ---------- the schema <-> signature contract (the M2 null-timezone lesson) ----------

@pytest.mark.parametrize("schema", TOOL_SCHEMAS, ids=lambda s: s["function"]["name"])
def test_schema_matches_the_python_signature(schema: dict) -> None:
    spec = schema["function"]
    parameters = inspect.signature(agent_tools.TOOL_FUNCTIONS[spec["name"]]).parameters
    properties = spec["parameters"]["properties"]
    assert set(properties) == set(parameters)
    assert spec["parameters"]["additionalProperties"] is False
    required = {name for name, p in parameters.items() if p.default is inspect.Parameter.empty}
    assert set(spec["parameters"]["required"]) == required
    for name, param in parameters.items():
        types = properties[name]["type"]
        allows_null = "null" in (types if isinstance(types, list) else [types])
        assert allows_null == (param.default is None), f"{spec['name']}.{name}: schema vs default"
