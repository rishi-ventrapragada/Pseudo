"""M30: the action limit shared by every pseudo_hands process (pseudo_hands/core/action_budget.py).

Two SharedPopupBudget objects pointed at the same file stand in for two pseudo_hands processes
(pseudo_brain's own, and the one Claude Code starts). The clock is fake, and the file is temporary.
"""

import os
from pathlib import Path

from pseudo_hands.core import action_rules
from pseudo_hands.core.action_budget import SharedPopupBudget


class Clock:
    def __init__(self) -> None:
        self.now = 1_000_000.0

    def __call__(self) -> float:
        return self.now


def two_processes(path: Path) -> tuple[Clock, SharedPopupBudget, SharedPopupBudget]:
    clock = Clock()
    return clock, SharedPopupBudget(clock=clock, path=path), SharedPopupBudget(clock=clock, path=path)


def test_core_uses_the_shared_limit() -> None:
    assert isinstance(action_rules.budget, SharedPopupBudget)
    assert (action_rules.budget.limit, action_rules.budget.seconds) == (4, 120.0)


def test_a_fifth_popup_is_refused_even_from_another_process(tmp_path: Path) -> None:
    clock, first, second = two_processes(tmp_path / "count.json")
    for budget in (first, second, first, second):
        assert budget.take() == 0.0
        clock.now += 10
    assert second.take() == 80.0 and first.take() == 80.0  # the oldest popup leaves the window in 80 s
    clock.now += 80
    assert second.take() == 0.0


def test_a_warm_sessions_process_and_each_launchs_process_share_one_count(tmp_path: Path) -> None:
    """(M32) A warm session's pseudo_hands lives for minutes; every launch starts a new one. One count for all."""
    clock, path = Clock(), tmp_path / "count.json"
    warm = SharedPopupBudget(clock=clock, path=path)  # the open session's pseudo_hands

    def launch() -> SharedPopupBudget:
        return SharedPopupBudget(clock=clock, path=path)  # a new process for one request, then gone

    for budget in (launch(), warm, warm, launch()):  # a launch, two warm requests, another launch
        assert budget.take() == 0.0
        clock.now += 20
    assert warm.take() == 40.0 and launch().take() == 40.0  # the 5th is refused whichever way it comes
    clock.now += 40  # the first popup has left the 2-minute window: room for one more, and then full again
    assert warm.take() == 0.0 and launch().take() == 20.0


def test_a_brand_new_process_starts_with_the_same_count(tmp_path: Path) -> None:
    clock, first, _ = two_processes(tmp_path / "count.json")
    assert [first.take() for _ in range(4)] == [0.0] * 4
    fresh = SharedPopupBudget(clock=clock, path=tmp_path / "count.json")  # as if Claude Code had just launched one
    assert fresh.take() == 120.0


def test_a_damaged_recent_file_means_the_limit_is_reached(tmp_path: Path) -> None:
    path = tmp_path / "count.json"
    path.write_text("not json", encoding="ascii")
    clock = Clock()
    clock.now = path.stat().st_mtime + 5
    assert SharedPopupBudget(clock=clock, path=path).take() == 120.0
    assert path.read_text(encoding="ascii") == "not json"  # nothing was guessed or repaired


def test_a_damaged_file_untouched_for_a_whole_window_starts_again(tmp_path: Path) -> None:
    path = tmp_path / "count.json"
    path.write_text("not json", encoding="ascii")
    clock = Clock()
    clock.now = path.stat().st_mtime + 121
    assert SharedPopupBudget(clock=clock, path=path).take() == 0.0


def test_a_file_that_cant_be_opened_means_the_limit_is_reached(tmp_path: Path) -> None:
    folder = tmp_path / "count.json"
    folder.mkdir()  # a folder where the file should be: opening it fails
    assert SharedPopupBudget(path=folder).take() == 120.0


def test_times_from_the_future_count_as_now(tmp_path: Path) -> None:
    path = tmp_path / "count.json"
    clock = Clock()
    path.write_text(str([clock.now + 9999] * 4), encoding="ascii")  # as if the laptop's clock was set back
    budget = SharedPopupBudget(clock=clock, path=path)
    assert budget.take() == 120.0
    clock.now += 120
    assert budget.take() == 0.0


def test_only_numbers_are_stored(tmp_path: Path) -> None:
    path = tmp_path / "count.json"
    SharedPopupBudget(path=path).take()
    assert path.read_text(encoding="ascii").strip("[]").replace(".", "").isdigit() and os.path.getsize(path) < 40
