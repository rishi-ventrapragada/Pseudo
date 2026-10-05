"""M30: the action limit, shared by every pseudo_hands process (D25: 4 action popups per 2 minutes).

What it demonstrates: a limit that lives in ONE process stops counting when a second process
appears. Until M30 only pseudo_brain started pseudo_hands, so an in-memory count was enough
(action_rules.PopupBudget). Since M30, Claude Code starts its OWN pseudo_hands for every action
request (D26), and each new process would begin again at zero: the limit would never be reached.

So the count moves to a small file, action_popups.json in %LOCALAPPDATA%'s Pseudo folder, holding only the
times of the last few popups (numbers, nothing from the screen). Every process reads and updates
it while holding a lock on it, so two processes can't both take the last slot.

Fail closed, like the rest of core: if the file can't be locked, read or written, the answer is
"limit reached", never "go ahead". One escape, so a damaged file can't block actions forever: a
file nobody has touched for a whole window (2 minutes) can't hold a popup that still counts, so
it is started again from empty.
"""

import json
import msvcrt
import os
import time
from collections.abc import Callable
from pathlib import Path

BUDGET_FILE = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Pseudo" / "action_popups.json"
LOCK_TRIES = 20  # each try waits up to about a second (msvcrt.LK_LOCK)


class SharedPopupBudget:
    """At most `limit` action popups in any `seconds`-long stretch, counted across processes.
    The same take() as action_rules.PopupBudget, so act.py doesn't care which one it has."""

    def __init__(self, limit: int = 4, seconds: float = 120.0, clock: Callable[[], float] = time.time,
                 path: Path | None = None) -> None:
        self.limit, self.seconds, self._clock, self._path = limit, seconds, clock, path

    def take(self) -> float:
        """0.0 if a popup may be shown now (and it's counted); else how many seconds to wait."""
        path = self._path or BUDGET_FILE  # looked up on each call, so tests can point it at a temp file
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a+b") as file:  # "a+": create it if missing, never truncate on open
                lock(file)
                try:
                    return self._take_locked(file, path)
                finally:
                    unlock(file)
        except (OSError, ValueError):
            return self.seconds  # fail closed: we can't prove there is room

    def _take_locked(self, file, path: Path) -> float:
        now = self._clock()
        file.seek(0)
        raw = file.read()
        try:
            shown = [min(float(t), now) for t in json.loads(raw or b"[]")]  # a time in the future counts as now
        except (ValueError, TypeError):
            if now - path.stat().st_mtime < self.seconds:
                return self.seconds  # damaged and recent: fail closed
            shown = []  # damaged but untouched for a whole window: nothing in it can still count
        shown = [t for t in shown if now - t < self.seconds]
        full = len(shown) >= self.limit
        if not full:
            shown.append(now)
        file.seek(0)  # written back even when full, so a time pulled back from the future stays pulled back
        file.truncate()
        file.write(json.dumps(shown).encode("ascii"))
        file.flush()
        return self.seconds - (now - min(shown)) if full else 0.0


def lock(file) -> None:
    """Lock the file's first byte for this process; waits if another pseudo_hands holds it."""
    for _try in range(LOCK_TRIES):
        try:
            file.seek(0)
            msvcrt.locking(file.fileno(), msvcrt.LK_LOCK, 1)
            return
        except OSError:
            continue
    raise OSError("the action limit's file stayed locked")


def unlock(file) -> None:
    file.seek(0)
    msvcrt.locking(file.fileno(), msvcrt.LK_UNLCK, 1)
