"""Tests for M16: the providers allowlist (D16, pseudo_brain/providers.py).

Every list here is FAKE, written to a temp folder, except the first two tests, which
check the committed providers.toml itself. No network: loading a list sends nothing.
"""

import copy
import json
import re
from pathlib import Path

import pytest

from pseudo_brain.providers import PROVIDERS_FILE, ProviderRefused, load_allowlist

REASON = "Ollama removed 2026-10-01 to free laptop resources; reinstall to re-enable"  # P5-perf

GOOD = {
    "groq": {"name": "Fake cloud", "base_url": "https://fake.invalid/v1", "key_env": "FAKE_KEY",
             "models": ["big", "small"], "leaves_laptop": True, "privacy": "fake note", "timeout_seconds": 60,
             "max_prompt_tokens": 3000},
    "local": {"name": "Fake local", "base_url": "http://127.0.0.1:11434/v1", "key_env": "", "models": ["tiny:3b"],
              "leaves_laptop": False, "privacy": "fake note", "timeout_seconds": 180, "max_prompt_tokens": 2500,
              "server": {"command": ["%FAKE_M16_DIR%\\fake.exe", "serve"], "address_env": "FAKE_HOST",
                         "cloud_off": {"file": "%FAKE_M16_DIR%\\server.json", "key": "cloud_off"}}},
}


def toml_value(value) -> str:
    """JSON strings, numbers, booleans and lists are valid TOML; dicts become inline tables."""
    if isinstance(value, dict):
        return "{" + ", ".join(f"{key} = {toml_value(item)}" for key, item in value.items()) + "}"
    return json.dumps(value)


def write_list(tmp_path: Path, providers: dict, default: str = "groq") -> Path:
    lines = [f"default = {json.dumps(default)}"]
    for provider_id, entry in providers.items():
        lines += [f"[providers.{provider_id}]"] + [f"{key} = {toml_value(value)}" for key, value in entry.items()]
    path = tmp_path / "providers.toml"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def changed(provider_id: str, **fields) -> dict:
    """GOOD with some fields of one provider replaced (a value of None removes the field)."""
    providers = copy.deepcopy(GOOD)
    for key, value in fields.items():
        if value is None:
            providers[provider_id].pop(key)
        else:
            providers[provider_id][key] = value
    return providers


def refusal(tmp_path: Path, providers: dict, default: str = "groq") -> str:
    with pytest.raises(ProviderRefused) as refused:
        load_allowlist(write_list(tmp_path, providers, default))
    return str(refused.value)


# ---------- the committed list ----------

def test_the_committed_allowlist_matches_d16() -> None:
    allowlist = load_allowlist()
    groq, local = allowlist.get("groq"), allowlist.providers["local"]  # local is disabled, so get() refuses it
    assert allowlist.default == "groq" and list(allowlist.providers) == ["groq", "local"]
    assert groq.models == ("openai/gpt-oss-120b", "openai/gpt-oss-20b") and groq.base_url.startswith("https://")
    assert groq.leaves_laptop and groq.key_env == "LLM_API_KEY" and groq.server is None
    assert local.models == ("granite4.1:3b",) and local.base_url == "http://127.0.0.1:11434/v1"
    assert not local.leaves_laptop and local.address == "127.0.0.1:11434"
    assert local.server.command[-1] == "serve" and local.server.cloud_off_key == "disable_ollama_cloud"
    assert local.disabled == REASON and not groq.disabled
    assert groq.transcribe_model == "whisper-large-v3" and not local.transcribe_model  # M26, D24


def test_the_committed_allowlist_holds_no_key() -> None:
    text = PROVIDERS_FILE.read_text(encoding="utf-8")
    assert not re.search(r"\b(?:gsk|sk|sk-ant)[-_][A-Za-z0-9_\-]{8,}", text)
    assert all(re.fullmatch(r"[A-Z_]*", p.key_env) for p in load_allowlist().providers.values())


# ---------- a good list ----------

