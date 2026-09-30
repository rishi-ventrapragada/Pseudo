"""M14, M16: the model client. One model call at a time, with visible 429 handling.

What it demonstrates: the same call as M1-M3 (the OpenAI-compatible API, D10), now
async (AsyncOpenAI), because pseudo_brain also talks to pseudo_hands over MCP, and
MCP is async. Nothing here prints: waits are reported through on_event, so any
interface (the terminal now, the React face in M18) can show them.

Since M16 a Model belongs to ONE provider from the allowlist (providers.py, D16). The
same code talks to Groq or to Ollama on this laptop: only the URL, key and model names
differ, and they come from providers.toml.

Honesty rules (D15, D16):
  - max_retries=0: the SDK never retries on its own; every request is one request.
  - a 429 switches to the provider's NEXT model, announced BEFORE the request goes out
    (the "fallback" event). A Model holds one provider and nothing else, so it cannot
    fall back to another provider: private mode can never fall back to the cloud.
  - a 429 on the provider's last model waits exactly as long as asked (retry-after),
    announced before the wait, at most MAX_RATE_LIMIT_WAITS times and never longer
    than LONGEST_WAIT_SECONDS.
  - anything else that fails raises ModelFailure with a plain reason (status code and
    error code only). The loop never turns a failure into an answer.
"""

import os
from collections.abc import Callable
from pathlib import Path

import anyio
import openai
from dotenv import load_dotenv
from openai.types.chat import ChatCompletion

from pseudo_brain.local_server import LocalServer
from pseudo_brain.providers import Provider

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
MAX_RATE_LIMIT_WAITS = 3  # per model call, on the provider's last model
LONGEST_WAIT_SECONDS = 60  # if the provider wants a longer wait than this, stop instead
DEFAULT_WAIT_SECONDS = 10.0  # when a 429 comes without a usable retry-after header
CHECK_TIMEOUT_SECONDS = 10.0  # asking a provider for its model list
NO_KEY = "no-key"  # the SDK wants some key; a provider without key_env (Ollama) ignores it


class ModelFailure(Exception):
    """The model call failed and waiting won't fix it. The message says why, in plain words."""


def load_key(provider: Provider) -> str:
    """The provider's key from .env, found by the variable NAME in providers.toml (never the value)."""
    if not provider.key_env:
        return NO_KEY
    load_dotenv(ENV_PATH)
    key = os.getenv(provider.key_env)
    if not key:
        raise ModelFailure(f"missing {provider.key_env} in .env (see .env.example)")
    return key


class Model:
    """One provider's models, in order. Tests replace complete() with scripted replies."""

    def __init__(self, provider: Provider, api_key: str) -> None:
        self.provider = provider
        self.index = 0  # which of provider.models is in use: 0 = the main model
        self.client = openai.AsyncOpenAI(base_url=provider.base_url, api_key=api_key, max_retries=0,
                                         timeout=provider.timeout_seconds)

    @property
    def name(self) -> str:
        return self.provider.models[self.index]

    @property
    def on_fallback(self) -> bool:
        return self.index > 0

    def use_main(self) -> None:
        """Every question starts on the main model again."""
        self.index = 0

    def fall_back(self) -> bool:
        """Move to the provider's next model. False if this was its last one."""
        if self.index + 1 >= len(self.provider.models):
            return False
        self.index += 1
        return True

    async def complete(self, request: dict) -> tuple[ChatCompletion, dict]:
        """One HTTP request. Returns the reply and the response headers (the rate-limit budget)."""
        raw = await self.client.chat.completions.with_raw_response.create(model=self.name, **request)
        return raw.parse(), dict(raw.headers)

    async def check(self) -> None:
        """Is the provider reachable, and does it have every model on our list? ModelFailure if not."""
        where = f"{self.provider.name} at {self.provider.address}"
        try:
            page = await self.client.models.list(timeout=CHECK_TIMEOUT_SECONDS)
        except openai.APIConnectionError:  # includes timeouts
            raise ModelFailure(f"could not reach {where}") from None
        except openai.APIStatusError as error:
            raise ModelFailure(f"{where} refused to list its models ({error.status_code})") from None
        available = {listed.id for listed in page.data}
        missing = [name for name in self.provider.models if name not in available]
        if missing:
            raise ModelFailure(f"{where} doesn't have {', '.join(missing)}")


async def connect_provider(provider: Provider, servers: dict[str, LocalServer],
                           on_event: Callable[[str, dict], None]) -> Model:
    """A ready Model: the provider's own server started if it has one, its key loaded, and checked.

    Raises ServerFailure or ModelFailure, with a plain reason, if the provider can't be used.
    A server started here stays in `servers`, so the interface can stop it when it exits.
    """
    if provider.server:
        server = servers.setdefault(provider.id, LocalServer(provider))
        on_event("server_starting", {"provider": provider.id, "address": provider.address})
        on_event("server_ready", await server.start())
    try:
        model = Model(provider, load_key(provider))
        await model.check()
    except ModelFailure:
        if provider.server:
            servers[provider.id].stop()  # started for nothing: don't leave it running
        raise
    return model


def retry_after(error: openai.RateLimitError) -> float:
    """How long the provider asked us to wait, in seconds."""
    try:
        return float(error.response.headers.get("retry-after", DEFAULT_WAIT_SECONDS))
    except (TypeError, ValueError):
        return DEFAULT_WAIT_SECONDS


async def wait(seconds: float) -> None:
    """Its own function so tests can skip the real waiting."""
    await anyio.sleep(seconds)


async def call_model(model, request: dict,
                     on_event: Callable[[str, dict], None]) -> tuple[ChatCompletion, dict]:
    """One model call: a 429 falls back within the provider, then waits. Raises ModelFailure otherwise.

    A 400 "tool_use_failed" (the model wrote a broken tool call) is re-raised unchanged,
    so the loop can ask the model again within its iteration cap.
    """
    name, waits = model.provider.name, 0
    while True:
        try:
            return await model.complete(request)
        except openai.RateLimitError as error:  # 429: too many tokens or requests this minute
            limited = model.name
            if model.fall_back():  # the next model of the SAME provider, announced before it's used
                on_event("fallback", {"provider": model.provider.id, "from": limited, "to": model.name})
                continue
            delay = retry_after(error)
            waits += 1
            if waits > MAX_RATE_LIMIT_WAITS or delay > LONGEST_WAIT_SECONDS:
                raise ModelFailure(f"{name} is still rate limiting (429) after {waits - 1} wait(s) and asks "
                                   f"for {delay:.0f} s more; try again in a minute") from None
            on_event("rate_limited", {"seconds": delay, "wait": waits, "of": MAX_RATE_LIMIT_WAITS,
                                      "provider": name, "model": model.name})
            await wait(delay)
        except openai.APIStatusError as error:
            code = getattr(error, "code", None)
            if error.status_code == 400 and code == "tool_use_failed":
                raise
            if error.status_code == 413:
                raise ModelFailure(f"the request is bigger than {name}'s per-minute token limit; "
                                   "waiting won't help") from None
            raise ModelFailure(f"{name} returned an error ({error.status_code}"
                               f"{', ' + code if code else ''})") from None
        except openai.APIConnectionError:  # includes timeouts
            raise ModelFailure(f"could not reach {name} (network problem or timeout)") from None
