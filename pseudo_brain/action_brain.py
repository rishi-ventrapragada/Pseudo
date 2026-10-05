"""M30: the action brain's settings (D26), read from providers.toml.

What it demonstrates: config as an allowlist, again (M16). Which program answers action
requests, which model, and above all WHICH TOOLS it gets are written in one committed file,
and checked when Pseudo starts. The brain's code names no tools: the names live in
providers.toml, so `git diff` shows any change to what a brain may call.

Rules checked here:
  - The action brain never gets the switch tool (switch requests stay on Groq) and never the
    two memory tools (those are brain-only: no model may search or write memory, M24).
  - account_env is the NAME of a .env variable, never the account itself.
"""

import tomllib
from dataclasses import dataclass
from pathlib import Path

from pseudo_brain.hands import MEMORY_TOOLS
from pseudo_brain.providers import PROVIDERS_FILE, ProviderRefused

FIELDS = ("name", "command", "model", "tools", "account_env", "privacy", "timeout_seconds")
TEXT_FIELDS = ("name", "model", "account_env", "privacy")


@dataclass(frozen=True)
class ActionBrain:
    name: str
    command: tuple[str, ...]  # the program to start; tests put a fake one here
    model: str
    tools: tuple[str, ...]  # the only tools it is given
    account_env: str
    privacy: str
    timeout_seconds: float
    id: str = "claude-code"  # shown wherever a provider id is shown


@dataclass(frozen=True)
class Routing:
    switch_tool: str  # offered to a model only when you ask to see or switch to a window
    action_brain: ActionBrain | None  # None: every question stays on the chat provider


def is_names(value: object) -> bool:
    return isinstance(value, list) and bool(value) and all(isinstance(item, str) and item for item in value)


def load_routing(path: Path = PROVIDERS_FILE) -> Routing:
    """Read and check the routing settings. Raises ProviderRefused on the first problem."""
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise ProviderRefused(f"can't read {path.name} ({type(error).__name__})") from None
    switch_tool = data.get("switch_tool", "")
    if not isinstance(switch_tool, str):
        raise ProviderRefused("switch_tool must be a tool's name, in quotes")
    entry = data.get("action_brain")
    if entry is None:
        return Routing(switch_tool, None)
    missing = [name for name in FIELDS if name not in entry]
    if missing:
        raise ProviderRefused(f"action_brain: missing {', '.join(missing)}")
    if not is_names(entry["command"]) or not is_names(entry["tools"]):
        raise ProviderRefused("action_brain: command and tools must be non-empty lists of names")
    forbidden = [tool for tool in entry["tools"] if tool == switch_tool or tool in MEMORY_TOOLS]
    if forbidden:
        raise ProviderRefused(f"action_brain: it may never be given {', '.join(forbidden)}")
    if not all(isinstance(entry[name], str) and entry[name] for name in TEXT_FIELDS):
        raise ProviderRefused("action_brain: name, model, account_env and privacy must be text, in quotes")
    if "@" in entry["account_env"]:
        raise ProviderRefused("action_brain: account_env is the NAME of a .env variable, never the account itself")
    return Routing(switch_tool, ActionBrain(entry["name"], tuple(entry["command"]), entry["model"],
                                            tuple(entry["tools"]), entry["account_env"], entry["privacy"],
                                            float(entry["timeout_seconds"])))
