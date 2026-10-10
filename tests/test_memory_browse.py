"""Tests for M42: the memory browser (core/memory_browse.py). Read-only, redacted again, and no wider than M24's door.

The tricks are the M3/M24 sandbox's: names that are paths, links that lead outside (symlinks, junctions,
hard links), and files that aren't Pseudo's notes. `outside` holds a fake secret that must never come
back, and every file under the test's folder must be byte-for-byte unchanged afterwards.
"""

import json
from pathlib import Path

import pytest
from test_memory_sandbox import make_link

from pseudo_hands.core import memory, memory_browse, redactor
from pseudo_hands.core.memory_browse import NOT_OPENED, list_memories, open_memory

OLD, NEW, TYPED = "2026-09-30-080000-000.md", "2026-10-07-101500-123.md", "2026-10-08-090000-001.md"
SECRET = "ZEBRA-4417"


@pytest.fixture(autouse=True)
def empty_terms(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    terms = tmp_path / "redaction_terms.txt"
    terms.write_text("# no terms\n", encoding="utf-8")
    monkeypatch.setattr(redactor, "TERMS_FILE", terms)
    monkeypatch.setattr(memory_browse, "_titles", {})


def note(date: str, title: str, question: str, answer: str) -> str:
    return f"---\ndate: {date}T10:00:00+0530\nprovider: groq\n---\n# {title}\n## Question\n{question}\n## Answer\n{answer}\n"


@pytest.fixture
def vault(temp_vault: Path, tmp_path: Path) -> Path:
    """Two notes as Pseudo saved them, one typed in Obsidian with a fake name, and a secret outside."""
    temp_vault.mkdir(parents=True)
    (temp_vault / OLD).write_text(note("2026-09-30", "Summarise the release notes", "Summarise the release notes",
                                       "Three fixes."), encoding="utf-8")
    (temp_vault / NEW).write_text(note("2026-10-07", "Read the booking form", "Read the booking form",
                                       "Booked by [PERSON]."), encoding="utf-8")
    (temp_vault / TYPED).write_text(note("2026-10-08", "Call Rahul Verma", "Call Rahul Verma about the notes",
                                         "His number is on the page."), encoding="utf-8")
    (tmp_path / "outside").mkdir()
    (tmp_path / "outside" / "secret.md").write_text(note("2026-10-01", SECRET, SECRET, SECRET), encoding="utf-8")
    return temp_vault


def snapshot(root: Path) -> dict[str, bytes]:
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}


@pytest.fixture
def unchanged(tmp_path: Path, vault: Path):
    before = snapshot(tmp_path)
    yield
    assert snapshot(tmp_path) == before  # read-only: no file anywhere was written


def test_the_list_is_newest_first_with_dates_and_titles(vault: Path, unchanged) -> None:
    found = list_memories()
    assert [(i["name"], i["date"]) for i in found["items"]] == [(TYPED, "2026-10-08"), (NEW, "2026-10-07"),
                                                                 (OLD, "2026-09-30")]
    assert found["items"][1]["title"] == "Read the booking form" and found["note"] == ""


def test_a_name_typed_in_obsidian_is_masked_when_listed_and_opened(vault: Path, unchanged) -> None:
    listed = list_memories()["items"][0]["title"]
    opened = open_memory(TYPED)
    assert "Rahul" not in json.dumps([listed, opened]) and "[PERSON]" in listed and "[PERSON]" in opened["question"]
    assert opened["answer"] == "His number is on the page." and opened["date"] == "2026-10-08"


def test_each_title_is_redacted_once_until_its_note_changes(vault: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(memory_browse, "redact", lambda text: calls.append(text) or text)
    list_memories(), list_memories()
    assert len(calls) == 3
    (vault / OLD).write_text(note("2026-09-30", "Summarise the notes again", "q", "a"), encoding="utf-8")
    list_memories()
    assert calls[-1] == "Summarise the notes again" and len(calls) == 4


def test_only_pseudos_own_note_names_are_listed(vault: Path) -> None:
    for name in ["notes.md", "2026-10-07-101500-123.md.txt", "٢٠٢٦-١٠-٠٧-١٠١٥٠٠-١٢٣.md", "2026-10-07-101500.md"]:
        (vault / name).write_text(note("2026-10-09", SECRET, SECRET, SECRET), encoding="utf-8")
    (vault / ".obsidian").mkdir()
    (vault / ".obsidian" / "2026-10-09-000000-000.md").write_text(SECRET, encoding="utf-8")
    assert SECRET not in json.dumps(list_memories()) and len(list_memories()["items"]) == 3


@pytest.mark.parametrize("name", [
    "..\\outside\\secret.md", "../outside/secret.md", "C:\\Windows\\win.ini", "*", "*.md", "",
    f"{NEW}/x", f"x\\{NEW}", f"{NEW} ", NEW.removesuffix(".md"), "٢٠٢٦-١٠-٠٧-١٠١٥٠٠-١٢٣.md", None, 20261007,
])
def test_a_name_pseudo_does_not_make_is_refused(vault: Path, unchanged, name) -> None:
    opened = open_memory(name)
    assert opened["note"] == "that is not a memory name Pseudo makes" and opened["question"] == ""


@pytest.mark.parametrize("kind", ["symlink", "hard link"])
def test_a_linked_note_is_neither_listed_nor_opened(vault: Path, tmp_path: Path, kind: str) -> None:
    linked = "2026-10-09-120000-000.md"
    make_link(kind, vault / linked, tmp_path / "outside" / "secret.md")
    assert linked not in json.dumps(list_memories()) and open_memory(linked)["note"] == NOT_OPENED
    assert SECRET not in json.dumps([list_memories(), open_memory(linked)])


@pytest.mark.parametrize("kind", ["symlink", "junction"])
def test_a_linked_vault_folder_is_refused(temp_vault: Path, tmp_path: Path, kind: str) -> None:
    (tmp_path / "outside").mkdir()
    (tmp_path / "outside" / NEW).write_text(note("2026-10-07", SECRET, SECRET, SECRET), encoding="utf-8")
    temp_vault.parent.mkdir(parents=True)
    make_link(kind, temp_vault, tmp_path / "outside")
    listed, opened = list_memories(), open_memory(NEW)
    assert listed["items"] == [] and "is a link" in listed["note"] and "is a link" in opened["note"]
    assert SECRET not in json.dumps([listed, opened])


@pytest.mark.parametrize("content", [note("2026-10-09", "big", "big", "x" * 21_000).encode("utf-8"),
                                     b"\xff\xfe not UTF-8 \x81"])
def test_an_oversized_or_unreadable_note_is_skipped(vault: Path, content: bytes) -> None:
    (vault / "2026-10-09-120000-000.md").write_bytes(content)
    assert len(list_memories()["items"]) == 3 and open_memory("2026-10-09-120000-000.md")["note"] == NOT_OPENED


def test_a_folder_named_like_a_note_and_a_missing_note_cannot_be_opened(vault: Path, unchanged) -> None:
    (vault / "2026-10-09-120000-000.md").mkdir()
    assert open_memory("2026-10-09-120000-000.md")["note"] == NOT_OPENED
    assert open_memory("2026-10-10-120000-000.md")["note"] == NOT_OPENED


def test_no_vault_yet_lists_nothing_and_creates_nothing(temp_vault: Path) -> None:
    assert list_memories() == {"items": [], "note": "there is no memory folder yet"} and not temp_vault.exists()
    assert memory.TASKS_DIR == temp_vault
