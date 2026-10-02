"""Tests for M24: the memory vault's sandbox (D23). Pseudo only creates and reads plain notes, inside ONE folder.

The tricks are the M3 sandbox's: links that lead outside (symlinks, junctions, hard links), files that
aren't notes, and names taken from input. `outside` holds a fake secret that must never come back.
"""

import os
import subprocess
from pathlib import Path

import pytest

from pseudo_hands.core import memory, redactor
from pseudo_hands.core.memory import NOT_SAVED, SAVED, save_memory
from pseudo_hands.core.memory_search import search_memories

QUESTION = "why did the vercel deploy fail"
SECRET = "Vercel deploy failed: the fake secret ZEBRA-4417 was in the wrong place."


@pytest.fixture(autouse=True)
def empty_terms(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    terms = tmp_path / "redaction_terms.txt"
    terms.write_text("# no terms\n", encoding="utf-8")
    monkeypatch.setattr(redactor, "TERMS_FILE", terms)


@pytest.fixture
def outside(tmp_path: Path) -> Path:
    """A folder NEXT TO the vault, holding a note-shaped secret."""
    folder = tmp_path / "outside"
    folder.mkdir()
    (folder / "secret.md").write_text(f"## Question\nVercel deploy\n## Answer\n{SECRET}\n", encoding="utf-8")
    return folder


def make_link(kind: str, link: Path, target: Path) -> None:
    """Create a symlink / junction / hard link, or skip the test if Windows won't allow it."""
    try:
        if kind == "symlink":
            link.symlink_to(target, target_is_directory=target.is_dir())
        elif kind == "junction":
            subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], check=True, capture_output=True)
        else:
            os.link(target, link)
    except (OSError, subprocess.CalledProcessError) as error:
        pytest.skip(f"can't create a {kind} here: {error}")


def save() -> dict:
    return save_memory("Why did the Vercel deploy fail?", "A missing variable.", [], "groq", "m", "s")


def nothing_found() -> bool:
    found = search_memories(QUESTION)
    return found["memories"] == [] and "ZEBRA" not in str(found)


def test_control_the_same_note_as_a_plain_file_inside_is_found(temp_vault: Path, outside: Path) -> None:
    """Without this, every "nothing found" below could pass just because the note scores too low."""
    temp_vault.mkdir(parents=True)
    (temp_vault / "plain.md").write_bytes((outside / "secret.md").read_bytes())
    assert "ZEBRA" in str(search_memories(QUESTION)["memories"])


@pytest.mark.parametrize("kind", ["symlink", "junction"])
def test_a_linked_vault_folder_is_refused(popup_yes, temp_vault: Path, outside: Path, kind: str) -> None:
    temp_vault.parent.mkdir(parents=True)
    make_link(kind, temp_vault, outside)
    assert save()["status"] == NOT_SAVED
    assert sorted(p.name for p in outside.iterdir()) == ["secret.md"]  # nothing written outside
    assert nothing_found()


@pytest.mark.parametrize("kind", ["symlink", "hard link"])
def test_a_linked_note_is_skipped(temp_vault: Path, outside: Path, kind: str) -> None:
    temp_vault.mkdir(parents=True)
    make_link(kind, temp_vault / "link.md", outside / "secret.md")
    assert nothing_found()


def test_files_that_are_not_notes_are_ignored(temp_vault: Path) -> None:
    (temp_vault / ".obsidian").mkdir(parents=True)
    (temp_vault / ".obsidian" / "workspace.md").write_text(SECRET, encoding="utf-8")  # in a subfolder
    (temp_vault / "sub").mkdir()
    (temp_vault / "sub" / "deep.md").write_text(SECRET, encoding="utf-8")
    (temp_vault / "secret.txt").write_text(SECRET, encoding="utf-8")  # not .md
    assert nothing_found()


@pytest.mark.parametrize("content", [SECRET + " pad" * 6000, b"\xff\xfe Vercel deploy failed \x81"])
def test_oversized_or_unreadable_notes_are_skipped(temp_vault: Path, content) -> None:
    temp_vault.mkdir(parents=True)
    path = temp_vault / "odd.md"
    path.write_bytes(content if isinstance(content, bytes) else content.encode("utf-8"))
    assert nothing_found()


def test_a_save_writes_only_a_new_timestamped_note_inside_the_vault(popup_yes, temp_vault: Path, tmp_path: Path) -> None:
    before = {p for p in tmp_path.rglob("*")}
    results = [save_memory("../../outside/evil.md", "a.md\\..\\..\\x", ["../tool"], "../p", "m", "../s") for _ in range(3)]
    assert all(r["status"] == SAVED for r in results)
    names = {r["note"] for r in results}
    assert len(names) == 3 and all(".." not in n and "evil" not in n for n in names)  # never overwritten
    created = {p for p in tmp_path.rglob("*")} - before
    assert {p for p in created if p.is_file()} == {temp_vault / n for n in names}


def test_the_vault_is_under_local_app_data_not_a_synced_folder() -> None:
    real = Path(os.environ["LOCALAPPDATA"]) / "Pseudo" / "memory"
    assert memory.MEMORY_DIR == real and "OneDrive" not in str(real)
