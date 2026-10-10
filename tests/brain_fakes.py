"""Shared fakes for pseudo_brain's tests (M14, M16). Not a test file itself.

Everything here is FAKE: fake providers, a scripted FakeModel that plays Groq or Ollama,
and a small in-memory MCP server that plays pseudo_hands (the real MCP protocol, no
subprocess). No network, no real windows.
"""

import httpx2
import openai
from mcp.server import MCPServer
from openai.types.chat import ChatCompletion

from pseudo_brain.hands import connect_hands
from pseudo_brain.loop import run_turn
from pseudo_brain.model import Model
from pseudo_brain.providers import Provider
from pseudo_brain.session import Session

MARKER = "ZEBRA-7731"  # fake screen text: must never appear in an event

# Two models, like Groq's main + fallback (D16).
FAKE_CLOUD = Provider("groq", "Fake cloud", "https://fake.invalid/v1", "FAKE_M16_KEY", ("big-model", "small-model"),
                      True, "fake note", 60.0, 3000)
# One model: a 429 has nowhere to fall back to, so it waits (the M14 behaviour).
FAKE_ONE = Provider("one", "Fake cloud", "https://fake.invalid/v1", "FAKE_M16_KEY", ("only-model",),
                    True, "fake note", 60.0, 3000)
# Private mode: one model, at 127.0.0.1.
FAKE_LOCAL = Provider("local", "Fake local", "http://127.0.0.1:11434/v1", "", ("tiny-model",),
                      False, "fake note", 180.0, 2500)


def fake_read_active_window() -> dict:
    return {"title": "Fake notes", "app": "notepad.exe", "content": f"Text: call [PERSON] about {MARKER}"}


def fake_focus_window(window_id: str) -> dict:
    return {"window_id": window_id, "status": "not approved"}


def fake_broken() -> dict:
    raise RuntimeError("fake failure")


FAKE_HANDS = MCPServer("fake_hands")
FAKE_HANDS.add_tool(fake_read_active_window, name="read_active_window", description="Read the fake window.")
FAKE_HANDS.add_tool(fake_focus_window, name="focus_window", description="Focus a fake window.")
FAKE_HANDS.add_tool(fake_broken, name="broken_tool", description="Always fails.")
FAKE_MODEL_TOOLS = ("read_active_window", "focus_window", "broken_tool")  # (D29) the fake server's model_tools


def reply(content: str | None = None, tools: list = (), tokens: tuple = (100, 10)) -> ChatCompletion:
    """A fake model reply: plain text, or tool calls given as (name, arguments) pairs."""
    calls = [{"id": f"call_{i}", "type": "function", "function": {"name": n, "arguments": a}}
             for i, (n, a) in enumerate(tools)]
    return ChatCompletion.model_validate({
        "id": "fake", "object": "chat.completion", "created": 0, "model": "fake-model",
        "choices": [{"index": 0, "finish_reason": "tool_calls" if calls else "stop",
                     "message": {"role": "assistant", "content": content, "tool_calls": calls or None}}],
        "usage": {"prompt_tokens": tokens[0], "completion_tokens": tokens[1], "total_tokens": sum(tokens)}})


def http_response(status: int, headers: dict | None = None) -> httpx2.Response:
    return httpx2.Response(status, headers=headers or {}, request=httpx2.Request("POST", "https://fake.invalid/v1"))


def rate_limited(seconds: str = "2") -> openai.RateLimitError:
    return openai.RateLimitError("rate limited", response=http_response(429, {"retry-after": seconds}), body=None)


def unreachable() -> openai.APIConnectionError:
    return openai.APIConnectionError(request=httpx2.Request("POST", "http://127.0.0.1:11434/v1"))


class FakeModel(Model):
    """The REAL Model (so its fallback logic is what's tested), with complete() scripted.

    Returns the scripted replies in order (the last one repeats) and records every request
    and which model it went to. If timeline is a list, each request is also added to it,
    so a test can check it came after an event.
    """

    def __init__(self, *replies, provider: Provider = FAKE_ONE, timeline: list | None = None) -> None:
        super().__init__(provider, "fake-key")
        self.replies, self.requests, self.used, self.timeline = list(replies), [], [], timeline

    async def complete(self, request: dict):
        self.requests.append(request)
        self.used.append(self.name)
        if self.timeline is not None:
            self.timeline.append(("request", {"model": self.name}))
        outcome = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome, {"x-ratelimit-remaining-tokens": "7000", "x-ratelimit-limit-tokens": "8000"}


async def ask(fake_model: FakeModel, text: str = "What does my active window say?",
              session: Session | None = None, events: list | None = None):
    """One question through the real loop, fake model and fake hands. Returns (result, events, session)."""
    events = [] if events is None else events
    session = session or Session()
    async with connect_hands(FAKE_HANDS, FAKE_MODEL_TOOLS) as hands:
        result = await run_turn(session, text, fake_model, hands, lambda kind, data: events.append((kind, data)))
    return result, events, session
