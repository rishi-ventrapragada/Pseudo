"""FAKE UI Automation controls and patterns, shared by the M12 and M28 tests. Not a test file itself.

FakeControl stands in for a uiautomation Control, FakePattern for one of its patterns. A
pattern keeps its state (Value, ToggleState, IsSelected...) and logs every call, so a test
can see exactly what an action did, and how often a value was read. No real window is touched.
"""

import uiautomation as auto
from comtypes import COMError

P = auto.PatternId
ELEMENT_NOT_AVAILABLE = -2147220991  # 0x80040201 as a signed 32-bit number, the way COM reports it


def gone() -> COMError:
    """The error real UI Automation raises when an element vanished (UIA_E_ELEMENTNOTAVAILABLE)."""
    return COMError(ELEMENT_NOT_AVAILABLE, "element not available", (None, None, None, 0, None))


class FakeRect:
    """Like uiautomation's Rect: a rectangle on screen."""

    def __init__(self, left: int, top: int, right: int, bottom: int) -> None:
        self.left, self.top, self.right, self.bottom = left, top, right, bottom

    def width(self) -> int:
        return self.right - self.left

    def height(self) -> int:
        return self.bottom - self.top


class FakePattern:
    """One pattern. `calls` logs (method, arguments...); `value_reads` counts reads of Value."""

    def __init__(self, value: str = "", **state: object) -> None:
        self.calls: list[tuple] = []
        self.value_reads, self._value = 0, value
        self.IsReadOnly, self.ToggleState, self.IsSelected, self.DefaultAction = False, 0, False, ""
        self.ExpandCollapseState, self.refuse = 0, False  # refuse=True: the app rejects every call
        self.__dict__.update(state)

    @property
    def Value(self) -> str:
        self.value_reads += 1
        return self._value

    def _call(self, *call: object) -> None:
        self.calls.append(call)
        if self.refuse:
            raise gone()

    def Invoke(self, waitTime: float = 0.5) -> bool:
        self._call("Invoke", waitTime)
        return True

    def DoDefaultAction(self, waitTime: float = 0.5) -> bool:
        self._call("DoDefaultAction", waitTime)
        return True

    def SetValue(self, value: str, waitTime: float = 0.5) -> bool:
        self._call("SetValue", value, waitTime)
        self._value = value
        return True

    def Toggle(self, waitTime: float = 0.5) -> bool:
        self._call("Toggle", waitTime)
        self.ToggleState = 1 - self.ToggleState
        return True

    def Select(self, waitTime: float = 0.5) -> bool:
        self._call("Select", waitTime)
        self.IsSelected = True
        return True

    def Expand(self, waitTime: float = 0.5) -> bool:
        self._call("Expand", waitTime)
        self.ExpandCollapseState = 1
        return True

    def Collapse(self, waitTime: float = 0.5) -> bool:
        self._call("Collapse", waitTime)
        self.ExpandCollapseState = 0
        return True


class FakeControl:
    """A fake UI Automation control.

    fail="props"    every question raises, like a control that vanished mid-read
    fail="children" only GetChildren() raises
    fail="password" only IsPassword raises
    patterns        {PatternId: FakePattern}: what it can do (none by default)
    """

    def __init__(self, name: str = "", kind: str = "Text", children: tuple = (), *, fail: str | None = None,
                 offscreen: bool = False, box: tuple = (0, 0, 100, 20), patterns: dict | None = None,
                 runtime_id: tuple = (), enabled: bool = True, password: bool = False) -> None:
        self._name, self._kind, self._children = name, kind, list(children)
        self._fail, self._offscreen, self._box = fail, offscreen, box
        self.patterns, self.runtime_id, self.enabled, self.password = patterns or {}, runtime_id, enabled, password

    def _answer(self, value: object) -> object:
        if self._fail == "props":
            raise gone()
        return value

    @property
    def Name(self) -> str:
        return self._answer(self._name)

    def rename(self, name: str) -> None:
        self._name = name

    @property
    def ControlTypeName(self) -> str:
        return self._answer(f"{self._kind}Control")

    @property
    def IsOffscreen(self) -> bool:
        return self._answer(self._offscreen)

    @property
    def IsPassword(self) -> bool:
        if self._fail == "password":
            raise gone()
        return self._answer(self.password)

    @property
    def IsEnabled(self) -> bool:
        return self._answer(self.enabled)

    @property
    def BoundingRectangle(self) -> FakeRect:
        return self._answer(FakeRect(*self._box))

    def GetChildren(self) -> list["FakeControl"]:
        if self._fail == "children":
            raise gone()
        return self._answer(self._children)

    def GetFirstChildControl(self) -> "FakeControl | None":
        return self._children[0] if self._children else None

    def GetPattern(self, pattern_id: int) -> FakePattern | None:
        return self._answer(self.patterns.get(pattern_id))

    def GetRuntimeId(self) -> list[int]:
        return self._answer(list(self.runtime_id))
