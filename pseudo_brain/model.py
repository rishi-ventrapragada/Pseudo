"""M14: the model client. One Groq call at a time, with visible 429 handling.

What it demonstrates: the same call as M1-M3 (the OpenAI-compatible API, D10), now
async (AsyncOpenAI), because pseudo_brain also talks to pseudo_hands over MCP, and
MCP is async. Nothing here prints: waits are reported through on_event, so any
interface (the terminal now, the React face in M15) can show them.

Honesty rules (D15):
  - max_retries=0: the SDK never retries on its own; every request is one request.
  - a 429 waits exactly as long as Groq asks (retry-after), announced BEFORE the
    wait, at most MAX_RATE_LIMIT_WAITS times and never longer than LONGEST_WAIT_SECONDS.
  - anything else that fails raises ModelFailure with a plain reason (status code and
    error code only). The loop never turns a failure into an answer.
"""

import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import anyio
import openai
from dotenv import load_dotenv
from openai.types.chat import ChatCompletion

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
MAX_RATE_LIMIT_WAITS = 3  # per model call
LONGEST_WAIT_SECONDS = 60  # if Groq wants a longer wait than this, stop instead
DEFAULT_WAIT_SECONDS = 10.0  # when a 429 comes without a usable retry-after header


class ModelFailure(Exception):
    """The model call failed and waiting won't fix it. The message says why, in plain words."""


@dataclass
class ModelSettings:
    base_url: str
    api_key: str
    model: str


def load_settings() -> ModelSettings:
    """The three LLM_* settings from .env (the same file and names as M1-M3)."""
    load_dotenv(ENV_PATH)
    values = [os.getenv(name) for name in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL")]
    if not all(values):
        raise ModelFailure("missing LLM_BASE_URL, LLM_API_KEY or LLM_MODEL in .env (see .env.example)")
    return ModelSettings(*values)


class Model:
    """The real model: Groq through AsyncOpenAI. Tests pass a fake with the same complete()."""

    def __init__(self, settings: ModelSettings) -> None:
        self.name = settings.model
        self.client = openai.AsyncOpenAI(base_url=settings.base_url, api_key=settings.api_key,
                                         max_retries=0, timeout=60)

    async def complete(self, request: dict) -> tuple[ChatCompletion, dict]:
        """One HTTP request. Returns the reply and the response headers (the rate-limit budget)."""
        raw = await self.client.chat.completions.with_raw_response.create(model=self.name, **request)
        return raw.parse(), dict(raw.headers)


def retry_after(error: openai.RateLimitError) -> float:
    """How long Groq asked us to wait, in seconds."""
    try:
        return float(error.response.headers.get("retry-after", DEFAULT_WAIT_SECONDS))
    except (TypeError, ValueError):
        return DEFAULT_WAIT_SECONDS


async def wait(seconds: float) -> None:
    """Its own function so tests can skip the real waiting."""
    await anyio.sleep(seconds)


async def call_model(model, request: dict,
                     on_event: Callable[[str, dict], None]) -> tuple[ChatCompletion, dict]:
    """One model call, waiting out 429s the way Groq asks. Raises ModelFailure otherwise.

    A 400 "tool_use_failed" (the model wrote a broken tool call) is re-raised unchanged,
    so the loop can ask the model again within its iteration cap.
    """
    waits = 0
    while True:
        try:
            return await model.complete(request)
        except openai.RateLimitError as error:  # 429: too many tokens or requests this minute
            delay = retry_after(error)
            waits += 1
            if waits > MAX_RATE_LIMIT_WAITS or delay > LONGEST_WAIT_SECONDS:
                raise ModelFailure(f"Groq is still rate limiting (429) after {waits - 1} wait(s) and asks "
                                   f"for {delay:.0f} s more; try again in a minute") from None
            on_event("rate_limited", {"seconds": delay, "wait": waits, "of": MAX_RATE_LIMIT_WAITS})
            await wait(delay)
        except openai.APIStatusError as error:
            code = getattr(error, "code", None)
            if error.status_code == 400 and code == "tool_use_failed":
                raise
            if error.status_code == 413:
                raise ModelFailure("the request is bigger than Groq's per-minute token limit; "
                                   "waiting won't help") from None
            raise ModelFailure(f"Groq returned an error ({error.status_code}"
                               f"{', ' + code if code else ''})") from None
        except openai.APIConnectionError:  # includes timeouts
            raise ModelFailure("could not reach Groq (network problem or timeout)") from None
