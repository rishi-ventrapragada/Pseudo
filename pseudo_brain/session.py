"""M14: session history. What pseudo_brain remembers between your questions.

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
"""

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

SESSIONS_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Pseudo" / "sessions"


class TooLarge(Exception):
    """The current turn alone is over the budget; sending it would only fail."""

    def __init__(self, estimate: int, limit: int) -> None:
        super().__init__(f"~{estimate} tokens, limit {limit}")
        self.estimate, self.limit = estimate, limit


def estimate_tokens(messages: list[dict], tools: list[dict] = ()) -> int:
    """About 4 characters per token: rough, but free (no tokenizer). Groq reports the real count."""
    return (len(json.dumps(messages, ensure_ascii=False)) + len(json.dumps(list(tools)))) // 4


def is_final_answer(message: dict) -> bool:
    return message["role"] == "assistant" and not message.get("tool_calls") and bool(message.get("content"))


@dataclass
class Session:
    turns: list[list[dict]] = field(default_factory=list)  # each turn: its messages, in order
    started: str = field(default_factory=lambda: time.strftime("%Y%m%d-%H%M%S"))  # also the file name

    def start_turn(self, text: str) -> None:
        self.turns.append([{"role": "user", "content": text}])

    def add(self, message: dict) -> None:
        """Add an assistant or tool message to the current turn."""
        self.turns[-1].append(message)

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
        kept = [{"role": m["role"], "content": m["content"]} for turn in self.turns for m in turn
                if m["role"] == "user" or is_final_answer(m)]
        path = SESSIONS_DIR / f"{self.started}.json"
        path.write_text(json.dumps({"started": self.started, "messages": kept}, ensure_ascii=False, indent=1),
                        encoding="utf-8")
        return path


def load_latest() -> Session | None:
    """The most recent saved session, or None. Its turns hold only messages and answers."""
    files = sorted(SESSIONS_DIR.glob("*.json")) if SESSIONS_DIR.exists() else []
    if not files:
        return None
    data = json.loads(files[-1].read_text(encoding="utf-8"))
    session = Session(started=data["started"])
    for message in data["messages"]:
        if message["role"] == "user":
            session.turns.append([message])
        elif session.turns:
            session.turns[-1].append(message)
    return session
