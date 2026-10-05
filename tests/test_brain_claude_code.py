"""M30: one action request through Claude Code (pseudo_brain/claude_code.py).

Claude Code here is FAKE (tests/fixtures/fake_claude.py): a small script that prints lines shaped
like Claude Code's, talks to nobody and starts no pseudo_hands. The billing check is replaced, so
no test reads .env, the registry or a real login. What is real: starting a child process, sending
the question through stdin, reading its lines, the caps, and stopping it.
"""

import json
import sys
import time
from pathlib import Path

import psutil
import pytest

from pseudo_brain import claude_billing, claude_code
from pseudo_brain.action_brain import ActionBrain
from pseudo_brain.claude_code import ask_claude
from pseudo_brain.loop import MAX_ITERATIONS, SYSTEM_PROMPT

FAKE = Path(__file__).resolve().parent / "fixtures" / "fake_claude.py"
TOOLS = ("list_open_windows", "read_active_window", "act_on_control")
QUESTION = "--help; tick the fake box"  # starts like an option on purpose


def brain(timeout: float = 30.0) -> ActionBrain:
    return ActionBrain("Fake Code", (sys.executable, str(FAKE)), "sonnet", TOOLS, "FAKE_ACCOUNT_VAR", "fake note", timeout)


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict:
    world = {"clean": True, "record": tmp_path / "record.json", "events": []}
    monkeypatch.setattr(claude_billing, "check",
                        lambda b: (world["clean"], f"billing check: {'CLEAN' if world['clean'] else 'NOT CLEAN'}"))
    monkeypatch.setattr(claude_code, "WORK_DIR", tmp_path / "work")
    monkeypatch.setenv("FAKE_CLAUDE_RECORD", str(world["record"]))
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "ok")
    world["on_event"] = lambda kind, data: world["events"].append((kind, data))
    return world


def kinds(world: dict) -> list[str]:
    return [kind for kind, _data in world["events"]]


@pytest.mark.anyio
async def test_an_action_request_is_answered_and_reported_like_the_loop_does(world: dict) -> None:
    result = await ask_claude(brain(), QUESTION, world["on_event"])
    assert result.ok and result.answer == "Fake answer: not approved." and result.model == "claude-sonnet-fake"
    assert result.tools == ["read_active_window", "act_on_control"]
    assert (result.tokens_in, result.tokens_out, result.calls) == (8206, 200, 3)
    assert kinds(world) == ["billing", "sending", "hands_pid", "tool_call", "tool_result", "tool_call", "tool_result",
                            "answer"]
    answer = world["events"][-1][1]
    assert (answer["provider"], answer["model"], answer["fallback"]) == ("claude-code", "claude-sonnet-fake", False)
    assert "fake result" not in json.dumps([data for kind, data in world["events"] if kind != "answer"])


@pytest.mark.anyio
async def test_it_is_started_with_only_pseudos_tools_and_the_question_goes_through_stdin(world: dict) -> None:
    await ask_claude(brain(), QUESTION, world["on_event"], memories=["a fake memory"], intro="Notes:")
    record = json.loads(world["record"].read_text(encoding="utf-8"))
    args = record["args"]
    assert record["question"] == QUESTION and QUESTION not in args
    assert args[0] == "-p" and "--strict-mcp-config" in args and "--no-session-persistence" in args
    assert args[args.index("--tools") + 1] == ""  # no built-in tools
    assert args[args.index("--max-turns") + 1] == str(MAX_ITERATIONS) and args[args.index("--model") + 1] == "sonnet"
    allowed = args[args.index("--allowedTools") + 1:args.index("--system-prompt")]
    assert allowed == ["mcp__pseudo_hands__" + tool for tool in TOOLS]
    assert args[args.index("--system-prompt") + 1] == SYSTEM_PROMPT + "\n\nNotes:\na fake memory"
    assert record["env"] == ["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"]  # nothing that could outrank the login
    config = json.loads(Path(args[args.index("--mcp-config") + 1]).read_text(encoding="utf-8"))
    server = config["mcpServers"]["pseudo_hands"]
    assert list(config["mcpServers"]) == ["pseudo_hands"]
    assert server["args"] == ["-m", "pseudo_hands.mcp_server", "--tools", ",".join(TOOLS)]


@pytest.mark.anyio
async def test_a_billing_check_that_isnt_clean_launches_nothing(world: dict) -> None:
    world["clean"] = False
    result = await ask_claude(brain(), QUESTION, world["on_event"])
    assert not result.ok and result.answer is None and "NOT CLEAN" in result.reason
    assert "Nothing was sent" in result.reason and kinds(world) == ["billing", "failed"]
    assert not world["record"].exists()


@pytest.mark.anyio
@pytest.mark.parametrize("mode, reason", [
    ("extra_tool", "other tools than the ones in providers.toml"),
    ("api_key", "isn't using the subscription login"),
    ("other_model", "another model"),
    ("dies", "stopped without an answer"),
    ("max_turns", "ended without an answer"),
    ("too_many", f"stopped after {MAX_ITERATIONS} tool calls"),
])
async def test_anything_unexpected_ends_without_an_answer(world: dict, monkeypatch: pytest.MonkeyPatch,
                                                           mode: str, reason: str) -> None:
    monkeypatch.setenv("FAKE_CLAUDE_MODE", mode)
    result = await ask_claude(brain(), QUESTION, world["on_event"])
    assert not result.ok and result.answer is None and reason in result.reason
    assert kinds(world)[-1] == "failed" and "answer" not in kinds(world)
    if mode in ("extra_tool", "api_key", "other_model"):
        assert "tool_call" not in kinds(world)  # stopped before any tool ran
    if mode == "too_many":
        assert kinds(world).count("tool_call") == MAX_ITERATIONS


@pytest.mark.anyio
async def test_a_hung_claude_code_is_stopped_and_not_left_running(world: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "hang")
    started = time.monotonic()
    result = await ask_claude(brain(timeout=3.0), QUESTION, world["on_event"])
    assert not result.ok and "didn't finish within 3 seconds" in result.reason and time.monotonic() - started < 20
    left = [p for p in psutil.process_iter(["cmdline"]) if str(FAKE) in " ".join(p.info["cmdline"] or [])]
    assert left == []


@pytest.mark.anyio
async def test_a_program_that_cant_start_is_a_visible_failure(world: dict, monkeypatch: pytest.MonkeyPatch,
                                                              tmp_path: Path) -> None:
    monkeypatch.setattr(claude_billing, "program", lambda b: [str(tmp_path / "no-such-program.exe")])
    result = await ask_claude(brain(), QUESTION, world["on_event"])
    assert not result.ok and "couldn't be started" in result.reason
