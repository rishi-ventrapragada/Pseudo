"""M16: the providers allowlist (D16). Where pseudo_brain may send your questions.

What it demonstrates: an ALLOWLIST. pseudo_brain doesn't trust whatever URL or model
name it is given: it reads one committed file, providers.toml, and refuses everything
that isn't in it. The whole file is checked when it is loaded, so a bad entry stops
Pseudo before any question is sent, never halfway through one.

Rules (D16):
  - A private provider (leaves_laptop = false) must live at 127.0.0.1 exactly, and none
    of its model names may contain "cloud" (how Ollama names models that run on its servers).
  - A provider whose data leaves the laptop must use https.
  - Keys never appear here: key_env is the NAME of the .env variable that holds a key.
  - Only a private provider may have a server that pseudo_brain starts (local_server.py).
  - A provider can be switched off with disabled = "<reason>" (P5-perf): it stays listed, so you
    can see why, but using it is refused with that reason. The default provider can't be disabled.
  - (M26, D24) transcribe_model names the provider's speech-to-text model for push-to-talk. Only a
    provider whose data leaves the laptop may have one (D20: no local speech models). A provider
    without one gets no voice input, so private mode never sends your voice anywhere.
"""

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

PROVIDERS_FILE = Path(__file__).resolve().parent / "providers.toml"
LOCALHOST = "127.0.0.1"  # the literal address: "localhost" can be redirected, so it's refused
FIELDS = ("name", "base_url", "key_env", "models", "leaves_laptop", "privacy", "timeout_seconds",
          "max_prompt_tokens")


class ProviderRefused(Exception):
    """This provider or model is not allowed. The message says why, in plain words."""


@dataclass(frozen=True)
class Server:
    """A private provider's own server, which pseudo_brain starts and stops (local_server.py)."""

    command: tuple[str, ...]  # with %VARIABLES% already filled in
    address_env: str  # the environment variable that tells the server where to listen
    cloud_off_file: Path  # a JSON file that must say cloud_off_key: true
    cloud_off_key: str


@dataclass(frozen=True)
class Provider:
    id: str
    name: str
    base_url: str
    key_env: str
    models: tuple[str, ...]  # models[0] is the main model; the rest are 429 fallbacks, in order
    leaves_laptop: bool
    privacy: str
    timeout_seconds: float
    max_prompt_tokens: int
    server: Server | None = None
    disabled: str = ""  # a reason here = switched off: using it is refused with this reason
    transcribe_model: str = ""  # M26: speech to text for push-to-talk; "" = no voice input on this provider

    @property
    def address(self) -> str:
        """host:port of base_url, e.g. "127.0.0.1:11434" (just the host when the URL has no port)."""
        url = urlparse(self.base_url)
        return f"{url.hostname}:{url.port}" if url.port else str(url.hostname)


@dataclass(frozen=True)
class Allowlist:
    providers: dict[str, Provider]
    default: str

    def get(self, provider_id: str) -> Provider:
        if provider_id not in self.providers:
            raise ProviderRefused(f'"{provider_id}" is not in the allowlist ({PROVIDERS_FILE.name}). '
                                  f"Allowed: {', '.join(self.providers)}")
        provider = self.providers[provider_id]
        if provider.disabled:
            raise ProviderRefused(f"{provider_id} is disabled: {provider.disabled}")
        return provider


def provider_info(provider: Provider) -> dict:
    """What an interface shows about a provider (the face's provider bar and privacy note)."""
    return {"id": provider.id, "name": provider.name, "models": list(provider.models),
            "leaves_laptop": provider.leaves_laptop, "privacy": provider.privacy,
            "transcribe_model": provider.transcribe_model,  # M26: "" = no voice input on this provider
            "disabled": provider.disabled}  # M41: why it's switched off, or ""; the face hides it from the pickers


def load_allowlist(path: Path = PROVIDERS_FILE) -> Allowlist:
    """Read and check the whole file. Raises ProviderRefused on the first problem."""
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise ProviderRefused(f"can't read {path.name} ({type(error).__name__})") from None
    entries = data.get("providers")
    if not isinstance(entries, dict) or not entries:
        raise ProviderRefused(f"{path.name} lists no providers")
    providers = {provider_id: checked(provider_id, entry) for provider_id, entry in entries.items()}
    if data.get("default") not in providers:
        raise ProviderRefused(f"the default provider {data.get('default')!r} is not in {path.name}")
    if providers[data["default"]].disabled:
        raise ProviderRefused(f"the default provider {data['default']!r} is disabled")
    return Allowlist(providers, data["default"])


def checked(provider_id: str, entry: dict) -> Provider:
    """One entry -> a Provider, or ProviderRefused saying which rule it breaks."""
    def refuse(reason: str) -> ProviderRefused:
        return ProviderRefused(f"{provider_id}: {reason}")

    missing = [name for name in FIELDS if name not in entry]
    if missing:
        raise refuse(f"missing {', '.join(missing)}")
    models, leaves = entry["models"], entry["leaves_laptop"]
    if not isinstance(leaves, bool):  # "false" in quotes is a string, and a string would count as true
        raise refuse("leaves_laptop must be true or false, without quotes")
    if not isinstance(models, list) or not models or not all(isinstance(m, str) and m for m in models):
        raise refuse("models must be a non-empty list of names")
    if len(set(models)) != len(models):
        raise refuse("a model is listed twice")
    url = urlparse(entry["base_url"])
    if leaves:
        if url.scheme != "https":
            raise refuse("its data leaves the laptop, so its URL must use https")
        if not entry["key_env"]:
            raise refuse("its data leaves the laptop, so it needs key_env")
    else:
        try:
            port = url.port
        except ValueError:  # a port that isn't a number
            port = None
        if url.hostname != LOCALHOST or port is None:
            raise refuse(f"a private provider must be at {LOCALHOST}:<port>, not {url.hostname}")
        cloudy = [m for m in models if "cloud" in m.lower()]
        if cloudy:
            raise refuse(f'"{cloudy[0]}" looks like a cloud model; private mode refuses it')
    disabled = entry.get("disabled", "")
    if not isinstance(disabled, str):
        raise refuse('disabled must be the reason, in quotes, e.g. disabled = "server removed"')
    server = entry.get("server")
    if server is not None and leaves:
        raise refuse("only a private provider may have a server for pseudo_brain to start")
    transcribe = entry.get("transcribe_model", "")
    if not isinstance(transcribe, str) or ("transcribe_model" in entry and not transcribe):
        raise refuse("transcribe_model must be a model name, in quotes")
    if transcribe and not leaves:
        raise refuse("a private provider can't have a transcribe_model (D20: no local speech models)")
    return Provider(provider_id, entry["name"], entry["base_url"], entry["key_env"], tuple(models), leaves,
                    entry["privacy"], float(entry["timeout_seconds"]), int(entry["max_prompt_tokens"]),
                    checked_server(server, refuse) if server is not None else None, disabled, transcribe)


def checked_server(server: dict, refuse) -> Server:
    try:
        command = tuple(os.path.expandvars(part) for part in server["command"])
        if not command or not all(command):
            raise TypeError
        cloud_off = server["cloud_off"]
        cloud_file = Path(os.path.expandvars(cloud_off["file"])).expanduser()
        return Server(command, server["address_env"], cloud_file, cloud_off["key"])
    except (KeyError, TypeError):
        raise refuse("its server needs command, address_env and cloud_off = {file, key}") from None
