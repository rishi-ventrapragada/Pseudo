"""M32: what the warm-session tests share. Claude Code is FAKE (tests/fixtures/fake_claude.py), and the
billing check is replaced and COUNTED, so no test reads .env, the registry or a real login."""

import json
import sys
from pathlib import Path

import psutil
import pytest

from pseudo_brain import claude_billing, claude_code
from pseudo_brain.action_brain import ActionBrain

FAKE = Path(__file__).resolve().parent / "fixtures" / "fake_claude.py"
TOOLS = ("list_open_windows", "read_active_window", "act_on_control")
ONE_REQUEST = ["sending", "hands_pid", "tool_call", "tool_result", "tool_call", "tool_result", "answer"]


def brain(timeout: float = 30.0) -> ActionBrain:
    return ActionBrain("Fake Code", (sys.executable, str(FAKE)), "sonnet", TOOLS, "FAKE_ACCOUNT_VAR", "fake note", timeout)


def fake_world(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict:
    """A world with a fake Claude Code: its record file, the events reported, and how often billing was checked."""
    world: dict = {"clean": True, "checks": 0, "record": tmp_path / "record.json", "events": []}

    def check(_brain: ActionBrain) -> tuple[bool, str]:
        world["checks"] += 1
        return world["clean"], f"billing check: {'CLEAN' if world['clean'] else 'NOT CLEAN'}"

    monkeypatch.setattr(claude_billing, "check", check)
    monkeypatch.setattr(claude_code, "WORK_DIR", tmp_path / "work")
    monkeypatch.setenv("FAKE_CLAUDE_RECORD", str(world["record"]))
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "ok")
    world["on_event"] = lambda kind, data: world["events"].append((kind, data))
    return world


def kinds(world: dict) -> list[str]:
    return [kind for kind, _data in world["events"]]


def recorded(world: dict) -> dict:
    """What the fake wrote down: its arguments, its pid and every question it was sent."""
    return json.loads(world["record"].read_text(encoding="utf-8"))


def fakes_running() -> list[int]:
    """The fake Claude Code processes still running (there should be none after a stop)."""
    return [p.pid for p in psutil.process_iter(["cmdline"]) if str(FAKE) in " ".join(p.info["cmdline"] or [])]
