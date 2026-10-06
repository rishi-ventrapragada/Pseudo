"""M14, M16: the terminal interface for pseudo_brain. A thin wrapper (D11): it prints the
loop's events and reads your questions. Every decision lives in the other files. Since
M18 the provider and session rules live in chat.py, shared with the face (bridge.py).

Run it from the repo root:
    python -m pseudo_brain                    a new session on the default provider (providers.toml)
    python -m pseudo_brain --provider local   a new session in private mode: nothing leaves this laptop
    python -m pseudo_brain --continue         continue the latest saved session, on ITS provider
In the chat:
    /provider        list the allowed providers (D16), with their privacy notes
    /provider <id>   switch provider; this starts a new session (a session keeps one provider)
    /new             start a fresh session on the same provider
    /quit            quit (so do Ctrl+C and end of input); a server Pseudo started is stopped

What you see: which provider and model make every call, the tokens they cost, rate-limit
waits and fallbacks, the tools the model calls and the SIZE of each result. Never a tool
result's text: that goes to the model and stays in memory (M14 safety rule).
"""

import argparse

import anyio

from pseudo_brain.action_brain import load_routing
from pseudo_brain.chat import REFUSALS, Chat
from pseudo_brain.hands import connect_hands
from pseudo_brain.providers import Provider, load_allowlist

COMMANDS = "/provider, /provider <id>, /new, /quit"
BOM = "﻿"  # an invisible mark PowerShell puts at the start of piped text (found in M16's checks)


def describe(provider: Provider) -> str:
    """One line: id, name, models, whether data leaves the laptop, and the privacy note."""
    fallback = f", fallback {', '.join(provider.models[1:])}" if len(provider.models) > 1 else ""
    leaves = "YES" if provider.leaves_laptop else "NO"
    off = f" | DISABLED: {provider.disabled}" if provider.disabled else ""
    return (f"{provider.id} ({provider.name}): {provider.models[0]}{fallback} | "
            f"data leaves this laptop: {leaves} | {provider.privacy}{off}")


def format_event(kind: str, data: dict) -> str | None:
    """One event -> one line of terminal output (None = don't show it)."""
    if kind == "sending":
        trimmed = f" | dropped {data['dropped_turns']} old turn(s) to fit" if data["dropped_turns"] else ""
        memories = f" | {data['memories']} memory(ies)" if data.get("memories") else ""
        return (f"\n--- SENDING TO {data['provider']} · {data['model']} (call {data['call']} of max {data['of']}) | "
                f"{data['messages']} messages + {data['tools']} tools, ~{data['estimate']} tokens{memories}{trimmed} ---")
    if kind == "tokens":
        budget = (f"budget left this minute: {data['budget_left']} of {data['budget'] or '?'}"
                  if data["budget_left"] else "no rate-limit info")
        return f"tokens: {data['in']} in / {data['out']} out (estimated ~{data['estimate']} in) | {budget}"
    if kind == "fallback":
        return (f"--- RATE LIMITED (429) on {data['from']}: switching to {data['to']} "
                f"(the next model of {data['provider']}; never another provider) ---")
    if kind == "rate_limited":
        return (f"--- RATE LIMITED (429) on {data['model']}: waiting {data['seconds']:.0f} s as {data['provider']} "
                f"asked (wait {data['wait']} of {data['of']}) ---")
    if kind == "model_retry":
        return "--- MODEL WROTE AN INVALID TOOL CALL (400): asking again ---"
    if kind == "tool_call" and data.get("by") == "pseudo":  # (M24) Pseudo's own call, not the model's
        return "--- SAVING TO MEMORY: the approval popup asks you first (redacted; default no) ---"
    if kind == "tool_call":
        return f"--- MODEL WANTS TO CALL TOOL: {data['name']} {data['arguments'] or '{}'} ---"
    if kind == "tool_result" and data.get("by") == "pseudo":
        return None  # memory_saved / memory_not_saved says how it went
    if kind == "tool_result":
        error = " (ERROR)" if data["is_error"] else ""
        return f"--- TOOL RESULT{error}: {data['chars']} chars, sent to the model, kept in memory only ---"
    if kind == "answer":
        label = f"{data['provider']} · {data['model']}" + (", fallback" if data["fallback"] else "")
        return (f"\n--- ANSWER ({label} | {data['calls']} model call(s), {data['tokens_in']} tokens in / "
                f"{data['tokens_out']} out) ---\npseudo> {data['text'] or '(empty answer)'}")
    if kind == "failed":
        return f"\n--- FAILED: {data['reason']}. No answer was produced. ---"
    if kind == "memories":
        if data["count"]:
            return f"--- MEMORY: {data['count']} past task(s) added to this question ({data['chars']} chars, redacted) ---"
        return f"--- MEMORY: none added ({data['note']}) ---"
    if kind == "routed":  # (M30)
        return (f"\n--- ACTION REQUEST: going to {data['name']} ({data['model']}), not the chat provider | "
                f"{data['privacy']} ---")
    if kind == "billing":  # (M30) names and booleans only
        return f"--- {data['line']} ---"
    if kind == "launch":  # (M32) the four steps of warm_sessions.py; the face words them the same (events.ts)
        return f"--- LAUNCH: starting Claude Code for this request ({data['why']}) ---"
    if kind == "warm":
        return f"--- WARM SESSION: request {data['request']} of {data['of']} in the open Claude Code session ---"
    if kind == "warm_restart":
        return f"--- WARM SESSION: restarting it after this request ({data['why']}) ---"
    if kind == "warm_opened":
        if data["opened"]:
            return f"--- WARM SESSION: opened for your next action requests (restarted after {data['of']}) ---"
        return f"--- WARM SESSION: not opened ({data['why']}) ---"
    if kind == "memory_saved":
        return f"--- MEMORY: saved this task, redacted, as {data['note']} ---"
    if kind == "memory_not_saved":
        return f"--- MEMORY: not saved ({data['reason']}) ---"
    if kind == "server_starting":
        return f"--- PRIVATE SERVER for {data['provider']}: checking cloud is off, then starting it on {data['address']} ---"
    if kind == "server_ready":
        if data["started_by_us"]:
            return (f"--- SERVER READY on {data['address']} in {data['seconds']:.1f} s "
                    "(started by Pseudo; stopped when Pseudo exits) ---")
        return f"--- SERVER FOUND on {data['address']}: already running, not started by Pseudo, so Pseudo won't stop it ---"
    return None


