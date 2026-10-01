"""Tests for M18: which process is pseudo_hands (find_hands_pid in pseudo_brain/hands.py), and the
bridge telling the face that pid, so the face can let ONLY it bring the approval popup to the front.

Every process here is FAKE: a small stand-in with a pid, a command line and children.
No process is started or read.
"""

from contextlib import asynccontextmanager

import psutil
import pytest

from brain_fakes import FAKE_HANDS
from pseudo_brain import bridge
from pseudo_brain.hands import Hands, connect_hands, find_hands_pid
from test_brain_bridge import run, world  # noqa: F401 - world is a pytest fixture

HANDS = ["C:\\dev\\Pseudo\\.venv\\Scripts\\python.exe", "-m", "pseudo_hands.mcp_server"]


class FakeProcess:
    """Just what find_hands_pid uses of a psutil.Process."""

    def __init__(self, pid: int, cmdline: list[str] | None, children: list["FakeProcess"] = ()) -> None:
        self.pid, self._cmdline, self._children = pid, cmdline, list(children)

    def cmdline(self) -> list[str]:
        if self._cmdline is None:
            raise psutil.AccessDenied(self.pid)
        return self._cmdline

    def children(self, recursive: bool = False) -> list["FakeProcess"]:
        if not recursive:
            return self._children
        return [p for child in self._children for p in [child, *child.children(recursive=True)]]


def bridge_with(*children: FakeProcess) -> FakeProcess:
    return FakeProcess(100, ["python.exe", "-m", "pseudo_brain.bridge"], children)


def test_the_real_python_is_picked_not_the_venv_launcher() -> None:
    real = FakeProcess(301, HANDS, [FakeProcess(302, ["conhost.exe"])])
    launcher = FakeProcess(300, HANDS, [FakeProcess(303, ["conhost.exe"]), real])
    assert find_hands_pid(bridge_with(launcher)) == 301


def test_other_child_processes_are_ignored() -> None:
    ollama = FakeProcess(400, ["ollama.exe", "serve"])
    unreadable = FakeProcess(401, None)  # its command line can't be read: it isn't pseudo_hands
    assert find_hands_pid(bridge_with(ollama, unreadable, FakeProcess(300, HANDS))) == 300


@pytest.mark.parametrize("children", [
    [],  # pseudo_hands isn't running
    [FakeProcess(300, ["python.exe", "-m", "something_else"])],
    [FakeProcess(300, HANDS), FakeProcess(310, HANDS)],  # two of them: not sure which, so none
])
def test_anything_uncertain_gives_no_pid(children: list[FakeProcess]) -> None:
    assert find_hands_pid(bridge_with(*children)) is None


def test_a_process_that_vanishes_gives_no_pid() -> None:
    class Gone(FakeProcess):
        def children(self, recursive: bool = False) -> list:
            raise psutil.NoSuchProcess(self.pid)
    assert find_hands_pid(Gone(100, ["python.exe"])) is None


@pytest.mark.anyio
async def test_in_memory_hands_have_no_pid() -> None:
    async with connect_hands(FAKE_HANDS) as hands:
        assert hands.pid is None


@pytest.mark.anyio
async def test_ready_tells_the_face_the_pid_of_pseudo_hands(world: dict, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: F811
    @asynccontextmanager
    async def hands_with_a_pid():
        async with connect_hands(FAKE_HANDS) as fake:
            yield Hands(fake._client, [], pid=4321)
    monkeypatch.setattr(bridge, "connect_hands", hands_with_a_pid)

    async def nothing(face) -> None:
        pass
    _, face = await run(nothing)
    assert face.replies("ready")[0]["hands_pid"] == 4321
