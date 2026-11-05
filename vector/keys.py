"""Saving and checking AI keys: `vector --set-key openrouter` (or claude).

Keys are saved where VECTOR's app can read them even when it's opened from the Dock, Start Menu
or at login: the Keychain on a Mac, your user environment variables on Windows.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

PROVIDERS = {
    "openrouter": ("OPENROUTER_API_KEY", "sk-or-", "https://openrouter.ai/keys"),
    "claude": ("ANTHROPIC_API_KEY", "sk-ant-", "https://console.anthropic.com (API keys page)"),
}
PROVIDERS["anthropic"] = PROVIDERS["claude"]


def clean(key: str) -> str:
    """Pasted keys often pick up spaces, quotes or a line break."""
    return key.strip().strip("\"'").strip()


def wrong_kind(provider: str, key: str) -> str | None:
    """A friendly warning if the key is clearly for a different service."""
    _, prefix, _ = PROVIDERS[provider]
    if key.startswith(prefix):
        return None
    for other, (_, other_prefix, _) in PROVIDERS.items():
        if other != provider and key.startswith(other_prefix):
            name = "a Claude (Anthropic)" if other_prefix == "sk-ant-" else "an OpenRouter"
            return f"That looks like {name} key, not a {provider.title()} key."
    return f"{provider.title()} keys start with {prefix}; this one doesn't."


def check_openrouter(key: str, timeout: int = 15) -> tuple[bool | None, str]:
    """Ask OpenRouter whether the key works. (True, info) / (False, why) / (None, couldn't check)."""
    req = urllib.request.Request("https://openrouter.ai/api/v1/key",
                                 headers={"Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read()).get("data", {})
        return True, data.get("label") or "key works"
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            return False, "OpenRouter says this key isn't valid (deleted, or copied wrong)."
        return None, f"OpenRouter answered {exc.code}"
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return None, f"couldn't reach OpenRouter ({exc})"


def check_claude(key: str) -> tuple[bool | None, str]:
    try:
        import anthropic

        anthropic.Anthropic(api_key=key).models.list(limit=1)
        return True, "key works"
    except Exception as exc:
        name = type(exc).__name__
        if name in ("AuthenticationError", "PermissionDeniedError"):
            return False, "Anthropic says this key isn't valid (deleted, or copied wrong)."
        return None, f"couldn't check it ({name})"


def save(name: str, value: str) -> str:
    """Save a key for VECTOR's app. Returns where it went."""
    os.environ[name] = value
    if sys.platform == "darwin":
        from vector.macos import keychain_set

        if keychain_set(name, value):
            return "your Mac's Keychain"
        raise RuntimeError("Couldn't save it in the Keychain.")
    if sys.platform == "win32":
        # Saved for your Windows account; apps opened from now on see it.
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command",
             f"[Environment]::SetEnvironmentVariable('{name}', $env:{name}, 'User')"],
            env=dict(os.environ), capture_output=True, timeout=60, check=False,
            creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode != 0:
            raise RuntimeError(f"Couldn't save it: {result.stderr.strip()[:200]}")
        return "your Windows user settings"
    return f"this terminal only (add  export {name}=...  to your shell profile to keep it)"


def stored(name: str) -> str:
    """The key VECTOR's app would use (cleaned)."""
    value = os.environ.get(name, "")
    if not value and sys.platform == "darwin":
        from vector.macos import keychain_get

        value = keychain_get(name)
    return clean(value)
