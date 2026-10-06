"""M30, M32: the PROCESSES of a Claude Code that Pseudo started (a launch, or a warm session).

What it demonstrates: a child process is really a small TREE. `claude` is a .cmd file, so Windows
starts cmd.exe, which starts Claude Code (node.exe), which starts pseudo_hands (the venv's python.exe
launcher, then the real Python): about 6 processes, 310 to 440 MB in M31. Stopping "the process" must
stop all of them, and must never touch a process Pseudo didn't start (CLAUDE.md section 6).

  - stop_tree(pid): a launch's way (M30). The tree is found from its root, which is still running.
  - Family: a warm session's way (M32). A session lives for minutes, so its processes are REMEMBERED as
    they are seen, each by pid AND start time. Windows hands a finished process's pid to the next
    process that starts, so a pid alone could, minutes later, name someone else's program.
    Family also adds up the memory its processes hold, which the face shows.
  - hands_pid(pid): the pseudo_hands inside that tree, the one that will show the approval popup.
"""

import psutil

from pseudo_brain.hands import find_hands_pid

KILL_WAIT_SECONDS = 3.0  # after a kill, how long to wait for Windows to report the process gone


def stop_tree(pid: int) -> None:
    """Stop Claude Code and everything it started (its pseudo_hands). Only this process tree."""
    try:
        family = psutil.Process(pid).children(recursive=True) + [psutil.Process(pid)]
    except psutil.Error:
        return
    for process in family:
        try:
            process.kill()
        except psutil.Error:
            pass


def hands_pid(claude_pid: int) -> int | None:
    """The pseudo_hands that Claude Code started (the one that will show the popup); None if unsure."""
    try:
        return find_hands_pid(psutil.Process(claude_pid))
    except psutil.Error:
        return None


class Family:
    """Every process one Claude Code ever had, each remembered by pid and start time."""

    def __init__(self, root_pid: int) -> None:
        self.root_pid = root_pid
        self.seen: dict[int, float] = {}  # pid -> when that process started
        self.look()

    def look(self) -> list[psutil.Process]:
        """The tree as it is right now, root first, and remember every member. [] once the root is gone."""
        try:
            root = psutil.Process(self.root_pid)
            tree = [root, *root.children(recursive=True)]
            for process in tree:
                self.seen[process.pid] = process.create_time()
        except psutil.Error:
            return []
        return tree

    def ram_mb(self) -> float:
        """The memory the tree holds right now, in MB (resident memory added up, as M31 measured it)."""
        total = 0
        for process in self.look():
            try:
                total += process.memory_info().rss
            except psutil.Error:
                pass
        return round(total / 1_048_576, 1)

    def left(self) -> list[psutil.Process]:
        """The remembered processes that are still running: same pid AND same start time."""
        found = []
        for pid, started in self.seen.items():
            try:
                process = psutil.Process(pid)
                if process.create_time() == started:
                    found.append(process)
            except psutil.Error:
                pass
        return found

    def stop(self, wait_seconds: float) -> int:
        """Give them `wait_seconds` to end by themselves, then kill what is left. Returns how many are STILL running.

        It blocks while it waits, so the session runs it in a worker thread."""
        _gone, left = psutil.wait_procs(self.left(), timeout=wait_seconds)
        for process in left:
            try:
                process.kill()
            except psutil.Error:
                pass
        _gone, left = psutil.wait_procs(left, timeout=KILL_WAIT_SECONDS)
        return len(left)
