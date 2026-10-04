"""M28: short ids for controls ("c1", "c2", ...), so a model can point at a button (D25).

What it demonstrates: the M10 window-id idea, one level down. A model can't name a control
by its text, because that text is redacted ("[PERSON] as done"), and it must never give
screen positions (it never sees pixels, D6). So read_active_window() writes an opaque id
next to each control that can act ("Button #c12: Save"), like a data-testid, and
act_on_control() takes only an id. This registry remembers what each id means:
(window handle, process id, runtime id, kind, raw name). The runtime id is UI Automation's
own number for one live control: if the app destroys and rebuilds it, the number changes.

Rules (stricter than window ids):
  - ids are never handed out twice; the counter only goes up
  - only the LATEST read's ids work: each read replaces the whole set, so an id from an
    older read answers "old id: read the window again"
  - only ids the model was shown work: ids cut off by the 1,200-character cap are never kept
"""

import re
import threading
from dataclasses import dataclass

ID_IN_TEXT = re.compile(r"#(c\d+)\b")  # how an id appears in an outline: "Button #c12: Save"


@dataclass(frozen=True)
class ControlKey:
    """What one id points at. Kept only inside pseudo_hands; the name is never sent to a model."""

    handle: int  # the window it was read from
    process_id: int  # that window's program, so a reused handle is noticed
    runtime_id: tuple[int, ...]
    kind: str  # "Button", "Edit", ...
    name: str  # its raw name, as Windows reported it in that read


def normal(control_id: str) -> str:
    """"#C12 " -> "c12": models sometimes copy the # or change the case."""
    return control_id.strip().lstrip("#").lower()


def shown_ids(text: str) -> set[str]:
    """Every id written in a (redacted, capped) outline."""
    return set(ID_IN_TEXT.findall(text))


class ControlIds:
    def __init__(self) -> None:
        self._count = 0
        self._current: dict[str, ControlKey] = {}  # the latest read's ids only
        self._lock = threading.Lock()  # the MCP server may run two tool calls at once

    def new_id(self) -> str:
        """A fresh id. It works only after replace() keeps it."""
        with self._lock:
            self._count += 1
            return f"c{self._count}"

    def replace(self, current: dict[str, ControlKey]) -> None:
        """The latest read's ids; every older id stops working."""
        with self._lock:
            self._current = dict(current)

    def find(self, control_id: str) -> ControlKey | None:
        with self._lock:
            return self._current.get(normal(control_id))

    def was_handed_out(self, control_id: str) -> bool:
        """True for an id some read created, even if it no longer works."""
        wanted = normal(control_id)
        with self._lock:
            return re.fullmatch(r"c[1-9]\d*", wanted) is not None and int(wanted[1:]) <= self._count


registry = ControlIds()  # one per process; tests swap in a fresh one
