"""M14, M16: the terminal interface for pseudo_brain. A thin wrapper (D11): it prints the
loop's events and reads your questions. Every decision lives in the other files, so
M17's React face can use the same loop through the same events.

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

from pseudo_brain.hands import connect_hands
from pseudo_brain.local_server import ServerFailure
from pseudo_brain.loop import run_turn
from pseudo_brain.model import NO_KEY, ModelFailure, connect_provider
from pseudo_brain.providers import Provider, ProviderRefused, load_allowlist
from pseudo_brain.session import Session, load_latest

REFUSALS = (ProviderRefused, ModelFailure, ServerFailure)  # a provider that can't be used, with the reason


def describe(provider: Provider) -> str:
    """One line: id, name, models, whether data leaves the laptop, and the privacy note."""
    fallback = f", fallback {', '.join(provider.models[1:])}" if len(provider.models) > 1 else ""
    leaves = "YES" if provider.leaves_laptop else "NO"
    return (f"{provider.id} ({provider.name}): {provider.models[0]}{fallback} | "
            f"data leaves this laptop: {leaves} | {provider.privacy}")


def format_event(kind: str, data: dict) -> str | None:
    """One event -> one line of terminal output (None = don't show it)."""
    if kind == "sending":
        trimmed = f" | dropped {data['dropped_turns']} old turn(s) to fit" if data["dropped_turns"] else ""
        return (f"\n--- SENDING TO {data['provider']} · {data['model']} (call {data['call']} of max {data['of']}) | "
                f"{data['messages']} messages + {data['tools']} tools, ~{data['estimate']} tokens{trimmed} ---")
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
    if kind == "tool_call":
        return f"--- MODEL WANTS TO CALL TOOL: {data['name']} {data['arguments'] or '{}'} ---"
    if kind == "tool_result":
        error = " (ERROR)" if data["is_error"] else ""
        return f"--- TOOL RESULT{error}: {data['chars']} chars, sent to the model, kept in memory only ---"
    if kind == "answer":
        label = f"{data['provider']} · {data['model']}" + (", fallback" if data["fallback"] else "")
        return (f"\n--- ANSWER ({label} | {data['calls']} model call(s), {data['tokens_in']} tokens in / "
                f"{data['tokens_out']} out) ---\npseudo> {data['text'] or '(empty answer)'}")
    if kind == "failed":
        return f"\n--- FAILED: {data['reason']}. No answer was produced. ---"
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


async def use(provider: Provider, servers: dict, secrets: list[str], show):
    """Connect to a provider (starting its server if it has one) and say so. Raises one of REFUSALS."""
    model = await connect_provider(provider, servers, show)
    if model.client.api_key != NO_KEY:
        secrets.append(model.client.api_key)
    print(f"--- PROVIDER {describe(provider)} ---")
    return model


async def chat(resume: bool, wanted: str | None) -> int:
    allowlist = load_allowlist()
    session = load_latest() if resume else None
    if session and wanted and wanted != session.provider:
        raise ProviderRefused(f"the latest session belongs to {session.provider}, and a session never changes "
                              f"provider; leave out --continue to start a new one on {wanted}")
    provider = allowlist.get(session.provider if session else wanted or allowlist.default)
    session = session or Session(provider=provider.id)
    secrets: list[str] = []
    show, servers = printer(secrets), {}
    try:
        model = await use(provider, servers, secrets, show)
        print(f"--- SESSION {session.started} | provider: {provider.id} | {len(session.turns)} earlier turn(s) loaded ---")
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
                    session = Session(provider=model.provider.id)
                    print(f"--- NEW SESSION {session.started} | provider: {model.provider.id} ---")
                elif text == "/provider":
                    print(f"--- ALLOWED PROVIDERS ({allowlist.providers[model.provider.id].name} is in use) ---")
                    for listed in allowlist.providers.values():
                        print(f" {'*' if listed.id == model.provider.id else ' '} {describe(listed)}")
                elif text.startswith("/provider "):
                    try:
                        chosen = allowlist.get(text.split(maxsplit=1)[1])
                        if chosen.id == model.provider.id:
                            print(f"--- ALREADY USING {chosen.id} ---")
                            continue
                        model = await use(chosen, servers, secrets, show)
                    except REFUSALS as refusal:
                        print(f"--- REFUSED: {refusal}. Still on {model.provider.id}. ---")
                        continue
                    session = Session(provider=chosen.id)
                    print(f"--- SWITCHED TO {chosen.id}: NEW SESSION {session.started} (a session keeps one provider) ---")
                elif text:
                    await run_turn(session, text, model, hands, show)
                    session.save()  # after every turn, so nothing is lost if the window closes
        if session.turns:
            print(f"\n--- SESSION SAVED: {session.save()} (your messages and final answers only) ---")
    finally:
        for server in servers.values():
            if server.stop():
                print(f"--- STOPPED the {server.provider.id} server (Pseudo started it) ---")
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
