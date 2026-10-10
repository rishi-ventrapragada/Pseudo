"""M30: the action brain's settings (action_brain.py) and the billing check (claude_billing.py).

Everything is FAKE: the settings come from temporary files, and the check's four sources (the
program on PATH, the account in .env, the outranking credentials, `claude auth status`) are
replaced, so no test reads .env, the registry or a real login, and nothing is launched.
"""

from pathlib import Path

import pytest

from pseudo_brain import claude_billing
from pseudo_brain.action_brain import ActionBrain, load_routing
from pseudo_brain.providers import ProviderRefused

FAKE_ACCOUNT = "owner@fake.invalid"
BRAIN = ActionBrain("Fake Code", ("fake-claude",), "sonnet", ("read_a", "act_b"), "FAKE_ACCOUNT_VAR", "fake note", 5.0)
GOOD = {"loggedIn": True, "authMethod": "claude.ai", "apiProvider": "firstParty", "email": FAKE_ACCOUNT}
MODEL_TOOLS = 'model_tools = ["read_a", "act_b", "switch_x"]\n'  # (D29) every routing file has one
ENTRY = ('[action_brain]\nname = "Fake Code"\ncommand = ["fake-claude"]\nmodel = "sonnet"\n'
         'tools = ["read_a", "act_b"]\naccount_env = "FAKE_ACCOUNT_VAR"\nprivacy = "fake note"\ntimeout_seconds = 5\n')


def settings(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "providers.toml"
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch) -> dict:
    """A machine where the check passes; a test changes one thing and sees it fail."""
    world = {"status": dict(GOOD), "found": [], "account": FAKE_ACCOUNT, "program": ["fake-claude"], "asked": 0}

    def status(command: list[str]) -> dict:
        world["asked"] += 1
        if isinstance(world["status"], Exception):
            raise world["status"]
        return world["status"]
    monkeypatch.setattr(claude_billing, "auth_status", status)
    monkeypatch.setattr(claude_billing, "outranking", lambda: list(world["found"]))
    monkeypatch.setattr(claude_billing, "wanted_account", lambda brain: world["account"])
    monkeypatch.setattr(claude_billing, "program", lambda brain: world["program"])
    return world


# ---------- the settings ----------

def test_the_committed_settings_load_and_never_give_the_switch_or_memory_tools() -> None:
    routing = load_routing()
    assert routing.action_brain is not None and routing.switch_tool
    assert routing.switch_tool not in routing.action_brain.tools
    assert not {"search_memories", "save_memory"} & set(routing.action_brain.tools)
    assert len(routing.action_brain.tools) == 3 and routing.action_brain.model == "sonnet"


def test_no_action_brain_means_everything_stays_on_the_chat_provider(tmp_path: Path) -> None:
    assert load_routing(settings(tmp_path, 'switch_tool = "switch_x"\n' + MODEL_TOOLS)).action_brain is None


@pytest.mark.parametrize("change, reason", [
    (("act_b", "switch_x"), "never be given switch_x"),
    (("act_b", "save_memory"), "never be given save_memory"),
    (("act_b", "looking_at"), "never be given looking_at"),  # (M42) a brain-only tool
    (("act_b", "new_tool"), "new_tool isn't in model_tools"),  # (D29) not on the one list
    (('"FAKE_ACCOUNT_VAR"', '"someone@fake.invalid"'), "never the account itself"),
    (('tools = ["read_a", "act_b"]', "tools = []"), "non-empty lists"),
    (("model = \"sonnet\"\n", ""), "missing model"),
])
def test_bad_action_brain_settings_are_refused(tmp_path: Path, change: tuple[str, str], reason: str) -> None:
    text = 'switch_tool = "switch_x"\n' + MODEL_TOOLS + ENTRY.replace(*change)
    with pytest.raises(ProviderRefused, match=reason):
        load_routing(settings(tmp_path, text))


# ---------- the billing check ----------

def test_a_clean_machine_passes_and_the_line_has_no_account_in_it(world: dict) -> None:
    clean, line = claude_billing.check(BRAIN)
    assert clean and line.startswith("billing check: CLEAN") and "your account: True" in line
    assert "@" not in line and FAKE_ACCOUNT not in line


@pytest.mark.parametrize("key, value", [
    ("loggedIn", False), ("authMethod", "api_key"), ("apiProvider", "bedrock"), ("email", "other@fake.invalid"),
    ("email", None),
])
def test_any_other_login_is_not_clean(world: dict, key: str, value) -> None:
    world["status"][key] = value
    clean, line = claude_billing.check(BRAIN)
    assert not clean and "NOT CLEAN" in line and "@" not in line


def test_an_outranking_credential_is_not_clean_and_is_named(world: dict) -> None:
    world["found"] = ["ANTHROPIC_API_KEY"]
    clean, line = claude_billing.check(BRAIN)
    assert not clean and "ANTHROPIC_API_KEY" in line


def test_an_empty_account_is_refused_before_anything_is_asked(world: dict) -> None:
    world["account"] = ""
    clean, line = claude_billing.check(BRAIN)
    assert not clean and "FAKE_ACCOUNT_VAR isn't filled in" in line and world["asked"] == 0


def test_a_missing_program_is_refused(world: dict) -> None:
    world["program"] = None
    clean, line = claude_billing.check(BRAIN)
    assert not clean and "isn't installed" in line and world["asked"] == 0


@pytest.mark.parametrize("error", [OSError("fake"), ValueError("not json")])
def test_a_check_that_fails_is_not_clean(world: dict, error: Exception) -> None:
    world["status"] = error
    clean, line = claude_billing.check(BRAIN)
    assert not clean and "the billing check itself failed" in line


def test_the_account_is_compared_without_caring_about_case(world: dict) -> None:
    world["status"]["email"] = "Owner@Fake.Invalid"
    assert claude_billing.check(BRAIN)[0]


def test_claude_code_starts_without_any_claude_or_anthropic_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key-1")
    monkeypatch.setenv("CLAUDE_CODE_USE_BEDROCK", "1")
    env = claude_billing.child_env()
    assert "ANTHROPIC_API_KEY" not in env and "CLAUDE_CODE_USE_BEDROCK" not in env
    assert env["DISABLE_TELEMETRY"] == "1" and env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] == "1"


def test_a_variable_set_in_this_process_outranks(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(claude_billing, "stored_names", lambda: set())
    monkeypatch.setattr(claude_billing, "SETTINGS", (tmp_path / "settings.json",))
    monkeypatch.setenv("APPDATA", str(tmp_path))
    for name in claude_billing.OUTRANK:  # whatever this shell happens to have set
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://fake.invalid")
    assert claude_billing.outranking() == ["ANTHROPIC_BASE_URL"]
    monkeypatch.delenv("ANTHROPIC_BASE_URL")
    (tmp_path / "settings.json").write_text('{"apiKeyHelper": "fake.cmd", "env": {"ANTHROPIC_AUTH_TOKEN": "x"}}',
                                            encoding="utf-8")
    assert claude_billing.outranking() == ["apiKeyHelper", "ANTHROPIC_AUTH_TOKEN"]
