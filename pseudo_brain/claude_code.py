"""M30: one action request, answered by Claude Code (D26).

What it demonstrates: using ANOTHER agent as a brain, as a child process. In M29 Claude Sonnet
turned 18 of 18 held-out action requests into a usable popup; no free Groq model passed. So a
request to act on a window is handed to `claude -p` (Claude Code's one-shot mode), which is an
agent loop of its own: it calls tools and answers, like loop.py does with Groq.

What keeps it inside Pseudo's rules:
  - The billing check runs first (claude_billing.py). Not clean -> nothing is launched.
  - Claude Code gets its OWN pseudo_hands (a fresh process) publishing only the tools listed in
    providers.toml. --strict-mcp-config ignores every other MCP server you have configured,
    and --tools "" removes Claude Code's built-in tools (no file reads, no shell).
  - Pseudo's own SYSTEM_PROMPT replaces Claude Code's, so both brains get the same instructions.
  - The session is checked as it starts: exactly those tools, no API key in use, the model
    asked for. Anything else stops it before a tool runs.
  - At most MAX_ITERATIONS tool calls and timeout_seconds per question (CLAUDE.md section 6).
  - Privacy, refusals and the approval popup are untouched: they live in pseudo_hands' core
    (D11, D13), and this pseudo_hands is the same code as pseudo_brain's own.
Like loop.py it never prints: it reports the same events (sending, tool_call, tool_result,
answer, failed), plus hands_pid so the face can let THIS pseudo_hands bring its popup forward.
It keeps no history: each request is sent alone (the measured way; a warm session is M31).
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import anyio
import psutil
from anyio.streams.buffered import BufferedByteReceiveStream

from pseudo_brain import claude_billing
from pseudo_brain.action_brain import ActionBrain
from pseudo_brain.hands import HANDS_MODULE, REPO_ROOT, find_hands_pid
from pseudo_brain.loop import MAX_ITERATIONS, SYSTEM_PROMPT, EventSink, TurnResult, fail

SERVER_NAME = "pseudo_hands"
PREFIX = f"mcp__{SERVER_NAME}__"  # how Claude Code names an MCP server's tools
WORK_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Pseudo" / "claude_code"  # empty: no CLAUDE.md
MAX_LINE = 2_000_000  # one line of Claude Code's output (a tool result is at most a few thousand characters)


def write_config(brain: ActionBrain) -> Path:
    """The one MCP server Claude Code may use: pseudo_hands, publishing only the action brain's tools."""
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    server = {"type": "stdio", "command": sys.executable,
              "args": ["-m", HANDS_MODULE, "--tools", ",".join(brain.tools)], "env": {"PYTHONPATH": str(REPO_ROOT)}}
    path = WORK_DIR / "hands.json"
    path.write_text(json.dumps({"mcpServers": {SERVER_NAME: server}}), encoding="utf-8")
    return path


def command_line(program: list[str], brain: ActionBrain, config: Path, system_prompt: str) -> list[str]:
    """The question itself is NOT here: it goes in through stdin, so it can never be read as an option."""
    return [*program, "-p", "--strict-mcp-config", "--mcp-config", str(config), "--tools", "",
            "--allowedTools", *[PREFIX + tool for tool in brain.tools], "--system-prompt", system_prompt,
            "--model", brain.model, "--max-turns", str(MAX_ITERATIONS), "--output-format", "stream-json",
            "--verbose", "--no-session-persistence"]


def session_problem(init: dict, brain: ActionBrain) -> str:
    """'' if Claude Code started the way D26 says; else what is wrong (names only)."""
    if set(init.get("tools") or []) != {PREFIX + tool for tool in brain.tools}:
        return "it started with other tools than the ones in providers.toml"
    if init.get("apiKeySource") != "none":
        return "it isn't using the subscription login"
    if brain.model not in str(init.get("model", "")):
        return "it started on another model"
    return ""


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


def blocks(event: dict, kind: str) -> list[dict]:
    message = event.get("message") if isinstance(event.get("message"), dict) else {}
    content = message.get("content")
    return [b for b in content if isinstance(b, dict) and b.get("type") == kind] if isinstance(content, list) else []


