"""M42 (D29): the one list of tools a model may be offered, and the tools only Pseudo's brain calls.

What it demonstrates: an allowlist for TOOLS, as providers.toml already is for providers (D16).
Before D29 a model was offered whatever pseudo_hands published, minus the two memory tools that
hands.py named (M24). So a NEW tool, like M42's three for Pseudo's window, would have reached the
model by default. Now a tool reaches a model only if providers.toml's model_tools names it, and
`git diff` shows the day it was added.

Two lists, which never overlap:
  - model_tools (providers.toml): what Groq's loop is offered (the switch tool only by M29's rule,
    chat.py), and what the action brain's tools must come from (action_brain.py).
  - BRAIN_TOOLS (here): what Pseudo's brain calls for ITSELF and no model ever sees: the memory
    search and save (M24), the look-at chip and the memory browser (M42).
A tool pseudo_hands publishes that is in neither list is offered to nobody and can't be called.
"""

import tomllib
from pathlib import Path

from pseudo_brain.providers import PROVIDERS_FILE, ProviderRefused

BRAIN_TOOLS = ("search_memories", "save_memory", "looking_at", "list_memories", "open_memory")
MEMORY_TOOLS = ("search_memories", "save_memory")  # (M24) memory is on only when pseudo_hands publishes both


def load_model_tools(path: Path = PROVIDERS_FILE) -> tuple[str, ...]:
    """providers.toml's model_tools, checked. Raises ProviderRefused on the first problem."""
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise ProviderRefused(f"can't read {path.name} ({type(error).__name__})") from None
    tools = data.get("model_tools")
    if not isinstance(tools, list) or not all(isinstance(tool, str) and tool for tool in tools):
        raise ProviderRefused("model_tools must be a list of tool names, in quotes (D29)")
    if len(set(tools)) != len(tools):
        raise ProviderRefused("model_tools names a tool twice")
    brain_only = [tool for tool in tools if tool in BRAIN_TOOLS]
    if brain_only:
        raise ProviderRefused(f"model_tools: {', '.join(brain_only)} is brain-only; no model may be offered it (D29)")
    return tuple(tools)
