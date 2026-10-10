"""Tests for M41: a chat is renamed or deleted only if it is one Pseudo saved, in a real folder.

The tricks are the M3 sandbox's and M24's vault's: names that are really paths, links and junctions
that lead outside, hard links, and files Pseudo didn't write. Each case checks that the refusal says
why AND that nothing was touched: every file, inside and outside, is compared byte for byte.
Links are removed first when a test ends, so cleaning up never follows one.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from pseudo_brain import session as session_module
from pseudo_brain.session_files import SessionRefused, delete_session, is_link, rename_session

NAME = "20261010-091500-123"  # a real chat in the sessions folder
DECOY = "20261001-080000-000"  # a chat-shaped file OUTSIDE: the target of every link below

CHANGES = [delete_session, lambda name: rename_session(name, "Renamed")]


def chat_file(folder: Path, name: str) -> None:
    """A fake chat, shaped exactly like one Pseudo saves."""
    folder.mkdir(parents=True, exist_ok=True)
    messages = [{"role": "user", "content": "What does the fake form say?"},
                {"role": "assistant", "content": "A fake booking.", "answered_by": "groq · openai/gpt-oss-120b"}]
    (folder / f"{name}.json").write_text(json.dumps({"started": name, "provider": "groq", "title": "",
                                                     "messages": messages}), encoding="utf-8")


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict:
    sessions = tmp_path / "local" / "Pseudo" / "sessions"
    chat_file(sessions, NAME)
    outside = tmp_path / "outside"
    chat_file(outside, DECOY)
    (outside / "secret.txt").write_text("OUTSIDE SECRET", encoding="utf-8")
    monkeypatch.setattr(session_module, "SESSIONS_DIR", sessions)
    made: list[Path] = []
    yield {"root": tmp_path, "sessions": sessions, "outside": outside, "links": made}
    for link in reversed(made):  # only the links go; what they point at stays
        try:
            os.rmdir(link)  # a junction or a folder symlink
        except OSError:
            link.unlink(missing_ok=True)  # a file symlink or a hard link


def make_link(world: dict, kind: str, link: Path, target: Path) -> None:
    """A symlink, junction or hard link, or skip the test if Windows won't allow it."""
    try:
        if kind == "symlink":
            link.symlink_to(target, target_is_directory=target.is_dir())
        elif kind == "junction":
            if sys.platform != "win32":
                pytest.skip("junctions only exist on Windows")
            subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], check=True, capture_output=True)
        else:
            link.hardlink_to(target)
    except (OSError, subprocess.CalledProcessError) as error:
        pytest.skip(f"this machine won't create a {kind}: {error}")
    world["links"].append(link)


def snapshot(root: Path) -> dict[str, bytes]:
    """Every plain file under root, by path, not following links."""
    found = {}
    for folder, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if not is_link(Path(folder) / d)]
        for file in files:
            path = Path(folder) / file
            if not is_link(path):
                found[str(path.relative_to(root))] = path.read_bytes()
    return found


def refused(world: dict, name, reason: str) -> None:
    """Both changes are refused with `reason`, and no file anywhere changed."""
    before = snapshot(world["root"])
    for change in CHANGES:
        with pytest.raises(SessionRefused, match=reason):
            change(name)
    assert snapshot(world["root"]) == before


@pytest.mark.parametrize("name", [
    "..\\..\\..\\outside\\secret", "../../../outside/" + DECOY, "C:\\Windows\\win.ini", f"{NAME}.json", "*",
    "2026101?-*", f"{NAME}/x", f"x\\{NAME}", f"{NAME} ", "CON", "",
    "٢٠٢٦١٠١٠-٠٩١٥٠٠",  # Arabic-Indic digits: Python's \d says yes, Pseudo never writes them
    None, 20261010, [NAME],
])
def test_a_name_pseudo_does_not_make_is_refused(world: dict, name) -> None:
    refused(world, name, "not a chat name Pseudo makes")


@pytest.mark.parametrize("kind", ["junction", "symlink"])
def test_a_linked_sessions_folder_is_refused(world: dict, monkeypatch: pytest.MonkeyPatch, kind: str) -> None:
    door = world["root"] / "local2" / "Pseudo" / "sessions"
    door.parent.mkdir(parents=True)
    make_link(world, kind, door, world["outside"])
    monkeypatch.setattr(session_module, "SESSIONS_DIR", door)
    refused(world, DECOY, "sessions folder is a link")


@pytest.mark.parametrize("kind", ["junction", "symlink"])
def test_a_linked_pseudo_folder_is_refused(world: dict, monkeypatch: pytest.MonkeyPatch, kind: str) -> None:
    elsewhere = world["root"] / "elsewhere"
    chat_file(elsewhere / "sessions", DECOY)
    door = world["root"] / "local3" / "Pseudo"
    door.parent.mkdir(parents=True)
    make_link(world, kind, door, elsewhere)
    monkeypatch.setattr(session_module, "SESSIONS_DIR", door / "sessions")
    refused(world, DECOY, "Pseudo folder is a link")


@pytest.mark.parametrize("kind", ["symlink", "hard link"])
def test_a_linked_chat_file_is_refused(world: dict, kind: str) -> None:
    make_link(world, kind, world["sessions"] / f"{DECOY}.json", world["outside"] / f"{DECOY}.json")
    refused(world, DECOY, "isn't a plain file Pseudo saved")


def test_a_folder_named_like_a_chat_is_refused(world: dict) -> None:
    (world["sessions"] / f"{DECOY}.json").mkdir()
    refused(world, DECOY, "isn't a plain file Pseudo saved")


@pytest.mark.parametrize("content", [
    "{not json", "[]", '"a string"', '{"started": "20200101-000000", "messages": []}',  # another chat's name
    '{"started": "%s"}' % DECOY, '{"started": "%s", "messages": [{"text": "no role"}]}' % DECOY, "",
])
def test_a_file_pseudo_did_not_save_is_refused(world: dict, content: str) -> None:
    (world["sessions"] / f"{DECOY}.json").write_text(content, encoding="utf-8")
    refused(world, DECOY, "isn't a chat Pseudo saved")


def test_the_real_chat_beside_them_can_still_be_deleted(world: dict) -> None:
    assert delete_session(NAME) == "What does the fake form say?"
    assert not (world["sessions"] / f"{NAME}.json").exists()
    assert (world["outside"] / f"{DECOY}.json").exists() and (world["outside"] / "secret.txt").exists()
