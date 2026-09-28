"""Tests for M9: read_active_window(). Every window, tree and string here is FAKE.

The UI Automation walk is replaced with fake tree lines, so these tests never
read a real window. (Real UIA is checked separately, on a fake window we open.)
"""

import json
from pathlib import Path

import pytest

from pseudo_hands.core import active_window, blocked_apps, redactor, ui_tree
from pseudo_hands.core.active_window import CONTENT_WITHHELD, MAX_CONTENT_CHARS, TRUNCATED_MARK, read_active_window
from pseudo_hands.core.blocked_apps import RESTRICTED
from pseudo_hands.core.redactor import RedactionError
from pseudo_hands.core.ui_tree import TreeLine, TreeRead, clean, control_line
from pseudo_hands.core.windows import RawWindow

FAKE_TREE = [TreeLine(0, "Window", "notes.txt - Notepad"),
             TreeLine(1, "Document", "Text editor = Meeting with Rahul Verma, call +91 98765 43210"),
             TreeLine(1, "Button", "Save")]


def window(app: str | None = "notepad.exe", title: str = "notes.txt - Notepad", handle: int = 101) -> RawWindow:
    return RawWindow(title=title, app=app, visible=True, cloaked=False, focused=True, handle=handle)


@pytest.fixture
def screen(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """screen(windows, tree) fakes the z-ordered windows and the tree every read returns.
    (M12) tree can be a list: one result per read, the last one repeating. No retry wait."""
    (tmp_path / "blocked.txt").write_text("KeePass.exe\n", encoding="utf-8")
    (tmp_path / "terms.txt").write_text("# none\n", encoding="utf-8")
    monkeypatch.setattr(blocked_apps, "BLOCKED_APPS_FILE", tmp_path / "blocked.txt")
    monkeypatch.setattr(redactor, "TERMS_FILE", tmp_path / "terms.txt")
    monkeypatch.setattr(active_window, "RETRY_WAIT_SECONDS", 0)
    reads: list[int] = []

    def set_screen(windows: list[RawWindow], tree: TreeRead | Exception | list) -> list[int]:
        monkeypatch.setattr(active_window, "read_all_windows", lambda: windows)
        outcomes, calls = (tree if isinstance(tree, list) else [tree]), []

        def fake_read_tree(handle: int) -> TreeRead:
            reads.append(handle)
            calls.append(handle)
            outcome = outcomes[min(len(calls), len(outcomes)) - 1]
            if isinstance(outcome, Exception):
                raise outcome
            return outcome
        monkeypatch.setattr(active_window, "read_tree", fake_read_tree)
        return reads
    return set_screen


# ---------- what comes back ----------

def test_content_is_redacted(screen) -> None:
    screen([window()], TreeRead(FAKE_TREE, False, 3))
    result = read_active_window()
    assert "[PERSON]" in result["content"] and "[IN_PHONE]" in result["content"]
    assert result["content"].splitlines()[-1] == "  Button: Save"
    assert result["app"] == "notepad.exe" and result["controls_read"] == 3 and result["note"] == ""


def test_nothing_fake_leaks_anywhere(screen) -> None:
    screen([window(title="Rahul Verma notes - Notepad")], TreeRead(FAKE_TREE, False, 3))
    sent = json.dumps(read_active_window())
    assert not any(s in sent for s in ["Rahul", "Verma", "98765", "43210"])


# ---------- privacy rules ----------

@pytest.mark.parametrize("app", ["KeePass.exe", None])  # blocked, or unknown owner
def test_blocked_or_unknown_apps_are_never_walked(screen, app: str | None) -> None:
    reads = screen([window(app=app, title="Vault - secret")], TreeRead(FAKE_TREE, False, 3))
    result = read_active_window()
    assert result["title"] == RESTRICTED and result["app"] == RESTRICTED and result["content"] == ""
    assert reads == []  # the UI tree was never read


def test_the_assistant_window_is_skipped(screen) -> None:
    reads = screen([window(app="Hermes.exe", title="Hermes", handle=7), window(handle=101)], TreeRead(FAKE_TREE, False, 3))
    assert read_active_window()["app"] == "notepad.exe" and reads == [101]


def test_password_fields_are_never_read() -> None:
    class FakePasswordBox:
        Name, IsPassword = "Password", True

        def GetPattern(self, _pattern_id: int) -> None:
            raise AssertionError("a password field's value must never be read")
    assert control_line(FakePasswordBox(), "Edit") == "Password = [password field]"


def test_a_redaction_failure_withholds_the_content(screen, monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(_text: str) -> str:
        raise RedactionError("simulated")
    monkeypatch.setattr(active_window, "redact", broken)
    screen([window()], TreeRead(FAKE_TREE, False, 3))
    result = read_active_window()
    assert result["content"] == CONTENT_WITHHELD and "98765" not in json.dumps(result)


def test_a_ui_automation_error_reports_only_its_type(screen) -> None:
    screen([window()], OSError("Rahul Verma +91 98765 43210"))  # an error message containing text
    result = read_active_window()
    assert result["note"] == "read failed (OSError)" and "Rahul" not in json.dumps(result)


# ---------- size limits ----------

def test_long_content_is_cut_at_a_line_boundary(screen) -> None:
    many = [TreeLine(1, "ListItem", f"Row {i} of the fake report") for i in range(200)]
    screen([window()], TreeRead(many, False, 200))
    result = read_active_window()
    lines = result["content"].splitlines()
    assert result["truncated"] and lines[-1] == TRUNCATED_MARK
    assert len(result["content"]) <= MAX_CONTENT_CHARS + len(TRUNCATED_MARK) + 1
    assert all(line.startswith("  ListItem: Row ") and line.endswith("fake report") for line in lines[:-1])


def test_a_walk_that_hit_its_budget_is_marked_truncated(screen) -> None:
    screen([window()], TreeRead(FAKE_TREE, True, 200))
    assert read_active_window()["truncated"] is True


def test_a_long_text_is_never_cut_inside_a_number() -> None:
    cut = clean("Call +91 98765 43210 about the invoice", 14)
    assert not any(ch.isdigit() for ch in cut) and cut.endswith("…")


def test_empty_trees_and_no_window_are_explained(screen) -> None:
    screen([window()], TreeRead([], False, 1))
    assert read_active_window()["note"] == "no readable controls"
    screen([], TreeRead([], False, 0))
    assert read_active_window()["note"] == "no active window"


def test_budget_constants_are_what_the_lesson_says() -> None:
    assert (ui_tree.MAX_DEPTH, ui_tree.MAX_CONTROLS, ui_tree.MAX_RAW_CHARS) == (12, 200, 4000)
    assert ui_tree.TIME_BUDGET_SECONDS == 2.0 and MAX_CONTENT_CHARS == 1200
    assert active_window.RETRY_WAIT_SECONDS == 1.0  # (M12)


# ---------- M12: one retry for a failed or empty first read ----------

GOOD = TreeRead(FAKE_TREE, False, 3)
WINDOW_ONLY = TreeRead([TreeLine(0, "Window", "notes.txt - Notepad")], False, 1)  # nothing inside


def test_a_failed_first_read_is_retried_once(screen) -> None:
    reads = screen([window()], [OSError("cold start"), GOOD])
    result = read_active_window()
    assert reads == [101, 101] and result["note"] == "read on the second try"
    assert "[PERSON]" in result["content"]  # the second read went through redaction as usual


def test_a_first_read_with_nothing_inside_the_window_is_retried(screen) -> None:
    reads = screen([window()], [WINDOW_ONLY, GOOD])
    assert read_active_window()["controls_read"] == 3 and reads == [101, 101]


def test_a_good_first_read_is_not_retried(screen) -> None:
    reads = screen([window()], [GOOD, OSError("a second read must not happen")])
    assert read_active_window()["note"] == "" and reads == [101]


def test_two_failures_still_report_only_the_type(screen) -> None:
    reads = screen([window()], [OSError("Rahul Verma +91 98765 43210")] * 2)
    result = read_active_window()
    assert reads == [101, 101] and result["note"] == "read failed (OSError)"
    assert "Rahul" not in json.dumps(result) and "98765" not in json.dumps(result)


def test_skipped_controls_are_counted_in_the_note(screen) -> None:
    screen([window()], TreeRead(FAKE_TREE, False, 5, skipped=2))
    assert read_active_window()["note"] == "2 controls skipped (read errors)"
    screen([window()], [OSError("cold start"), TreeRead(FAKE_TREE, False, 4, skipped=1)])
    assert read_active_window()["note"] == "read on the second try; 1 control skipped (read errors)"