def printer(secrets: list[str]):
    """The terminal's on_event: format, hide every key if one ever appears, print."""
    def show(kind: str, data: dict) -> None:
        line = format_event(kind, data)
        if line:
            for secret in secrets:
                line = line.replace(secret, "<hidden>")
            print(line, flush=True)
    return show


async def ask(prompt: str) -> str:
    """input() in a helper thread, so the MCP connection keeps running while you type."""
    return await anyio.to_thread.run_sync(input, prompt, abandon_on_cancel=True)


async def chat(resume: bool, wanted: str | None) -> int:
    secrets: list[str] = []  # every key in use (Chat fills it); hidden in every printed line
    conversation = Chat(load_allowlist(), printer(secrets), secrets, load_routing())
    try:
        await conversation.start(resume, wanted)
        print(f"--- PROVIDER {describe(conversation.provider)} ---")
        print(f"--- SESSION {conversation.session.started} | provider: {conversation.provider.id} | "
              f"{len(conversation.session.turns)} earlier turn(s) loaded ---")
        print("--- CONNECTING TO pseudo_hands (MCP over stdio) ---", flush=True)
        async with connect_hands() as hands:
            print(f"--- CONNECTED: {len(hands.names)} tools discovered: {', '.join(hands.names)} ---")
            while True:
                try:
                    text = (await ask("\nyou> ")).replace(BOM, "").strip()
                except EOFError:  # end of piped input
                    break
                if text in ("/quit", "/exit"):
                    break
                if text == "/new":
                    conversation.new_session()
                    print(f"--- NEW SESSION {conversation.session.started} | provider: {conversation.provider.id} ---")
                elif text == "/provider":
                    print(f"--- ALLOWED PROVIDERS ({conversation.provider.name} is in use) ---")
                    for listed in conversation.allowlist.providers.values():
                        print(f" {'*' if listed.id == conversation.provider.id else ' '} {describe(listed)}")
                elif text.startswith("/provider "):
                    try:
                        switched = await conversation.switch(text.split(maxsplit=1)[1])
                    except REFUSALS as refusal:
                        print(f"--- REFUSED: {refusal}. Still on {conversation.provider.id}. ---")
                        continue
                    if not switched:
                        print(f"--- ALREADY USING {conversation.provider.id} ---")
                        continue
                    print(f"--- PROVIDER {describe(conversation.provider)} ---")
                    print(f"--- SWITCHED TO {conversation.provider.id}: NEW SESSION {conversation.session.started} "
                          "(a session keeps one provider) ---")
                elif text.startswith("/"):  # a mistyped command must never reach the model as a question
                    print(f"--- UNKNOWN COMMAND {text.split()[0]}: nothing was sent. Commands: {COMMANDS} ---")
                elif text:
                    await conversation.ask(text, hands)  # saved after every turn, so nothing is lost
        if conversation.session.turns:
            print(f"\n--- SESSION SAVED: {conversation.session.save()} (your messages and final answers only) ---")
    finally:
        for provider_id in conversation.close():
            print(f"--- STOPPED the {provider_id} server (Pseudo started it) ---")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m pseudo_brain", description="Pseudo's own brain (M14, M16).")
    parser.add_argument("--continue", dest="resume", action="store_true",
                        help="continue the latest saved session, on its own provider")
    parser.add_argument("--provider", help="start a new session on this provider from providers.toml")
    args = parser.parse_args()
    try:
        return anyio.run(chat, args.resume, args.provider)
    except REFUSALS as failure:  # a bad allowlist, a missing key, or a provider that can't be used
        print(f"--- CANNOT START: {failure} ---")
        return 1
    except KeyboardInterrupt:
        print("\nStopped by you. (Your last finished turn was already saved.)")
        return 1
