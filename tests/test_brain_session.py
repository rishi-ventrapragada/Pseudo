"""Tests for M14: pseudo_brain's session history (trimming, saving, continuing), plus two
rules about the package itself: the loop never prints, and the brain names no tools.
All messages here are FAKE; sessions are saved to a temporary folder.
"""

import ast
import json
from pathlib import Path

import pytest

from pseudo_brain import session as session_module
from pseudo_brain.session import Session, TooLarge, load_latest
from pseudo_brain.terminal import printer

PSEUDO_BRAIN = Path(__file__).resolve().parent.parent / "pseudo_brain"
MARKER = "ZEBRA-7731"  # fake screen text inside a fake tool result


def turn(number: int, padding: int = 0, with_tool: bool = False) -> list[dict]:
    """One finished fake turn: question, optional tool call + result, answer."""
    messages = [{"role": "user", "content": f"question {number} " + "x" * padding}]
    if with_tool:
        call = {"id": f"c{number}", "type": "function", "function": {"name": "fake_tool", "arguments": "{}"}}
        messages += [{"role": "assistant", "content": None, "tool_calls": [call]},
                     {"role": "tool", "tool_call_id": f"c{number}", "content": f"{MARKER} fake screen text"}]
    return messages + [{"role": "assistant", "content": f"answer {number}"}]


@pytest.fixture
def sessions_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setattr(session_module, "SESSIONS_DIR", tmp_path / "sessions")
    return tmp_path / "sessions"


# ---------- trimming ----------

def test_a_small_history_is_sent_whole() -> None:
    session = Session(turns=[turn(1), turn(2)])
    session.start_turn("question 3")
    messages, _, dropped = session.messages_for_request("fake system prompt", [], 3000)
    assert dropped == 0 and messages[0] == {"role": "system", "content": "fake system prompt"}
    assert [m["content"] for m in messages[1:]] == ["question 1 ", "answer 1", "question 2 ", "answer 2", "question 3"]


def test_old_turns_are_dropped_oldest_first_and_whole() -> None:
    session = Session(turns=[turn(n, padding=400, with_tool=True) for n in range(1, 6)])
    session.start_turn("the current question")
    messages, estimate, dropped = session.messages_for_request("fake system prompt", [], 400)
    asked = [m["content"].split()[1] for m in messages if m["role"] == "user"]
    assert estimate <= 400 and dropped >= 1 and asked[-1] == "current"
    assert asked[:-1] == [str(n) for n in range(6 - len(asked[:-1]), 6)]  # the most recent turns survive
    call_ids = {c["id"] for m in messages if m.get("tool_calls") for c in m["tool_calls"]}
    assert all(m["tool_call_id"] in call_ids for m in messages if m["role"] == "tool")  # no orphaned results
    assert len(session.turns) == 6  # trimming shaped the request; history keeps everything


def test_a_current_turn_over_budget_fails_and_is_kept() -> None:
    session = Session(turns=[turn(1)])
    session.start_turn("y" * 1000)
    with pytest.raises(TooLarge):
        session.messages_for_request("fake system prompt", [], 50)
    assert len(session.turns) == 2


# ---------- saving and continuing ----------

def test_saving_keeps_only_your_messages_and_final_answers(sessions_dir: Path) -> None:
    path = Session(turns=[turn(1, with_tool=True), turn(2)]).save()
    text = path.read_text(encoding="utf-8")
    assert [m["role"] for m in json.loads(text)["messages"]] == ["user", "assistant", "user", "assistant"]
    assert MARKER not in text and "tool_calls" not in text and '"tool"' not in text
    assert path.parent == sessions_dir


def test_continue_loads_the_latest_session(sessions_dir: Path) -> None:
    Session(turns=[turn(1)], started="20260101-000000").save()
    Session(turns=[turn(2), turn(3)], started="20260102-000000").save()
    latest = load_latest()
    assert latest.started == "20260102-000000"
    assert [[m["content"] for m in t] for t in latest.turns] == [["question 2 ", "answer 2"], ["question 3 ", "answer 3"]]


def test_no_saved_session_means_a_fresh_start(sessions_dir: Path) -> None:
    assert load_latest() is None


def test_a_saved_session_keeps_its_provider_and_who_answered(sessions_dir: Path) -> None:  # (M16)
    session = Session(turns=[turn(1)], provider="local")
    session.note_answer("local Â· tiny-model")
    session.start_turn("question 2")  # no answer yet: nothing to label
    saved = json.loads(session.save().read_text(encoding="utf-8"))
    assert saved["provider"] == "local"
    assert [m.get("answered_by") for m in saved["messages"]] == [None, "local Â· tiny-model", None]
    loaded = load_latest()
    assert loaded.provider == "local" and loaded.answered_by == {0: "local Â· tiny-model"}
    messages, _, _ = loaded.messages_for_request("fake system prompt", [], 3000)
    assert all("answered_by" not in m for m in messages)  # a label is never sent to a model


def test_a_session_saved_before_m16_belongs_to_groq(sessions_dir: Path) -> None:
    sessions_dir.mkdir(parents=True)
    old = {"started": "20260928-000000", "messages": [{"role": "user", "content": "hi"},
                                                       {"role": "assistant", "content": "hello"}]}
    (sessions_dir / "20260928-000000.json").write_text(json.dumps(old), encoding="utf-8")
    assert load_latest().provider == "groq"


# ---------- rules about the package ----------

def test_only_the_terminal_prints() -> None:
    for name in ("loop.py", "session.py", "hands.py", "model.py", "providers.py", "local_server.py", "chat.py",
                 "bridge.py"):
        tree = ast.parse((PSEUDO_BRAIN / name).read_text(encoding="utf-8"))
        prints = [n for n in ast.walk(tree)
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "print"]
        assert prints == [], f"{name} prints; only terminal.py may (the face reuses the loop and chat.py)"


def test_the_brain_names_no_tools() -> None:
    for path in PSEUDO_BRAIN.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for tool in ("list_open_windows", "read_active_window", "focus_window"):
            assert tool not in text, f"{path.name} names {tool}; tools must come from the server"


def test_the_prompt_asks_for_a_fresh_read_of_the_screen() -> None:  # (P5-tune) M14 answered from stale history
    from pseudo_brain.loop import SYSTEM_PROMPT
    assert "call the tools again" in SYSTEM_PROMPT and "never answer from earlier tool results" in SYSTEM_PROMPT


def test_the_terminal_hides_the_api_key(capsys: pytest.CaptureFixture) -> None:
    printer(["fake-key-123"])("failed", {"reason": "an error that mentions fake-key-123"})
    output = capsys.readouterr().out
    assert "fake-key-123" not in output and "<hidden>" in output and "No answer was produced" in output
