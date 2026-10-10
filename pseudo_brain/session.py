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
  - (M24) Memories (past tasks from pseudo_hands) join a request as one extra system message
    right after the system prompt. They belong to that REQUEST only: never stored in the turns,
    never saved. Over budget, the oldest turns go first, then the weakest memories, and only
    then does the turn fail as too large.
  - (M18) The face lists saved sessions and opens one by NAME. A name is accepted only
    if it looks like one Pseudo made (a date and time), so it can never be a path
    that points outside the sessions folder (the M3 sandbox idea).
  - (M41) A chat can have a title you gave it; without one, the sidebar shows its first question.
    Renaming, deleting and searching live in session_files.py.
"""

import json
import os
import re
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

M14_PROVIDER = "groq"  # sessions saved before M16 have no provider: they all used Groq
SESSIONS_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Pseudo" / "sessions"
SESSION_NAME = re.compile(r"[0-9]{8}-[0-9]{6}(-[0-9]{3})?")  # 20260930-231500-123 (M14's: no milliseconds)
# (M41) [0-9], not \d: Python's \d also matches other scripts' digits, which Pseudo never writes in a name
TITLE_CHARS = 60  # (M18) how much of a session's first question the face's list shows


class SessionNotFound(Exception):
    """(M18) There is no saved session with that name, or the name isn't one Pseudo makes."""


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
    title: str = ""  # (M41) the name you gave this chat; "" = none, so the sidebar shows its first question

    def start_turn(self, text: str) -> None:
        self.turns.append([{"role": "user", "content": text}])

    def add(self, message: dict) -> None:
        """Add an assistant or tool message to the current turn."""
        self.turns[-1].append(message)

    def note_answer(self, label: str) -> None:
        """Which provider and model answered the current turn. Saved, never sent to a model."""
        self.answered_by[len(self.turns) - 1] = label

    def messages_for_request(self, system_prompt: str, tools: list[dict], limit: int, memories: list[str] = (),
                             intro: str = "") -> tuple[list[dict], int, int, int]:
        """System prompt, memories, and as many recent turns as fit in `limit` tokens (the provider's max_prompt_tokens).

        `memories` are best first. Returns (messages, estimate, turns dropped, memories used)."""
        kept, dropped, used = list(self.turns), 0, list(memories)  # copies: trimming never deletes history
        while True:
            system = [{"role": "system", "content": system_prompt}]
            if used:
                system.append({"role": "system", "content": "\n".join([intro, *used])})
            messages = system + [message for turn in kept for message in turn]
            estimate = estimate_tokens(messages, tools)
            if estimate <= limit:
                break
            if len(kept) > 1:
                kept.pop(0)  # the oldest whole turn first
                dropped += 1
            elif used:
                used.pop()  # then the weakest memory
            else:
                raise TooLarge(estimate, limit)
        return messages, estimate, dropped, len(used)

    def transcript(self) -> list[dict]:
        """Your messages and the final answers, each answer with who gave it: what is saved (and shown)."""
        kept = []
        for number, turn in enumerate(self.turns):
            for m in turn:
                if m["role"] == "user" or is_final_answer(m):
                    kept.append({"role": m["role"], "content": m["content"]})
                    if m["role"] == "assistant" and number in self.answered_by:
                        kept[-1]["answered_by"] = self.answered_by[number]
        return kept

    def save(self) -> Path:
        """Write your messages and the final answers (nothing from tools) to this session's file."""
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        path = SESSIONS_DIR / f"{self.started}.json"
        data = {"started": self.started, "provider": self.provider, "title": self.title, "messages": self.transcript()}
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        return path


def saved_files() -> list[Path]:
    """Every saved session file, oldest first (the names are dates and times, so they sort by time)."""
    return sorted(SESSIONS_DIR.glob("*.json")) if SESSIONS_DIR.exists() else []


def session_item(name: str, data: dict) -> tuple[dict, list[str]]:
    """(M41) A saved chat's line in the sidebar (name, provider, questions, title), and your messages.

    Raises KeyError or TypeError for a damaged file."""
    asked = [m["content"] for m in data["messages"] if m["role"] == "user"]
    title = data.get("title") if isinstance(data.get("title"), str) and data.get("title") else ""
    item = {"name": name, "provider": data.get("provider") or M14_PROVIDER, "questions": len(asked),
            "title": title or (asked[0][:TITLE_CHARS] if asked else "")}
    return item, asked


def saved_chats() -> Iterator[tuple[dict, list[str]]]:
    """(M41) Every readable saved chat, newest first, as session_item() gives it."""
    for path in reversed(saved_files()):
        try:
            chat = session_item(path.stem, json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError, KeyError, TypeError):  # a damaged file is left out, never guessed at
            continue
        yield chat


def list_sessions() -> list[dict]:
    """(M18) Every saved session, newest first: its name, provider, number of questions and title."""
    return [item for item, _asked in saved_chats()]


def load_session(name: str) -> Session:
    """(M18) One saved session, by the name list_sessions() gave. Raises SessionNotFound."""
    if not isinstance(name, str) or not SESSION_NAME.fullmatch(name):
        raise SessionNotFound("that is not a session name")  # never used as a path
    path = SESSIONS_DIR / f"{name}.json"
    try:
        return read_session(path)
    except (OSError, ValueError, KeyError, TypeError):
        raise SessionNotFound(f"no readable saved session called {name}") from None


def load_latest() -> Session | None:
    """The most recent saved session, or None. Its turns hold only messages and answers, and it keeps its provider."""
    files = saved_files()
    return read_session(files[-1]) if files else None


def read_session(path: Path) -> Session:
    """A saved file -> a Session with its provider and answer labels."""
    data = json.loads(path.read_text(encoding="utf-8"))
    title = data.get("title") if isinstance(data.get("title"), str) else ""
    session = Session(started=data["started"], provider=data.get("provider") or M14_PROVIDER, title=title)
    for message in data["messages"]:
        label = message.pop("answered_by", None)  # kept in the session, never sent to a model
        if message["role"] == "user":
            session.turns.append([message])
        elif session.turns:
            session.turns[-1].append(message)
            if label:
                session.note_answer(label)
    return session
