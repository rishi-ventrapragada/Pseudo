"""M14: the terminal interface for pseudo_brain. A thin wrapper (D11): it prints the
loop's events and reads your questions. Every decision lives in loop.py, so M15's
React face can use the same loop through the same events.

Run it from the repo root:
    python -m pseudo_brain               start a new session
    python -m pseudo_brain --continue    continue the latest saved session
In the chat: /new starts a fresh session, /quit (or Ctrl+C, or end of input) quits.

What you see: every model call, the tokens it cost, rate-limit waits, the tools the
model calls and the SIZE of each result. Never a tool result's text: that goes to the
model and stays in memory (M14 safety rule).
"""

import sys

import anyio

from pseudo_brain.hands import connect_hands
from pseudo_brain.loop import run_turn
from pseudo_brain.model import Model, ModelFailure, load_settings
from pseudo_brain.session import Session, load_latest


def format_event(kind: str, data: dict) -> str | None:
    """One loop event -> one line of terminal output (None = don't show it)."""
    if kind == "sending":
        trimmed = f" | dropped {data['dropped_turns']} old turn(s) to fit" if data["dropped_turns"] else ""
        return (f"\n--- SENDING TO MODEL (call {data['call']} of max {data['of']}) | {data['messages']} messages"
                f" + {data['tools']} tools, ~{data['estimate']} tokens{trimmed} ---")
    if kind == "tokens":
        return (f"tokens: {data['in']} in / {data['out']} out (estimated ~{data['estimate']} in) | Groq budget "
                f"left this minute: {data['budget_left'] or '?'} of {data['budget'] or '?'}")
    if kind == "rate_limited":
        return (f"--- RATE LIMITED (429): waiting {data['seconds']:.0f} s as Groq asked "
                f"(wait {data['wait']} of {data['of']}) ---")
    if kind == "model_retry":
        return "--- MODEL WROTE AN INVALID TOOL CALL (400): asking again ---"
    if kind == "tool_call":
        return f"--- MODEL WANTS TO CALL TOOL: {data['name']} {data['arguments'] or '{}'} ---"
    if kind == "tool_result":
        error = " (ERROR)" if data["is_error"] else ""
        return f"--- TOOL RESULT{error}: {data['chars']} chars, sent to the model, kept in memory only ---"
    if kind == "answer":
        return (f"\n--- ANSWER ({data['calls']} model call(s), {data['tokens_in']} tokens in / "
                f"{data['tokens_out']} out) ---\npseudo> {data['text'] or '(empty answer)'}")
    if kind == "failed":
        return f"\n--- FAILED: {data['reason']}. No answer was produced. ---"
    return None


def printer(api_key: str):
    """The terminal's on_event: format, hide the key if it ever appears, print."""
    def show(kind: str, data: dict) -> None:
        line = format_event(kind, data)
        if line:
            print(line.replace(api_key, "<hidden>"), flush=True)
    return show


async def ask(prompt: str) -> str:
    """input() in a helper thread, so the MCP connection keeps running while you type."""
    return await anyio.to_thread.run_sync(input, prompt, abandon_on_cancel=True)


async def chat(resume: bool) -> int:
    settings = load_settings()
    model, show = Model(settings), printer(settings.api_key)
    session = (load_latest() if resume else None) or Session()
    print(f"--- SESSION {session.started}: {len(session.turns)} earlier turn(s) loaded ---")
    print("--- CONNECTING TO pseudo_hands (MCP over stdio) ---", flush=True)
    async with connect_hands() as hands:
        print(f"--- CONNECTED: {len(hands.names)} tools discovered: {', '.join(hands.names)} ---")
        while True:
            try:
                text = (await ask("\nyou> ")).strip()
            except EOFError:  # end of piped input
                break
            if text in ("/quit", "/exit"):
                break
            if text == "/new":
                session = Session()
                print(f"--- NEW SESSION {session.started} ---")
                continue
            if text:
                await run_turn(session, text, model, hands, show)
                session.save()  # after every turn, so nothing is lost if the window closes
    if session.turns:
        print(f"\n--- SESSION SAVED: {session.save()} (your messages and final answers only) ---")
    return 0


def main() -> int:
    try:
        return anyio.run(chat, "--continue" in sys.argv[1:])
    except ModelFailure as failure:  # only load_settings raises it outside a turn
        print(f"--- CANNOT START: {failure} ---")
        return 1
    except KeyboardInterrupt:
        print("\nStopped by you. (Your last finished turn was already saved.)")
        return 1