def test_a_good_list_loads_and_fills_in_variables(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_M16_DIR", str(tmp_path))
    allowlist = load_allowlist(write_list(tmp_path, GOOD))
    local = allowlist.get("local")
    assert allowlist.default == "groq" and local.models == ("tiny:3b",)
    assert local.server.command == (str(tmp_path / "fake.exe"), "serve")
    assert local.server.cloud_off_file == tmp_path / "server.json"


def test_an_unknown_provider_is_refused_and_the_allowed_ones_are_named(tmp_path: Path) -> None:
    with pytest.raises(ProviderRefused, match='"cloudy" is not in the allowlist.*Allowed: groq, local'):
        load_allowlist(write_list(tmp_path, GOOD)).get("cloudy")


# ---------- private mode can't leave the laptop ----------

@pytest.mark.parametrize("url", [
    "https://api.groq.com/openai/v1", "http://localhost:11434/v1", "http://192.168.1.5:11434/v1",
    "http://127.0.0.1.evil.com:11434/v1", "http://127.0.0.1@evil.com:11434/v1", "http://127.0.0.1/v1",
    "http://127.0.0.1:abc/v1"])
def test_a_private_provider_must_be_at_127_0_0_1(tmp_path: Path, url: str) -> None:
    assert "must be at 127.0.0.1" in refusal(tmp_path, changed("local", base_url=url))


@pytest.mark.parametrize("name", ["gpt-oss:120b-cloud", "qwen3:4b-CLOUD", "Cloud/tiny"])
def test_a_private_provider_refuses_cloud_model_names(tmp_path: Path, name: str) -> None:
    assert "looks like a cloud model" in refusal(tmp_path, changed("local", models=["tiny:3b", name]))


def test_leaves_laptop_must_be_a_real_boolean(tmp_path: Path) -> None:
    # "false" in quotes is a non-empty string, which Python would treat as TRUE
    assert "without quotes" in refusal(tmp_path, changed("local", leaves_laptop="false"))


def test_only_a_private_provider_may_have_a_server(tmp_path: Path) -> None:
    server = GOOD["local"]["server"]
    assert "only a private provider" in refusal(tmp_path, changed("groq", server=server))
    assert "its server needs" in refusal(tmp_path, changed("local", server={"command": ["x.exe"]}))
    assert "its server needs" in refusal(tmp_path, changed("local", server={**server, "command": []}))


# ---------- cloud providers ----------

def test_a_cloud_provider_must_use_https_and_name_its_key(tmp_path: Path) -> None:
    assert "must use https" in refusal(tmp_path, changed("groq", base_url="http://fake.invalid/v1"))
    assert "needs key_env" in refusal(tmp_path, changed("groq", key_env=""))


# ---------- broken lists ----------

def test_broken_lists_are_refused_with_a_reason(tmp_path: Path) -> None:
    assert "missing privacy" in refusal(tmp_path, changed("groq", privacy=None))
    assert "non-empty list" in refusal(tmp_path, changed("groq", models=[]))
    assert "listed twice" in refusal(tmp_path, changed("groq", models=["big", "big"]))
    assert "default provider 'nope'" in refusal(tmp_path, GOOD, default="nope")
    assert "lists no providers" in refusal(tmp_path, {})
    bad = tmp_path / "broken.toml"
    bad.write_text("default = [unclosed", encoding="utf-8")
    with pytest.raises(ProviderRefused, match="can't read broken.toml"):
        load_allowlist(bad)


# ---------- a disabled provider (P5-perf) ----------

def test_the_committed_local_provider_is_refused_with_its_reason() -> None:
    with pytest.raises(ProviderRefused, match=re.escape(f"local is disabled: {REASON}")):
        load_allowlist().get("local")


def test_a_disabled_provider_stays_listed_but_is_refused(tmp_path: Path) -> None:
    allowlist = load_allowlist(write_list(tmp_path, changed("local", disabled="fake reason")))
    assert list(allowlist.providers) == ["groq", "local"]  # still listed, so you can see why it's off
    with pytest.raises(ProviderRefused, match="local is disabled: fake reason"):
        allowlist.get("local")
    assert allowlist.get("groq").name == "Fake cloud"


def test_disabled_must_be_a_reason_and_the_default_cant_be_disabled(tmp_path: Path) -> None:
    assert "disabled must be the reason" in refusal(tmp_path, changed("local", disabled=True))
    assert "the default provider 'groq' is disabled" in refusal(tmp_path, changed("groq", disabled="fake reason"))


# ---------- M26: the speech-to-text model ----------

def test_a_cloud_provider_may_name_a_transcribe_model(tmp_path: Path) -> None:
    allowlist = load_allowlist(write_list(tmp_path, changed("groq", transcribe_model="ears")))
    assert allowlist.get("groq").transcribe_model == "ears"
    assert load_allowlist(write_list(tmp_path, GOOD)).get("groq").transcribe_model == ""  # none = no voice input


def test_a_transcribe_model_must_be_a_name_and_never_on_a_private_provider(tmp_path: Path) -> None:
    for bad in ("", 42, ["ears"]):
        assert "transcribe_model must be a model name" in refusal(tmp_path, changed("groq", transcribe_model=bad))
    assert "D20" in refusal(tmp_path, changed("local", transcribe_model="local-ears"))
