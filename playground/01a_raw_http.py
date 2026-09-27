"""M1a: talk to a model with nothing but an HTTP request.

What it demonstrates: a "call to an AI model" is one HTTPS POST. You send
JSON (which model, plus a list of messages) and you get JSON back. No SDK,
no magic, just the same kind of request as fetch() in a web app.

Concepts it teaches: the endpoint URL, the Authorization header, the request
body, status codes, the response shape (choices / message / usage), and
rate limits.

Run it:  python playground/01a_raw_http.py
         python playground/01a_raw_http.py "your own question"
"""

import json
import os
import sys
import time
from pathlib import Path

import httpx2
from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
SYSTEM_PROMPT = "You are a concise assistant. Answer in one or two short sentences."
DEFAULT_QUESTION = "In one sentence, what is an API?"

# Groq (like OpenAI) reports your remaining budget in these response headers.
# On Groq, "requests" counts per day and "tokens" counts per minute.
RATE_LIMIT_HEADERS = (
    "x-ratelimit-limit-requests",
    "x-ratelimit-remaining-requests",
    "x-ratelimit-limit-tokens",
    "x-ratelimit-remaining-tokens",
)


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

    # 1. Where the request goes. "/chat/completions" is the standard path every
    #    OpenAI-compatible provider uses; only the base URL changes between them.
    url = f"{base_url.rstrip('/')}/chat/completions"
    show("1. ENDPOINT", f"POST {url}", api_key)

    # 2. Headers. The key travels here as a "Bearer" token (like a Supabase key).
    #    We print a copy with the key swapped out, never the real dict.
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    safe_headers = {**headers, "Authorization": "Bearer <hidden>"}
    show("2. HEADERS", json.dumps(safe_headers, indent=2), api_key)

    # 3. The body: which model, and the whole conversation as a list of messages.
    #    "system" sets the rules, "user" is what you typed.
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ],
    }
    show("3. REQUEST BODY (the full JSON we send)", json.dumps(body, indent=2), api_key)

    print("\n--- SENDING TO MODEL ---")
    started = time.perf_counter()
    try:
        response = httpx2.post(url, headers=headers, json=body, timeout=60)
    except httpx2.RequestError as error:  # no internet, DNS failure, timeout...
        show("NETWORK ERROR", repr(error), api_key)
        return 1
    seconds = time.perf_counter() - started

    show("4. RESPONSE STATUS", f"{response.status_code} {response.reason_phrase}  ({seconds:.2f} s)", api_key)

    limits = [f"{name}: {response.headers.get(name, '(not sent)')}" for name in RATE_LIMIT_HEADERS]
    show("5. RATE-LIMIT HEADERS (your free-tier budget, live)", "\n".join(limits), api_key)

    # Anything other than 200 is an error: 401 = bad key, 429 = rate limited.
    # The error details come back as JSON too, so we just show them.
    if response.status_code != 200:
        show("ERROR BODY", response.text, api_key)
        return 1

    data = response.json()  # JSON text -> Python dict
    show("6. RESPONSE BODY (the full JSON we got back)", json.dumps(data, indent=2), api_key)

    # Out of all that JSON, this is the one field we actually wanted.
    answer = data["choices"][0]["message"]["content"]
    usage = data["usage"]
    show(
        "7. THE PART WE ACTUALLY WANTED",
        f'data["choices"][0]["message"]["content"]\n  -> {answer}\n\n'
        f"Tokens: {usage['prompt_tokens']} in + {usage['completion_tokens']} out"
        f" = {usage['total_tokens']} total",
        api_key,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
