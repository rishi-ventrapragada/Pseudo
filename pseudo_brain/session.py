"""M14, M16: session history. What pseudo_brain remembers between your questions.

What it demonstrates: the model is stateless (M1), so every call must resend the
conversation. The session keeps it, turn by turn, and TRIMS each request to a
budget, because Groq's free tier allows 8,000 tokens per minute and every call
resends everything. Since M16 the budget is the provider's max_prompt_tokens
(providers.toml): Ollama's context is smaller than Groq's minute budget.

Rules:
  - History is a list of whole TURNS: your message, any tool calls and results, and
    the answer. Trimming drops the OLDEST whole turn, so a tool result is never left
    without the call that asked for it. Trimming shapes one request; history keeps all.
  - The current turn is never trimmed. If it alone is too big, the turn fails.
  - Saving keeps only your messages and the final answers. Tool calls and tool results
    (screen content, even redacted) live only in memory and are gone when you quit.
  - (M16) A session belongs to ONE provider for life, and says which model gave each
    answer. A private conversation's history can never be sent to the cloud later:
    the loop refuses a model from another provider (loop.py), and switching
    provider starts a new session.
"""

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

M14_PROVIDER = "groq"  # sessions saved before M16 have no provider: they all used Groq
SESSIONS_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Pseudo" / "sessions"


class TooLarge(Exception):
    """The current turn alone is over the budget; sending it would only fail."""

    def __init__(self, estimate: int, limit: int) -> None:
        super().__init__(f"~{estimate} tokens, limit {limit}")
        self.estimate, self.limit = estimate, limit


def estimate_tokens(messages: list[dict], tools: list[dict] = ()) -> int:
    """About 4 characters per token: rough, but free (no tokenizer). Groq reports the real count."""
    return (len(json.dumps(messages, ensure_ascii=False)) + len(json.dumps(list(tools)))) // 4


def session_name() -> str:
    """The time now, to the millisecond: a session started right after another one gets its own file."""
    now = time.time()  # read the clock once, so seconds and milliseconds belong together
    return time.strftime("%Y%m%d-%H%M%S", time.localtime(now)) + f"-{int(now * 1000) % 1000:03d}"


def is_final_answer(message: dict) -> bool:
    return message["role"] == "assistant" and not message.get("tool_calls") and bool(message.get("content"))


@dataclass
class Session:
    turns: list[list[dict]] = field(default_factory=list)  # each turn: its messages, in order
    started: str = field(default_factory=lambda: session_name())  # also the file name
    provider: str = ""  # the provider this session belongs to ("" = not bound yet: the first turn binds it)
    answered_by: dict[int, str] = field(default_factory=dict)  # turn number -> "groq · model (fallback)"

    def start_turn(self, text: str) -> None:
        self.turns.append([{"role": "user", "content": text}])

    def add(self, message: dict) -> None:
        """Add an assistant or tool message to the current turn."""
        self.turns[-1].append(message)

    def note_answer(self, label: str) -> None:
        """Which provider and model answered the current turn. Saved, never sent to a model."""
        self.answered_by[len(self.turns) - 1] = label

    def messages_for_request(self, system_prompt: str, tools: list[dict], limit: int) -> tuple[list[dict], int, int]:
        """System prompt plus as many recent turns as fit in `limit` tokens (the provider's max_prompt_tokens).

        Returns (messages, estimate, turns dropped)."""
        system = [{"role": "system", "content": system_prompt}]
        kept, dropped = list(self.turns), 0  # a copy: trimming a request never deletes history
        while True:
            messages = system + [message for turn in kept for message in turn]
            estimate = estimate_tokens(messages, tools)
            if estimate <= limit or len(kept) <= 1:
                break
            kept.pop(0)  # the oldest whole turn
            dropped += 1
        if estimate > limit:
            raise TooLarge(estimate, limit)
        return messages, estimate, dropped

    def save(self) -> Path:
        """Write your messages and the final answers (nothing from tools) to this session's file."""
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        kept = []
        for number, turn in enumerate(self.turns):
            for m in turn:
                if m["role"] == "user" or is_final_answer(m):
                    kept.append({"role": m["role"], "content": m["content"]})
                    if m["role"] == "assistant" and number in self.answered_by:
                        kept[-1]["answered_by"] = self.answered_by[number]
        path = SESSIONS_DIR / f"{self.started}.json"
        data = {"started": self.started, "provider": self.provider, "messages": kept}
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        return path


def load_latest() -> Session | None:
    """The most recent saved session, or None. Its turns hold only messages and answers, and it keeps its provider."""
    files = sorted(SESSIONS_DIR.glob("*.json")) if SESSIONS_DIR.exists() else []
    if not files:
        return None
    data = json.loads(files[-1].read_text(encoding="utf-8"))
    session = Session(started=data["started"], provider=data.get("provider") or M14_PROVIDER)
    for message in data["messages"]:
        label = message.pop("answered_by", None)  # kept in the session, never sent to a model
        if message["role"] == "user":
            session.turns.append([message])
        elif session.turns:
            session.turns[-1].append(message)
            if label:
                session.note_answer(label)
    return session
