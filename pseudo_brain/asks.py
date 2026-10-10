"""M40: every tool_call event says whether that tool asks for your approval (`asks`).

What it demonstrates: telling the window a FACT instead of letting it guess. Until M40 the face showed
"an approval popup may appear" for every tool, reads included, because it couldn't tell them apart (D11:
it decides nothing). pseudo_hands marks each tool it publishes: read_only_hint=True for the reads. The
brain keeps those marks (hands.py) and adds `asks` to each tool_call, whichever brain made the call:
the Groq loop, Claude Code (launched or warm), or Pseudo's own save to memory.

A mark is a hint, not a guard: the popup itself still runs inside pseudo_hands' core (D13). So the
safe default is to ask: a tool with no mark, or a name the brain doesn't know, counts as asking.
"""

from pseudo_brain.loop import EventSink


class WithAsks:
    """An on_event that adds `asks` to tool_call events and passes every other event on unchanged."""

    def __init__(self, sink: EventSink) -> None:
        self.sink = sink
        self.hands = None  # set for each question (chat.py); until then every tool counts as asking

    def __call__(self, kind: str, data: dict) -> None:
        if kind == "tool_call":
            name = str(data.get("name", ""))
            data = {**data, "asks": self.hands.asks(name) if self.hands is not None else True}
        self.sink(kind, data)
