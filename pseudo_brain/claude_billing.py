"""M30: the billing check that runs before EVERY Claude Code launch (D16, D26).

What it demonstrates: checking who pays, and who sees your data, BEFORE sending anything.
Claude Code picks its credentials in an order: an API key or token in the environment, a
helper named in its settings, another cloud provider's switch... and only then your
subscription login. Any of those would silently send Pseudo's (redacted) screen text
somewhere D16 doesn't allow, or bill it per token (D3: zero budget). So the check passes only if:
  1. none of the variables that outrank the login is set (this process, or stored in Windows);
  2. no Claude Code settings file names a key helper or sets one of those variables;
  3. `claude auth status` says: logged in, through claude.ai, first party;
  4. the logged-in account is the one named in .env (its "Help improve Claude" setting is
     the one D16 relies on). The account is COMPARED here, never printed, logged or returned.
The result is a line of names and booleans only. Measured in M15 and M29 (108 launches).
"""

import json
import os
import shutil
import subprocess
import winreg
from pathlib import Path

from dotenv import load_dotenv

from pseudo_brain.action_brain import ActionBrain
from pseudo_brain.model import ENV_PATH

OUTRANK = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN", "CLAUDE_CODE_USE_BEDROCK",
           "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_FOUNDRY", "CLAUDE_CODE_USE_ANTHROPIC_AWS", "ANTHROPIC_PROFILE",
           "ANTHROPIC_FEDERATION_RULE_ID", "ANTHROPIC_ORGANIZATION_ID", "ANTHROPIC_BASE_URL", "CLAUDE_CONFIG_DIR")
SETTINGS = (Path.home() / ".claude" / "settings.json", Path.home() / ".claude" / "settings.local.json",
            Path(r"C:\Program Files\ClaudeCode\managed-settings.json"),
            Path(r"C:\ProgramData\ClaudeCode\managed-settings.json"))
WINDOWS_ENV = ((winreg.HKEY_CURRENT_USER, "Environment"),
               (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"))
NO_WINDOW = subprocess.CREATE_NO_WINDOW  # a console window flashing up would land in front of your work


def child_env() -> dict[str, str]:
    """The environment Claude Code is started with: every CLAUDE*/ANTHROPIC* variable removed, telemetry off."""
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith(("CLAUDE", "ANTHROPIC"))}
    env.update(DISABLE_TELEMETRY="1", DISABLE_ERROR_REPORTING="1", CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC="1")
    return env


def stored_names() -> set[str]:
    """The NAMES of the variables stored in Windows for this user and this laptop."""
    names: set[str] = set()
    for root, path in WINDOWS_ENV:
        try:
            with winreg.OpenKey(root, path) as key:
                names |= {winreg.EnumValue(key, i)[0].upper() for i in range(winreg.QueryInfoKey(key)[1])}
        except OSError:
            pass
    return names


def outranking() -> list[str]:
    """Everything set that Claude Code would use BEFORE the subscription login (names only)."""
    stored = stored_names()
    found = [name for name in OUTRANK if name in stored or os.environ.get(name)]
    for path in SETTINGS:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            found += ["apiKeyHelper"] if "apiKeyHelper" in data else []
            found += [name for name in (data.get("env") or {}) if name in OUTRANK]
    if os.environ.get("APPDATA") and (Path(os.environ["APPDATA"]) / "Anthropic").exists():
        found.append("Anthropic profile folder")
    return found


def program(brain: ActionBrain) -> list[str] | None:
    """The action brain's command with its program found on PATH; None if it isn't installed."""
    found = shutil.which(brain.command[0])
    return [found, *brain.command[1:]] if found else None


def auth_status(command: list[str]) -> dict:
    done = subprocess.run([*command, "auth", "status"], capture_output=True, text=True, env=child_env(),
                          creationflags=NO_WINDOW, timeout=60)
    return json.loads(done.stdout)


def wanted_account(brain: ActionBrain) -> str:
    """Your account, from the .env variable providers.toml names. '' if it isn't filled in."""
    load_dotenv(ENV_PATH)
    return (os.getenv(brain.account_env) or "").strip().lower()


def check(brain: ActionBrain) -> tuple[bool, str]:
    """(clean, why). clean only if Claude Code will use your subscription login, on your account.

    Any error while checking counts as not clean: nothing is launched on a guess."""
    try:
        command = program(brain)
        if command is None:
            return False, f"{brain.name} isn't installed (no '{brain.command[0]}' on PATH)"
        account = wanted_account(brain)
        if not account:
            return False, f"{brain.account_env} isn't filled in in .env (see .env.example)"
        found = outranking()
        status = auth_status(command)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        return False, f"the billing check itself failed ({type(error).__name__})"
    login = (status.get("loggedIn"), status.get("authMethod"), status.get("apiProvider"))
    yours = str(status.get("email") or "").strip().lower() == account
    clean = not found and login == (True, "claude.ai", "firstParty") and yours
    return clean, (f"billing check: {'CLEAN' if clean else 'NOT CLEAN'} | outranking credentials set: "
                   f"{', '.join(found) or 'none'} | login: {login[1]} / {login[2]} | your account: {yours}")
