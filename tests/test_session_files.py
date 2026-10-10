"""Tests for M41: renaming, deleting and searching saved chats (pseudo_brain/session_files.py).

Every chat here is FAKE and lives in a temporary folder. The refusals (names that are really paths,
links, junctions, files Pseudo didn't write) are in test_session_files_refusals.py.
"""

import json
from pathlib import Path

import pytest

from pseudo_brain import session as session_module
from pseudo_brain.session import Session, list_sessions, load_session
from pseudo_brain.session_files import SessionRefused, delete_session, rename_session, search_sessions

NAME, OTHER = "20261010-091500-123", "20261009-180000-456"  # OTHER is older, so it lists second


def save(name: str, questions: list[str], answer: str) -> Path:
    session = Session(started=name, provider="groq")
    for question in questions:
        session.start_turn(question)
        session.add({"role": "assistant", "content": answer})
        session.note_answer("groq · openai/gpt-oss-120b")
    return session.save()


@pytest.fixture
def chats(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    folder = tmp_path / "Pseudo" / "sessions"
    monkeypatch.setattr(session_module, "SESSIONS_DIR", folder)
    save(NAME, ["What does the booking form say?"], "It's a room booking for Friday.")
    save(OTHER, ["Summarise the window I was on", "Which shipping speeds can I pick?"], "Standard, express, next day.")
    return folder


def titles() -> dict[str, str]:
    return {item["name"]: item["title"] for item in list_sessions()}


# ---------- rename ----------

def test_a_renamed_chat_keeps_everything_else(chats: Path) -> None:
    before = json.loads((chats / f"{NAME}.json").read_text(encoding="utf-8"))
    assert rename_session(NAME, "  Booking form  ") == "Booking form"
    after = json.loads((chats / f"{NAME}.json").read_text(encoding="utf-8"))
    assert after == {**before, "title": "Booking form"}  # messages, who answered and the provider are untouched


def test_the_sidebar_shows_the_new_name_or_else_the_first_question(chats: Path) -> None:
    rename_session(NAME, "Booking form")
    assert titles() == {NAME: "Booking form", OTHER: "Summarise the window I was on"}


def test_an_open_chat_keeps_its_name_when_it_is_saved_again(chats: Path) -> None:
    rename_session(NAME, "Booking form")
    session = load_session(NAME)
    assert session.title == "Booking form"
    session.start_turn("And on Saturday?")
    session.add({"role": "assistant", "content": "Nothing is booked."})
    session.save()
    assert titles()[NAME] == "Booking form"


def test_a_chat_saved_before_m41_has_no_title_and_lists_its_first_question(chats: Path) -> None:
    path = chats / f"{OTHER}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    del data["title"]
    path.write_text(json.dumps(data), encoding="utf-8")
    assert titles()[OTHER] == "Summarise the window I was on"
    assert load_session(OTHER).title == ""


@pytest.mark.parametrize("title, reason", [
    ("", "can't be empty"), ("   ", "can't be empty"), (None, "can't be empty"), (42, "can't be empty"),
    ("two\nlines", "one line"), ("a\ttab", "one line"),
    ("‮evil", "one line"),  # a right-to-left override: it would show the name backwards
    ("x" * 61, "at most 60 characters"),
])
def test_a_name_that_is_not_one_plain_line_is_refused_and_nothing_changes(chats: Path, title, reason: str) -> None:
    before = (chats / f"{NAME}.json").read_bytes()
    with pytest.raises(SessionRefused, match=reason):
        rename_session(NAME, title)
    assert (chats / f"{NAME}.json").read_bytes() == before


def test_sixty_characters_and_any_language_are_fine(chats: Path) -> None:
    assert rename_session(NAME, "x" * 60) == "x" * 60
    assert rename_session(NAME, "बुकिंग फ़ॉर्म, café") == "बुकिंग फ़ॉर्म, café"


# ---------- delete ----------

def test_delete_removes_that_one_file_and_says_its_title(chats: Path) -> None:
    assert delete_session(NAME) == "What does the booking form say?"
    assert not (chats / f"{NAME}.json").exists()
    assert titles() == {OTHER: "Summarise the window I was on"}


def test_deleting_it_again_is_refused(chats: Path) -> None:
    delete_session(NAME)
    with pytest.raises(SessionRefused, match="no saved chat called"):
        delete_session(NAME)


# ---------- search ----------

@pytest.mark.parametrize("text, found", [
    ("BOOKING", [NAME]),                 # the first question, any case
    ("shipping speeds", [OTHER]),        # only in the second question
    ("next day", []),                    # only in an answer: answers are never searched
    ("zzz", []),
    ("", [NAME, OTHER]), ("   ", [NAME, OTHER]), (None, [NAME, OTHER]),  # no words: every chat, newest first
])
def test_search_looks_at_titles_and_your_messages_only(chats: Path, text, found: list[str]) -> None:
    assert [item["name"] for item in search_sessions(text)] == found


def test_search_finds_a_chat_by_the_name_you_gave_it(chats: Path) -> None:
    rename_session(OTHER, "Release notes")
    assert [item["name"] for item in search_sessions("release")] == [OTHER]
    assert search_sessions("release")[0]["title"] == "Release notes"


def test_search_leaves_out_a_damaged_file(chats: Path) -> None:
    (chats / "20261010-120000-000.json").write_text("{not json", encoding="utf-8")
    assert [item["name"] for item in search_sessions("the")] == [NAME, OTHER]
