"""M18: one conversation with pseudo_brain, shared by every interface (the terminal and the face).

What it demonstrates: moving logic OUT of an interface. In M16 the terminal itself decided
which provider to start on, that a switch starts a new session, and which servers to stop
at exit. The face needs exactly the same rules, and two copies would drift apart. So the
rules live here, in a Chat, and the interfaces become thin wrappers (D11): terminal.py
prints, bridge.py sends JSON lines to the face. Neither decides anything.

The rules (M16, D16, and one from M18):
  - A session belongs to ONE provider for life. Switching provider starts a new session,
    and opening a saved session reconnects to THAT session's provider.
  - A refused switch changes nothing: same provider, same session.
  - Connecting to private mode starts its server (Ollama); close() stops every server
    Pseudo started, and only those.
  - Every key in use is added to `secrets`, so an interface can hide it in what it shows.
  - Switching provider closes the old provider's connections (M18), so private mode keeps no
    idle connection to the cloud open.
  - Nothing here prints. What happens is reported through on_event, like the loop.
  - (M24) Memory, when pseudo_hands has it: before a question, search_memories finds up to 3
    redacted past tasks for it; after an ANSWERED question, save_memory stores it, if you approve
    in the popup. Pseudo calls both itself; the model never sees them (hands.py). Failed turns are
    never saved, and a failed search just means no memories.
  - (M30) Routing, when providers.toml has it (routing.py decides from your words, no model):
      * a request to ACT on a window goes to the action brain, Claude Code (D26). If it can't be
        used (billing check not clean, not installed), the turn fails visibly: no fallback to Groq.
      * everything else goes to the chat provider as before, and the window-switching tool is
        offered only when you ask to see or switch to a window (M29's rule).
      * in private mode nothing is routed: an action request stays on the laptop like the rest.
    The action brain gets the question alone (no history). The question and its final answer are
    kept in the session, labelled with who answered.
  - (M32) When the interface gave this Chat warm sessions (the face does; the terminal doesn't), an
    action request goes through their rules (warm_sessions.py): an open Claude Code session answers
    it, or a launch as in M30. A warm session serves ONE conversation, so each request says which
    session it comes from, and switching provider stops the open one.
"""

from pseudo_brain.action_brain import ActionBrain, Routing
from pseudo_brain.asks import WithAsks
from pseudo_brain.claude_code import ask_claude
from pseudo_brain.hands import Hands, OfferedHands
from pseudo_brain.local_server import LocalServer, ServerFailure
from pseudo_brain.loop import EventSink, TurnResult, run_turn
from pseudo_brain.model import NO_KEY, Model, ModelFailure, connect_provider
from pseudo_brain.providers import Allowlist, Provider, ProviderRefused
from pseudo_brain.routing import is_action_request, offers_focus
from pseudo_brain.session import Session, SessionNotFound, load_latest, load_session
from pseudo_brain.warm_sessions import WarmSessions

REFUSALS = (ProviderRefused, ModelFailure, ServerFailure, SessionNotFound)  # can't do that; the reason says why


