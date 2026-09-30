"""M18: one conversation with pseudo_brain, shared by every interface (the terminal and the face).

What it demonstrates: moving logic OUT of an interface. In M16 the terminal itself decided
which provider to start on, that a switch starts a new session, and which servers to stop
at exit. The face needs exactly the same rules, and two copies would drift apart. So the
rules live here, in a Chat, and the interfaces become thin wrappers (D11): terminal.py
prints, bridge.py sends JSON lines to the face. Neither decides anything.

The rules (M16, D16), unchanged:
  - A session belongs to ONE provider for life. Switching provider starts a new session,
    and opening a saved session reconnects to THAT session's provider.
  - A refused switch changes nothing: same provider, same session.
  - Connecting to private mode starts its server (Ollama); close() stops every server
    Pseudo started, and only those.
  - Every key in use is added to `secrets`, so an interface can hide it in what it shows.
  - Nothing here prints. What happens is reported through on_event, like the loop.
"""

from pseudo_brain.hands import Hands
from pseudo_brain.local_server import LocalServer, ServerFailure
from pseudo_brain.loop import EventSink, TurnResult, run_turn
from pseudo_brain.model import NO_KEY, Model, ModelFailure, connect_provider
from pseudo_brain.providers import Allowlist, Provider, ProviderRefused
from pseudo_brain.session import Session, SessionNotFound, load_latest, load_session

REFUSALS = (ProviderRefused, ModelFailure, ServerFailure, SessionNotFound)  # can't do that; the reason says why


class Chat:
    """The provider in use, the current session, and the servers Pseudo started."""

    def __init__(self, allowlist: Allowlist, on_event: EventSink, secrets: list[str]) -> None:
        self.allowlist, self.on_event, self.secrets = allowlist, on_event, secrets
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
        self.model = await self.connect(chosen)
        self.session = Session(provider=chosen.id)
        return True

    def new_session(self) -> None:
        """A fresh session on the same provider."""
        self.session = Session(provider=self.provider.id)

    async def open_session(self, name: str) -> None:
        """Continue a saved session on ITS provider. Raises one of REFUSALS, and then nothing has changed."""
        session = load_session(name)
        if session.provider != self.provider.id:
            self.model = await self.connect(self.allowlist.get(session.provider))
        self.session = session

    async def ask(self, text: str, hands: Hands) -> TurnResult:
        """One question through the loop. The session is saved after every turn, so nothing is lost."""
        result = await run_turn(self.session, text, self.model, hands, self.on_event)
        self.session.save()
        return result

    def close(self) -> list[str]:
        """Stop every server Pseudo started. Returns the ids of the providers whose server was stopped."""
        return [server.provider.id for server in self.servers.values() if server.stop()]