async def ask_claude(brain: ActionBrain, text: str, on_event: EventSink, memories: list[str] = (),
                     intro: str = "") -> TurnResult:
    """One action request through Claude Code. ok=False always means: there is no answer (as in loop.py)."""
    result = TurnResult()
    clean, why = await anyio.to_thread.run_sync(claude_billing.check, brain)
    on_event("billing", {"clean": clean, "line": why})
    if not clean:
        return fail(result, f"{why}. Nothing was sent to {brain.name}, and nothing was done.", on_event)
    prompt = SYSTEM_PROMPT + ("\n\n" + "\n".join([intro, *memories]) if memories else "")
    command = command_line(claude_billing.program(brain), brain, write_config(brain), prompt)
    on_event("sending", {"call": 1, "of": MAX_ITERATIONS, "messages": 1, "tools": len(brain.tools),
                         "estimate": (len(prompt) + len(text)) // 4, "dropped_turns": 0, "memories": len(memories),
                         "provider": brain.id, "model": brain.model})
    try:
        process = await anyio.open_process(command, cwd=str(WORK_DIR), env=claude_billing.child_env(),
                                           stderr=subprocess.DEVNULL,
                                           creationflags=claude_billing.NO_WINDOW)
    except OSError as error:
        return fail(result, f"{brain.name} couldn't be started ({type(error).__name__})", on_event)
    try:
        with anyio.fail_after(brain.timeout_seconds):
            await process.stdin.send(text.encode("utf-8"))
            await process.stdin.aclose()
            return await follow(process, brain, result, on_event)
    except TimeoutError:
        return fail(result, f"{brain.name} didn't finish within {brain.timeout_seconds:.0f} seconds; stopped", on_event)
    finally:
        with anyio.CancelScope(shield=True):  # also when you quit mid-question: never leave it running
            stop_tree(process.pid)
            await process.aclose()


async def follow(process, brain: ActionBrain, result: TurnResult, on_event: EventSink) -> TurnResult:
    """Read Claude Code's output, one JSON event per line, until its result line."""
    lines, names = BufferedByteReceiveStream(process.stdout), {}
    while True:
        try:
            raw = await lines.receive_until(b"\n", MAX_LINE)
            event = json.loads(raw)
        except (anyio.EndOfStream, anyio.IncompleteRead, anyio.DelimiterNotFound):
            return fail(result, f"{brain.name} stopped without an answer", on_event)
        except ValueError:
            continue  # not a JSON line: ignore it
        if event.get("type") == "system" and event.get("subtype") == "init":
            problem = session_problem(event, brain)
            if problem:
                return fail(result, f"{brain.name} was stopped: {problem}", on_event)
            result.model = str(event.get("model", brain.model))
            on_event("hands_pid", {"pid": hands_pid(process.pid)})
        for block in blocks(event, "tool_use"):
            name = str(block.get("name", "")).removeprefix(PREFIX)
            if len(result.tools) >= MAX_ITERATIONS:
                return fail(result, f"stopped after {MAX_ITERATIONS} tool calls without an answer", on_event)
            result.tools.append(name)
            names[block.get("id")] = name
            on_event("tool_call", {"name": name, "arguments": json.dumps(block.get("input") or {})})
        for block in blocks(event, "tool_result"):
            on_event("tool_result", {"name": names.get(block.get("tool_use_id"), ""),
                                     "chars": len(json.dumps(block.get("content") or "")),
                                     "is_error": bool(block.get("is_error"))})
        if event.get("type") == "result":
            return finish(event, brain, result, on_event)


def finish(event: dict, brain: ActionBrain, result: TurnResult, on_event: EventSink) -> TurnResult:
    usage = event.get("usage") or {}
    result.calls = int(event.get("num_turns") or 0)
    result.tokens_in = sum(int(usage.get(key) or 0) for key in ("input_tokens", "cache_read_input_tokens",
                                                                 "cache_creation_input_tokens"))
    result.tokens_out = int(usage.get("output_tokens") or 0)
    if event.get("subtype") != "success" or event.get("is_error"):
        return fail(result, f"{brain.name} ended without an answer ({event.get('subtype')})", on_event)
    result.ok, result.answer = True, str(event.get("result") or "")
    on_event("answer", {"text": result.answer, "calls": result.calls, "tokens_in": result.tokens_in,
                        "tokens_out": result.tokens_out, "provider": brain.id, "model": result.model or brain.model,
                        "fallback": False})
    return result
