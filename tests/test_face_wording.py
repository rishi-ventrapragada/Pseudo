"""M40: every event the brain sends has a wording in the window (face/src/steps.ts).

Until M40 the window copied the terminal's wording word for word; now it speaks to a person, and the terminal
keeps its own (terminal.py, pinned by its own tests). What must not happen is an event the window has no words
for: it would simply be missing from "what Pseudo did". So this reads every on_event("kind", ...) in pseudo_brain
and looks for `case 'kind'` in steps.ts. (Python reads the TypeScript file as text; no browser is involved.)
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
STEPS = (REPO_ROOT / "face" / "src" / "steps.ts").read_text(encoding="utf-8")
NOT_SHOWN = {"hands_pid"}  # for the main process only: which process may bring the approval popup forward


def brain_event_kinds() -> set[str]:
    kinds: set[str] = set()
    for path in (REPO_ROOT / "pseudo_brain").glob("*.py"):
        kinds |= set(re.findall(r'on_event\(\s*"([a-z_]+)"', path.read_text(encoding="utf-8")))
    return kinds


def test_found_the_brains_events() -> None:
    kinds = brain_event_kinds()
    assert {"sending", "tool_call", "answer", "routed", "warm", "memories", "hands_pid"} <= kinds
    assert len(kinds) >= 20


def test_every_event_has_a_wording_in_the_window() -> None:
    missing = [kind for kind in sorted(brain_event_kinds()) if f"case '{kind}'" not in STEPS]
    assert missing == []


def test_the_events_the_window_does_not_show_are_few_and_said_so() -> None:
    for kind in NOT_SHOWN:
        assert re.search(rf"case '{kind}':.*\n\s*default:\s*\n\s*return null", STEPS), kind
