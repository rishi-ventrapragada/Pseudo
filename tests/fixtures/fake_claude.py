"""A FAKE Claude Code for M30's and M32's tests. It talks to nobody and has no tools: it only prints
lines shaped like `claude -p --output-format stream-json`, chosen by FAKE_CLAUDE_MODE.

  python fake_claude.py auth status   -> a fake login, as JSON
  python fake_claude.py -p ...flags   -> a LAUNCH: reads the question from stdin, prints one fake request
  ... --input-format stream-json      -> (M32) a WARM session: one JSON line per request on stdin, answered
                                         one after the other by this same process, until stdin is closed

FAKE_CLAUDE_MODE    what goes wrong ("ok": nothing). In a warm session it applies to request number
                    FAKE_CLAUDE_AT (default 1) only; "stuck" applies when stdin is closed.
FAKE_CLAUDE_INPUTS  "7000,9000,21000": the input tokens of request 1, 2, 3... (the last one repeats).
                    Default: 8206 for every request.
FAKE_CLAUDE_RECORD  a file that gets this process's arguments, its pid and every question so far, so a
                    test can check exactly how pseudo_brain started it and what it was sent.
"""

import json
import os
import sys
import time

PREFIX = "mcp__pseudo_hands__"
MODE = os.environ.get("FAKE_CLAUDE_MODE", "ok")
AT = int(os.environ.get("FAKE_CLAUDE_AT", "1"))
INPUTS = [int(n) for n in os.environ.get("FAKE_CLAUDE_INPUTS", "8206").split(",")]
CACHE_WRITTEN = 1200


def say(event: dict) -> None:
    print(json.dumps(event), flush=True)


def use(number: int, tool: str) -> None:
    say({"type": "assistant", "message": {"content": [
        {"type": "tool_use", "id": f"t{number}", "name": PREFIX + tool, "input": {"n": number}}]}})
    say({"type": "user", "message": {"content": [
        {"type": "tool_result", "tool_use_id": f"t{number}", "content": [{"type": "text", "text": "fake result"}]}]}})


def record(args: list[str], questions: list[str]) -> None:
    if os.environ.get("FAKE_CLAUDE_RECORD"):
        with open(os.environ["FAKE_CLAUDE_RECORD"], "w", encoding="utf-8") as file:
            json.dump({"args": args, "question": questions[-1], "questions": questions, "pid": os.getpid(),
                       "env": sorted(k for k in os.environ if k.upper().startswith(("CLAUDE", "ANTHROPIC")))}, file)


def answer(number: int, allowed: list[str], tag: str = "") -> int | None:
    """Print one request's lines. Returns an exit code if the fake ends here, else None.

    `tag` goes into the answer, so a warm session's answers can be told apart ("Fake answer 2: ...")."""
    mode = MODE if number == AT else "ok"
    init = {"type": "system", "subtype": "init", "tools": allowed, "apiKeySource": "none", "model": "claude-sonnet-fake"}
    if mode == "extra_tool":
        init["tools"] = allowed + ["Bash"]
    if mode == "api_key":
        init["apiKeySource"] = "ANTHROPIC_API_KEY"
    if mode == "other_model":
        init["model"] = "claude-haiku-fake"
    print("a line that is not JSON", flush=True)
    say(init)  # Claude Code prints an init line for EVERY request, also in a warm session (M31)
    if mode == "hang":
        time.sleep(60)
    if mode == "slow":  # answers, but only after a while: time for a test to do something meanwhile
        time.sleep(1.5)
    if mode == "dies":
        return 3
    for step in range(8 if mode == "too_many" else 1):
        use(step * 2, "read_active_window")
        use(step * 2 + 1, "act_on_control")
    if mode == "max_turns":
        say({"type": "result", "subtype": "error_max_turns", "is_error": True, "num_turns": 6})
        return 1
    total = INPUTS[min(number, len(INPUTS)) - 1]
    say({"type": "result", "subtype": "success", "is_error": False, "result": f"Fake answer{tag}: not approved.",
         "num_turns": 3, "usage": {"input_tokens": 6, "cache_read_input_tokens": total - CACHE_WRITTEN - 6,
                                   "cache_creation_input_tokens": CACHE_WRITTEN, "output_tokens": 200}})
    return None


def main() -> int:
    args = sys.argv[1:]
    if args[:2] == ["auth", "status"]:
        say({"loggedIn": True, "authMethod": "claude.ai", "apiProvider": "firstParty", "email": "owner@fake.invalid"})
        return 0
    allowed = args[args.index("--allowedTools") + 1:args.index("--system-prompt")]
    if "--input-format" not in args:  # a launch: the whole of stdin is the one question
        record(args, [sys.stdin.read()])
        return answer(1, allowed) or 0
    questions: list[str] = []
    record(args, [""])  # a session that was started but never asked still leaves its arguments
    for line in sys.stdin:  # a warm session: one request per line, until our input is closed
        if line.strip():
            questions.append(json.loads(line)["message"]["content"][0]["text"])
            record(args, questions)
            code = answer(len(questions), allowed, f" {len(questions)}")
            if code is not None:
                return code
    if MODE == "stuck":  # a session that doesn't end when its input is closed: it has to be killed
        time.sleep(60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
