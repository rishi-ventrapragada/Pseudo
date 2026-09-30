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
               Title redaction is a pass-through here unless a test also asks
               for real_redaction (M8). Each test gets a fresh id registry
               (M10), so the first listed window is always "w1".
  no_real_popups -> (M10, runs for EVERY test) a test that reaches the real
               approval popup fails instead of showing it on screen.
  popup_yes / popup_no -> (M10) the person at the approval popup, faked.
  anyio_backend -> (M14) async tests run on asyncio.
  waits     -> (M14) the model's 429 waits are recorded instead of slept.
"""

import sys
from pathlib import Path

import pytest

# Let tests `import agent_tools` from playground/, the way 03_agent_loop.py does.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "playground"))
# Let tests `import pseudo_hands` from the repo root (Phase 2 onward).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import agent_tools  # noqa: E402  (has to come after the sys.path lines above)
from pseudo_hands.core import approval, blocked_apps, window_ids, windows  # noqa: E402
from pseudo_hands.core.windows import RawWindow  # noqa: E402
from pseudo_brain import model  # noqa: E402


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


@pytest.fixture(autouse=True)
def no_real_popups(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(question: str) -> bool:
        pytest.fail("a test tried to show a real approval popup")  # BaseException: ask() can't swallow it
    monkeypatch.setattr(approval, "approver", refuse)


@pytest.fixture
def popup_yes(monkeypatch: pytest.MonkeyPatch) -> FakeApprover:
    fake = FakeApprover(answer=True)
    monkeypatch.setattr(approval, "approver", fake)
    return fake


@pytest.fixture
def popup_no(monkeypatch: pytest.MonkeyPatch) -> FakeApprover:
    fake = FakeApprover(answer=False)
    monkeypatch.setattr(approval, "approver", fake)
    return fake


@pytest.fixture
def desktop(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Returns a helper: desktop([windows...]) makes list_open_windows() see exactly those."""
    list_file = tmp_path / "blocked_apps.txt"
    list_file.write_text("# test list\nKeePass.exe\n", encoding="utf-8")
    monkeypatch.setattr(blocked_apps, "BLOCKED_APPS_FILE", list_file)

    # Redaction off by default, so M4/M5 tests test blocking alone; M8 tests add `real_redaction`.
    monkeypatch.setattr(windows, "redact", lambda title: title)
    monkeypatch.setattr(window_ids, "registry", window_ids.WindowIds())  # (M10) ids start at w1

    def set_windows(fakes: list[RawWindow]) -> None:
        monkeypatch.setattr(windows, "read_all_windows", lambda: fakes)
    return set_windows


@pytest.fixture
def real_redaction(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """(M8) Turn the real redactor back on inside list_open_windows(), with an EMPTY
    private-terms file, so the owner's real list is never read by tests."""
    from pseudo_hands.core import redactor

    terms = tmp_path / "redaction_terms.txt"
    terms.write_text("# no terms\n", encoding="utf-8")
    monkeypatch.setattr(redactor, "TERMS_FILE", terms)
    monkeypatch.setattr(windows, "redact", redactor.redact)
    return terms


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def waits(monkeypatch: pytest.MonkeyPatch) -> list:
    """(M14) Replaces the model's real waiting: each wait is recorded, none is slept."""
    waited: list = []

    async def fake_wait(seconds: float) -> None:
        waited.append(seconds)
    monkeypatch.setattr(model, "wait", fake_wait)
    return waited
