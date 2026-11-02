"""Configuration loading for VECTOR.

Settings come from (lowest to highest priority):
  1. Built-in defaults
  2. ~/.vector/config.toml  (or the file in $VECTOR_CONFIG)
  3. Environment variables  (VECTOR_PROVIDER, VECTOR_MODEL, ...)
"""

from __future__ import annotations

import os
import re
import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path

HOME_DIR = Path(os.environ.get("VECTOR_HOME", Path.home() / ".vector"))

DEFAULT_CONFIG_TOML = """\
# VECTOR configuration. Every setting is optional.

# Who VECTOR is talking to.
user_name = "Boss"

# Which AI runs VECTOR:
#   "ollama"     free, runs on this computer
#   "openrouter" free cloud models (needs a free OPENROUTER_API_KEY)
#   "anthropic"  Claude, the smartest (needs a paid ANTHROPIC_API_KEY)
#   "auto"       Claude if its key is set, else OpenRouter if its key is set, else Ollama
provider = "auto"

# Leave empty for the default
# (Claude: claude-opus-5-5, Ollama: llama3.2, OpenRouter: "auto:free" = the best free
# model available right now). See the options with:  vector --models
# Change it any time with:  vector --set model=google/gemma-4-31b-it:free
model = ""

# Claude only: low | medium | high | xhigh | max. Low keeps replies snappy.
effort = "low"

# Ollama server address.
ollama_url = "http://localhost:11434"

# Ask before running actions that change things (shell commands, deleting/moving
# files, writing files, typing keys). Strongly recommended to keep this on.
confirm_dangerous = true

# Voice: say the wake word, then your request. No button needed.
wake_word = "vector"
speak_replies = true
# Start listening for the wake word as soon as the VECTOR app opens.
listen_on_start = true
# Offline speech-to-text model: tiny.en (fastest), base.en, small.en (most accurate).
whisper_model = "base.en"

# Keyboard shortcut that pops up the summon bar from anywhere.
hotkey = "ctrl+shift+space"

# Check GitHub once a day for a new VECTOR version and offer it from the tray icon.
check_updates = true

# Extra folders to load your own skills from (*.py files using @tool).
skill_dirs = []
"""


DEFAULT_MODELS = {
    "anthropic": "claude-opus-5-5",
    "openrouter": "auto:free",
    "ollama": "llama3.2",
}


@dataclass
class Config:
    user_name: str = "Boss"
    provider: str = "auto"
    model: str = ""
    effort: str = "low"
    ollama_url: str = "http://localhost:11434"
    confirm_dangerous: bool = True
    wake_word: str = "vector"
    speak_replies: bool = True
    listen_on_start: bool = True
    whisper_model: str = "base.en"
    hotkey: str = "ctrl+shift+space"
    check_updates: bool = True
    skill_dirs: list[str] = field(default_factory=list)

    @property
    def home(self) -> Path:
        return HOME_DIR

    @property
    def resolved_provider(self) -> str:
        """The provider actually used: "auto" means Claude when a key is set, else Ollama."""
        provider = self.provider.lower().strip()
        if provider == "claude" or self.model.lower().startswith("claude-"):
            return "anthropic"  # a Claude model name always means Claude
        if provider == "auto":
            if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
                return "anthropic"
            if os.environ.get("OPENROUTER_API_KEY"):
                return "openrouter"
            return "ollama"
        return provider

    @property
    def resolved_model(self) -> str:
        if self.model:
            return self.model
        return DEFAULT_MODELS.get(self.resolved_provider, "claude-opus-5-5")


def config_path() -> Path:
    return Path(os.environ.get("VECTOR_CONFIG", HOME_DIR / "config.toml"))


def _coerce(value: str, current):
    if isinstance(current, bool):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    if isinstance(current, list):
        return [v for v in value.split(os.pathsep) if v]
    return value


def load_config(path: Path | None = None) -> Config:
    cfg = Config()
    path = path or config_path()
    if path.exists():
        with path.open("rb") as fh:
            data = tomllib.load(fh)
        known = {f.name for f in fields(Config)}
        for key, value in data.items():
            if key in known:
                setattr(cfg, key, value)
    for f in fields(Config):
        env = os.environ.get(f"VECTOR_{f.name.upper()}")
        if env is not None:
            setattr(cfg, f.name, _coerce(env, getattr(cfg, f.name)))
    return cfg


def write_default_config(path: Path | None = None, overwrite: bool = False) -> Path:
    path = path or config_path()
    if path.exists() and not overwrite:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(DEFAULT_CONFIG_TOML, encoding="utf-8")
    return path


def set_config_value(key: str, value: str, path: Path | None = None) -> Path:
    """Change one setting in the config file, keeping the comments around it."""
    known = {f.name: f for f in fields(Config)}
    if key not in known:
        raise KeyError(f"Unknown setting '{key}'. Settings: {', '.join(known)}")
    default = getattr(Config(), key)
    parsed = _coerce(value, default)
    if isinstance(parsed, bool):
        literal = "true" if parsed else "false"
    elif isinstance(parsed, list):
        literal = "[" + ", ".join(_toml_str(v) for v in parsed) + "]"
    else:
        literal = _toml_str(str(parsed))
    path = write_default_config(path)
    lines = path.read_text(encoding="utf-8").splitlines()
    pattern = re.compile(rf"^\s*{re.escape(key)}\s*=")
    for i, line in enumerate(lines):
        if pattern.match(line):
            lines[i] = f"{key} = {literal}"
            break
    else:
        lines.append(f"{key} = {literal}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _toml_str(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def describe_model(provider: str, model: str) -> str:
    """Friendly name for the footer and terminal: 'claude-haiku-5-5' -> 'Claude Haiku 5.5'."""
    if provider == "anthropic" and model.startswith("claude-"):
        parts = model.split("-")[1:]
        words = [p.capitalize() for p in parts if not p.isdigit()]
        numbers = [p for p in parts if p.isdigit()]
        return " ".join(["Claude", *words]) + (" " + ".".join(numbers) if numbers else "")
    if model == "auto:free":
        return "Free cloud AI (auto)"
    name = model.split("/")[-1].removesuffix(":free")
    where = {"ollama": "local", "openrouter": "free cloud"}.get(provider)
    return f"{name} ({where})" if where else name
