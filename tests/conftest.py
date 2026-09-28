"""Shared pytest setup. pytest loads this file automatically before the tests.

What it provides (a "fixture" is a helper a test asks for by naming it as a
parameter, like beforeEach in Jest, but only for the tests that want it):
  sandbox   -> a fresh, empty temporary sandbox for each test. The real
               playground/sandbox/ is never touched.
  outside   -> a folder NEXT TO that sandbox, holding secret.txt. The tools
               must never be able to read or change anything in it.
  say_yes / say_no -> stand-ins for the human at the approval prompt. They
               record every preview they were shown.
  desktop   -> (M4, M5) desktop([RawWindow, ...]) makes list_open_windows()
               see exactly those fake windows, with a test blocked list that
               holds only KeePass.exe. The real desktop is never read.
"""

import sys
from pathlib import Path

import pytest

# Let tests `import agent_tools` from playground/, the way 03_agent_loop.py does.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "playground"))
# Let tests `import pseudo_hands` from the repo root (Phase 2 onward).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import agent_tools  # noqa: E402  (has to come after the sys.path lines above)
from pseudo_hands.core import blocked_apps, windows  # noqa: E402
from pseudo_hands.core.windows import RawWindow  # noqa: E402


class FakeApprover:
    """Plays the human: remembers each preview and always gives the same answer."""

    def __init__(self, answer: bool) -> None:
        self.answer = answer
        self.previews: list[str] = []

    def __call__(self, preview: str) -> bool:
        self.previews.append(preview)
        return self.answer


@pytest.fixture
def sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    # monkeypatch swaps a value for one test and restores it afterwards
    # (like vi.spyOn / jest.mock in the JS world).
    root = tmp_path / "sandbox"
    root.mkdir()
    monkeypatch.setattr(agent_tools, "SANDBOX_DIR", root)
    return root


@pytest.fixture
def outside(tmp_path: Path) -> Path:
    folder = tmp_path / "outside"
    folder.mkdir()
    (folder / "secret.txt").write_text("OUTSIDE SECRET", encoding="utf-8")
    return folder


@pytest.fixture
def say_yes(monkeypatch: pytest.MonkeyPatch) -> FakeApprover:
    fake = FakeApprover(answer=True)
    monkeypatch.setattr(agent_tools, "approver", fake)
    return fake


@pytest.fixture
def say_no(monkeypatch: pytest.MonkeyPatch) -> FakeApprover:
    fake = FakeApprover(answer=False)
    monkeypatch.setattr(agent_tools, "approver", fake)
    return fake


@pytest.fixture
def desktop(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Returns a helper: desktop([windows...]) makes list_open_windows() see exactly those."""
    list_file = tmp_path / "blocked_apps.txt"
    list_file.write_text("# test list\nKeePass.exe\n", encoding="utf-8")
    monkeypatch.setattr(blocked_apps, "BLOCKED_APPS_FILE", list_file)

    def set_windows(fakes: list[RawWindow]) -> None:
        monkeypatch.setattr(windows, "read_all_windows", lambda: fakes)
    return set_windows
