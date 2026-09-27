"""M1b: the same model call as 01a, through the official openai SDK.

What it demonstrates: an SDK is a convenience wrapper around the exact same
HTTP request. It builds the URL, headers and JSON for you, sends them with
httpx2 (the library 01a used by hand), and turns the JSON reply into typed
Python objects.

Concepts it teaches: client objects, base_url (the knob that swaps the
provider), typed responses vs raw dicts, and the SDK's error classes.

Run it:  python playground/01b_sdk.py
         python playground/01b_sdk.py "your own question"
"""

import json
import os
import sys
import time
from pathlib import Path

import openai
from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
SYSTEM_PROMPT = "You are a concise assistant. Answer in one or two short sentences."
DEFAULT_QUESTION = "In one sentence, what is an API?"


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


def show(title: str, text: str, api_key: str) -> None:
    """Print one labelled step. Every print in this script goes through here."""
    print(f"\n--- {title} ---")
    print(hide_key(text, api_key))


def main() -> int:
    base_url, api_key, model = load_config()
    question = " ".join(sys.argv[1:]) or DEFAULT_QUESTION

    # 1. The client stores where to send requests and which key to use.
    #    base_url pointing at Groq is the only thing that makes this "not OpenAI".
    #    The SDK normally retries failed calls twice, silently; max_retries=0
    #    turns that off so every request you see is exactly one request.
    client = openai.OpenAI(base_url=base_url, api_key=api_key, max_retries=0, timeout=60)
    show("1. CREATING THE CLIENT", f'OpenAI(base_url="{base_url}", api_key=<hidden>)', api_key)

    # 2. Same messages list as 01a. The SDK wraps it in the JSON body for us.
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    show(
        "2. CALLING client.chat.completions.create(...) WITH",
        f'model="{model}"\nmessages={json.dumps(messages, indent=2)}',
        api_key,
    )

    print("\n--- SENDING TO MODEL (the SDK builds the same POST as 01a, using httpx2) ---")
    started = time.perf_counter()
    try:
        completion = client.chat.completions.create(model=model, messages=messages)
    except openai.APIStatusError as error:  # the server answered with an error (401, 429...)
        show("ERROR FROM PROVIDER", f"{type(error).__name__} ({error.status_code}): {error.message}", api_key)
        return 1
    except openai.APIConnectionError as error:  # never reached the server
        show("NETWORK ERROR", repr(error), api_key)
        return 1
    seconds = time.perf_counter() - started

    # 3. No response.json(), no dict keys: the SDK hands back a typed object.
    answer = completion.choices[0].message.content
    usage = completion.usage
    show(
        "3. WHAT THE SDK GIVES BACK",
        f"Python type: {type(completion).__name__}   (a typed object, not a raw dict)\n"
        f"completion.choices[0].message.content\n  -> {answer}\n\n"
        f"completion.usage -> {usage.prompt_tokens} in + {usage.completion_tokens} out"
        f" = {usage.total_tokens} total  ({seconds:.2f} s)",
        api_key,
    )

    show(
        "4. RAW (01a) vs SDK (01b): same data, different access",
        'data["choices"][0]["message"]["content"]   # 01a: nested dicts from response.json()\n'
        "completion.choices[0].message.content      # 01b: attributes, with editor autocomplete",
        api_key,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
