"""Tests for M24: saving tasks to memory and finding them again (pseudo_hands/core/memory*.py, D23).

Everything is FAKE: fake tasks, a temporary vault (conftest's temp_vault), and the popup played by
popup_yes / popup_no. The owner's private terms are replaced by an empty list.
"""

import re
from pathlib import Path

import pytest
from mcp import Client

from pseudo_hands.core import memory, memory_search, redactor
from pseudo_hands.core.memory import NOT_APPROVED, NOT_SAVED, SAVED, save_memory
from pseudo_hands.core.memory_search import INTRO, MAX_CHARS, search_memories
from pseudo_hands.core.redactor import RedactionError
from pseudo_hands.mcp_server import server

VERCEL = ("My Vercel build broke, Rahul Verma said to call +91 98765 43210",
          "The NEXT_PUBLIC_API_URL variable was missing; adding it in the project settings fixed the build.")
NOTE_NAME = re.compile(r"\d{4}-\d{2}-\d{2}-\d{6}-\d{3}\.md")


@pytest.fixture(autouse=True)
def empty_terms(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The owner's real private terms are never read by tests."""
    terms = tmp_path / "redaction_terms.txt"
    terms.write_text("# no terms\n", encoding="utf-8")
    monkeypatch.setattr(redactor, "TERMS_FILE", terms)


def save(question: str = VERCEL[0], answer: str = VERCEL[1], model: str = "openai/gpt-oss-120b") -> dict:
    return save_memory(question, answer, ["read_active_window"], "groq", model, "20261002-120000-001")


def write_note(folder: Path, name: str, question: str, answer: str) -> Path:
    """A note as if you had typed it in Obsidian: nothing redacted."""
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_text(f"---\ndate: 2026-09-01T10:00:00+0530\n---\n# t\n## Question\n{question}\n## Answer\n{answer}\n",
                    encoding="utf-8")
    return path


# ---------- saving ----------

def test_an_approved_save_writes_one_redacted_note(popup_yes, temp_vault: Path) -> None:
    result = save()
    assert result["status"] == SAVED and NOTE_NAME.fullmatch(result["note"])
    text = (temp_vault / result["note"]).read_text(encoding="utf-8")
    assert "[IN_PHONE]" in text and "[PERSON]" in text
    assert not any(secret in text for secret in ("98765", "43210", "Rahul", "Verma"))
    assert "provider: groq\nmodel: openai/gpt-oss-120b\ntools: [read_active_window]\nsession: 20261002-120000-001" in text
    assert [p.name for p in temp_vault.iterdir()] == [result["note"]]


def test_the_popup_shows_the_redacted_note_and_says_no_is_the_default(popup_yes) -> None:
    save()
    (preview,) = popup_yes.previews
    assert "[IN_PHONE]" in preview and "98765" not in preview and "Rahul" not in preview
    assert "Cancel, Esc, the X, or no answer within 20 seconds means NO" in preview


def test_a_denied_save_writes_nothing(popup_no, temp_vault: Path) -> None:
    assert save()["status"] == NOT_APPROVED
    assert not temp_vault.exists() or not any(temp_vault.iterdir())


def test_a_failed_redaction_saves_nothing_and_never_asks(popup_yes, temp_vault: Path, monkeypatch) -> None:
    def broken(text: str) -> str:
        raise RedactionError("fake")
    monkeypatch.setattr(memory, "redact", broken)
    assert save()["status"] == NOT_SAVED and popup_yes.previews == []
    assert not temp_vault.exists()


def test_an_empty_task_is_not_saved(popup_yes) -> None:
    assert save(question="  ")["status"] == NOT_SAVED and popup_yes.previews == []


def test_properties_stay_one_plain_line_each(popup_yes, temp_vault: Path) -> None:
    result = save(model="evil\n---\ninjected: yes")
    properties = (temp_vault / result["note"]).read_text(encoding="utf-8").split("\n---\n")[0]
    assert properties.count("\n") == 5 and "injected:" not in properties


def test_a_long_answer_is_cut(popup_yes, temp_vault: Path) -> None:
    result = save(answer="word " * 1000)
    answer = (temp_vault / result["note"]).read_text(encoding="utf-8").split("## Answer\n")[1]
    assert len(answer) <= memory.MAX_ANSWER_CHARS + 20 and "(cut)" in answer


# ---------- finding ----------

def test_no_vault_yet_means_no_memories() -> None:
    found = search_memories("how did I fix the vercel build")
    assert found["memories"] == [] and found["note"]


def test_a_young_vault_finds_its_one_relevant_note(popup_yes) -> None:
    save()
    found = search_memories("how did I fix the vercel build")
    assert found["intro"] == INTRO and len(found["memories"]) == 1
    assert "NEXT_PUBLIC_API_URL" in found["memories"][0] and found["memories"][0].startswith("- 20")
    assert search_memories("price of gym plans")["memories"] == []  # unrelated: nothing


def test_background_notes_are_never_returned(temp_vault: Path) -> None:
    write_note(temp_vault, "a.md", "Plan the Sankranti trip home", "Leave Friday night by bus.")
    assert search_memories("air fryer sale price")["memories"] == []  # only a background note matches


def test_an_edit_or_a_deletion_counts_at_the_next_question(popup_yes, temp_vault: Path) -> None:
    note = temp_vault / save()["note"]
    assert search_memories("how did I fix the vercel build")["memories"]
    with open(note, "a", encoding="utf-8") as file:
        file.write("Later: it was the CORS setting too.\n")
    assert "CORS" in search_memories("how did I fix the vercel build")["memories"][0]
    note.unlink()
    assert search_memories("how did I fix the vercel build")["memories"] == []


def test_what_you_type_into_a_note_still_goes_out_redacted(temp_vault: Path) -> None:
    write_note(temp_vault, "mine.md", "Why did the Vercel deploy fail?", "Call Priya Sharma on +91 98765 43210 about it.")
    (memory_text,) = search_memories("why did the vercel deploy fail")["memories"]
    assert "98765" not in memory_text and "Priya" not in memory_text and "[IN_PHONE]" in memory_text


def test_at_most_three_memories_within_the_character_cap(temp_vault: Path) -> None:
    for i in range(5):
        write_note(temp_vault, f"n{i}.md", f"Vercel deploy failure number {i}", "Vercel deploy failed again. " * 60)
    found = search_memories("why did the vercel deploy fail")
    assert 1 <= len(found["memories"]) <= 3
    assert len("\n".join([found["intro"], *found["memories"]])) <= MAX_CHARS


@pytest.mark.parametrize("break_it", ["redaction", "background"])
def test_any_failure_means_no_memories(temp_vault: Path, monkeypatch, tmp_path: Path, break_it: str) -> None:
    write_note(temp_vault, "v.md", "Why did the Vercel deploy fail?", "A missing variable.")
    if break_it == "redaction":
        def broken(text: str) -> str:
            raise RedactionError("fake")
        monkeypatch.setattr(memory_search, "redact", broken)
    else:
        monkeypatch.setattr(memory_search, "BACKGROUND_FILE", tmp_path / "missing.txt")
    found = search_memories("why did the vercel deploy fail")
    assert found["memories"] == [] and found["note"]


@pytest.mark.anyio
async def test_the_memory_tools_say_what_they_do() -> None:
    async with Client(server) as client:
        tools = {tool.name: tool for tool in (await client.list_tools()).tools}
    assert tools["search_memories"].annotations.read_only_hint is True
    save_tool = tools["save_memory"].annotations
    assert save_tool.read_only_hint is False and save_tool.destructive_hint is False
