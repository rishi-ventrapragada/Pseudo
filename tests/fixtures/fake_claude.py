"""A FAKE Claude Code for M30's tests. It talks to nobody and has no tools: it only prints lines
shaped like `claude -p --output-format stream-json`, chosen by FAKE_CLAUDE_MODE.

  python fake_claude.py auth status   -> a fake login, as JSON
  python fake_claude.py -p ...flags   -> reads the question from stdin, prints a fake session

If FAKE_CLAUDE_RECORD names a file, the arguments and the question are written there, so a test
can check exactly how pseudo_brain started it.
"""

import json
import os
import sys
import time

PREFIX = "mcp__pseudo_hands__"
MODE = os.environ.get("FAKE_CLAUDE_MODE", "ok")


def say(event: dict) -> None:
    print(json.dumps(event), flush=True)


def use(number: int, tool: str) -> None:
    say({"type": "assistant", "message": {"content": [
        {"type": "tool_use", "id": f"t{number}", "name": PREFIX + tool, "input": {"n": number}}]}})
    say({"type": "user", "message": {"content": [
        {"type": "tool_result", "tool_use_id": f"t{number}", "content": [{"type": "text", "text": "fake result"}]}]}})


def main() -> int:
    args = sys.argv[1:]
    if args[:2] == ["auth", "status"]:
        say({"loggedIn": True, "authMethod": "claude.ai", "apiProvider": "firstParty", "email": "owner@fake.invalid"})
        return 0
    question = sys.stdin.read()
    if os.environ.get("FAKE_CLAUDE_RECORD"):
        with open(os.environ["FAKE_CLAUDE_RECORD"], "w", encoding="utf-8") as file:
            json.dump({"args": args, "question": question,
                       "env": sorted(k for k in os.environ if k.upper().startswith(("CLAUDE", "ANTHROPIC")))}, file)
    allowed = args[args.index("--allowedTools") + 1:args.index("--system-prompt")]
    init = {"type": "system", "subtype": "init", "tools": allowed, "apiKeySource": "none", "model": "claude-sonnet-fake"}
    if MODE == "extra_tool":
        init["tools"] = allowed + ["Bash"]
    if MODE == "api_key":
        init["apiKeySource"] = "ANTHROPIC_API_KEY"
    if MODE == "other_model":
        init["model"] = "claude-haiku-fake"
    print("a line that is not JSON", flush=True)
    say(init)
    if MODE == "hang":
        time.sleep(60)
    if MODE == "dies":
        return 3
    for number in range(8 if MODE == "too_many" else 1):
        use(number * 2, "read_active_window")
        use(number * 2 + 1, "act_on_control")
    if MODE == "max_turns":
        say({"type": "result", "subtype": "error_max_turns", "is_error": True, "num_turns": 6})
        return 1
    say({"type": "result", "subtype": "success", "is_error": False, "result": "Fake answer: not approved.",
         "num_turns": 3, "usage": {"input_tokens": 6, "cache_read_input_tokens": 7000,
                                   "cache_creation_input_tokens": 1200, "output_tokens": 200}})
    return 0


if __name__ == "__main__":
    sys.exit(main())
