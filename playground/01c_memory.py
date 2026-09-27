"""M1c: a terminal chat, and the proof that the model has no memory.

What it demonstrates: the model is stateless. It remembers nothing between
calls. The "memory" in every chat app is the program keeping a list of
messages and re-sending the whole list on every turn.

Concepts it teaches: conversation history, the "assistant" role, the context
growing (and costing more tokens) each turn, and what "forgetting" really is.

Run it:  python playground/01c_memory.py                (history ON)
         python playground/01c_memory.py --no-history   (watch it forget)
"""

import argparse
import os
import sys
from pathlib import Path

import openai
from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
SYSTEM_PROMPT = "You are a concise assistant. Answer in one or two short sentences."
MAX_TURNS = 20  # hard cap, so a forgotten chat can't burn the free-tier budget


def load_config() -> tuple[str, str, str]:
    """Read the three LLM_* settings from .env, or stop with a clear message."""
    load_dotenv(ENV_PATH)
    base_url = os.getenv("LLM_BASE_URL")
    api_key = os.getenv("LLM_API_KEY")
    model = os.getenv("LLM_MODEL")
    if not (base_url and api_key and model):
        sys.exit("Missing LLM_BASE_URL, LLM_API_KEY or LLM_MODEL. Run playground/00_check_setup.py")
    return base_url, api_key, model


def hide_key(text: str, api_key: str) -> str:
    """Belt and braces: blank out the key if it ever shows up in text we print."""
    return text.replace(api_key, "<hidden>")


def print_messages(messages: list[dict], api_key: str) -> None:
    """Show exactly what is about to be sent, one line per message."""
    for message in messages:
        print(hide_key(f"  [{message['role']}] {message['content']}", api_key))


def main() -> int:
    parser = argparse.ArgumentParser(description="Terminal chat with a history on/off switch.")
    parser.add_argument("--no-history", action="store_true", help="send only the latest message")
    use_history = not parser.parse_args().no_history

    base_url, api_key, model = load_config()
    client = openai.OpenAI(base_url=base_url, api_key=api_key, max_retries=0, timeout=60)

    # THE MEMORY. It's just a Python list living in this program.
    # The model never sees any of it unless we send it.
    history = [{"role": "system", "content": SYSTEM_PROMPT}]

    print(f"=== Chat (history {'ON' if use_history else 'OFF'}, max {MAX_TURNS} turns). Type 'quit' to exit ===")
    turns = 0
    while turns < MAX_TURNS:
        try:
            user_text = input("\nyou> ").strip()
        except (EOFError, KeyboardInterrupt):  # Ctrl+C, or the end of piped input
            print()
            break
        if user_text.lower() in ("quit", "exit"):
            break
        if not user_text:
            continue

        user_message = {"role": "user", "content": user_text}
        if use_history:
            history.append(user_message)
            messages = history
        else:
            # The ONLY difference in no-history mode: send the system prompt
            # plus this one message. Everything earlier is simply not sent.
            messages = [history[0], user_message]

        label = "" if use_history else " (history OFF)"
        print(f"--- SENDING TO MODEL: {len(messages)} messages{label} ---")
        print_messages(messages, api_key)

        try:
            completion = client.chat.completions.create(model=model, messages=messages)
        except openai.APIError as error:  # bad key, rate limit, network...
            print(hide_key(f"--- ERROR: {error} ---", api_key))
            return 1

        reply = completion.choices[0].message.content or ""
        usage = completion.usage
        print(f"--- MODEL REPLY (tokens: {usage.prompt_tokens} in, {usage.completion_tokens} out) ---")
        print(hide_key(f"assistant> {reply}", api_key))

        # Save the reply too, so on the next turn the model can "see" what it said.
        if use_history:
            history.append({"role": "assistant", "content": reply})
        turns += 1

    if turns == MAX_TURNS:
        print(f"\n(Reached MAX_TURNS = {MAX_TURNS}. Restart to keep chatting.)")
    print("Bye.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