class Chat:
    """The provider in use, the current session, and the servers Pseudo started."""

    def __init__(self, allowlist: Allowlist, on_event: EventSink, secrets: list[str],
                 routing: Routing | None = None) -> None:
        self.allowlist, self.secrets = allowlist, secrets
        self.on_event = WithAsks(on_event)  # (M40) every tool_call says whether that tool asks for approval
        self.routing = routing  # (M30) None: no routing at all, as before M30
        self.warm: WarmSessions | None = None  # (M32) set by the face's bridge; None: a launch per request
        self.servers: dict[str, LocalServer] = {}
        self.model: Model | None = None  # set by start()
        self.session: Session | None = None

    @property
    def provider(self) -> Provider:
        return self.model.provider

    async def start(self, resume: bool = False, wanted: str | None = None) -> None:
        """Connect to the first provider: the latest session's own (resume), `wanted`, or the default.

        Raises one of REFUSALS if that provider can't be used."""
        session = load_latest() if resume else None
        if session and wanted and wanted != session.provider:
            raise ProviderRefused(f"the latest session belongs to {session.provider}, and a session never changes "
                                  f"provider; leave out --continue to start a new one on {wanted}")
        provider = self.allowlist.get(session.provider if session else wanted or self.allowlist.default)
        self.model = await self.connect(provider)
        self.session = session or Session(provider=provider.id)

    async def connect(self, provider: Provider) -> Model:
        """A ready model for this provider (its server started if it has one); its key joins `secrets`."""
        model = await connect_provider(provider, self.servers, self.on_event)
        if model.client.api_key != NO_KEY:
            self.secrets.append(model.client.api_key)
        return model

    async def switch(self, provider_id: str) -> bool:
        """Use another provider, in a NEW session. False if it is already in use.

        Raises one of REFUSALS, and then nothing has changed."""
        chosen = self.allowlist.get(provider_id)
        if chosen.id == self.provider.id:
            return False
        await self.use(await self.connect(chosen))
        self.session = Session(provider=chosen.id)
        return True

    async def use(self, model: Model) -> None:
        """Use this model from now on, and close the old one's connections (M18).

        Before this, the old client stayed open: switching from Groq to private mode left an
        idle connection to Groq open (from the startup check) for as long as Pseudo ran."""
        old, self.model = self.model, model
        if old is not None and old is not model:
            await old.close()
            if self.warm:  # (M32) the conversation it served is over, and private mode keeps nothing open
                await self.warm.end("the provider was switched")

    def new_session(self) -> None:
        """A fresh session on the same provider."""
        self.session = Session(provider=self.provider.id)

    async def open_session(self, name: str) -> None:
        """Continue a saved session on ITS provider. Raises one of REFUSALS, and then nothing has changed."""
        session = load_session(name)
        if session.provider != self.provider.id:
            await self.use(await self.connect(self.allowlist.get(session.provider)))
        self.session = session

    async def ask(self, text: str, hands: Hands) -> TurnResult:
        """One question through the loop, with memories before and a save after (M24).

        The session is saved after every turn, so nothing is lost."""
        self.on_event.hands = hands  # (M40) the tools' marks, for `asks`
        intro, memories = await self.recall(text, hands)
        brain = self.action_brain_for(text)
        if brain:
            result = await self.ask_action(brain, text, memories, intro)
        else:
            withheld = self.routing.switch_tool if self.routing and not offers_focus(text) else ""
            result = await run_turn(self.session, text, self.model, OfferedHands(hands, withheld), self.on_event,
                                    memories, intro)
        self.session.save()
        if result.ok:
            await self.remember(text, result, hands, brain.id if brain else self.provider.id)
        return result

    def action_brain_for(self, text: str) -> ActionBrain | None:
        """(M30) The action brain, if this message is an action request and data may leave the laptop."""
        brain = self.routing.action_brain if self.routing else None
        if brain is None or not self.provider.leaves_laptop or not is_action_request(text):
            return None
        return brain

    async def ask_action(self, brain: ActionBrain, text: str, memories: list[str], intro: str) -> TurnResult:
        """(M30) One action request through Claude Code; the question and answer join this session."""
        self.on_event("routed", {"to": brain.id, "name": brain.name, "model": brain.model, "privacy": brain.privacy})
        self.session.provider = self.session.provider or self.provider.id
        self.session.start_turn(text)
        if self.warm:  # (M32) the open session if its rules allow, else a launch
            result = await self.warm.ask(brain, text, self.on_event, memories, intro, self.session.started)
        else:
            result = await ask_claude(brain, text, self.on_event, memories, intro)
        if result.ok:
            self.session.add({"role": "assistant", "content": result.answer})
            self.session.note_answer(f"{brain.id} · {result.model}")
        return result

    async def recall(self, text: str, hands: Hands) -> tuple[str, list[str]]:
        """(M24) The intro and the redacted past tasks for this question; none if memory is off or fails."""
        if not hands.has_memory:
            return "", []
        found = await hands.brain_call("search_memories", {"question": text})
        memories = [m for m in (found or {}).get("memories", []) if isinstance(m, str)]
        note = "the memory search failed" if found is None else str(found.get("note", ""))
        titles = [m.split("\n", 1)[0].removeprefix("- ").split(": ", 1)[-1][:80] for m in memories]  # (M42) redacted
        self.on_event("memories", {"count": len(memories), "chars": sum(len(m) for m in memories), "note": note,
                                   "titles": titles})
        return str((found or {}).get("intro", "")), memories

    async def remember(self, text: str, result: TurnResult, hands: Hands, provider_id: str) -> None:
        """(M24) Offer this answered task to memory. pseudo_hands redacts it and asks you in the popup."""
        if not hands.has_memory:
            return
        # A tool_call event, so the face lets pseudo_hands' popup come to the front, as for any tool (M18).
        self.on_event("tool_call", {"name": "save_memory", "arguments": "{}", "by": "pseudo"})
        saved = await hands.brain_call("save_memory", {
            "question": text, "answer": result.answer or "", "tools": result.tools, "provider": provider_id,
            "model": result.model, "session": self.session.started})
        self.on_event("tool_result", {"name": "save_memory", "chars": 0, "is_error": saved is None, "by": "pseudo"})
        if saved and saved.get("status") == "saved":
            self.on_event("memory_saved", {"note": str(saved.get("note", ""))})
        else:
            self.on_event("memory_not_saved", {"reason": str((saved or {}).get("reason") or "the memory tool failed")})

    def close(self) -> list[str]:
        """Stop every server Pseudo started. Returns the ids of the providers whose server was stopped."""
        return [server.provider.id for server in self.servers.values() if server.stop()]
