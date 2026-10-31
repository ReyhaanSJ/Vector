"""Configuration loading for VECTOR.

Settings come from (lowest to highest priority):
  1. Built-in defaults
  2. ~/.vector/config.toml  (or the file in $VECTOR_CONFIG)
  3. Environment variables  (VECTOR_PROVIDER, VECTOR_MODEL, ...)
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path

HOME_DIR = Path(os.environ.get("VECTOR_HOME", Path.home() / ".vector"))

DEFAULT_CONFIG_TOML = """\
# VECTOR configuration. Every setting is optional.

# Who VECTOR is talking to.
user_name = "Boss"

# "anthropic" (Claude, needs ANTHROPIC_API_KEY) or "ollama" (free, runs locally).
provider = "anthropic"

# Leave empty to use the provider default
# (anthropic: claude-opus-5-5, ollama: llama3.1).
model = ""

# Claude only: low | medium | high | xhigh | max. Low keeps replies snappy.
effort = "low"

# Ollama server address.
ollama_url = "http://localhost:11434"

# Ask before running actions that change things (shell commands, deleting/moving
# files, writing files, typing keys). Strongly recommended to keep this on.
confirm_dangerous = true

# Voice mode
wake_word = "vector"
speak_replies = true

# Extra folders to load your own skills from (*.py files using @tool).
skill_dirs = []
"""


@dataclass
class Config:
    user_name: str = "Boss"
    provider: str = "anthropic"
    model: str = ""
    effort: str = "low"
    ollama_url: str = "http://localhost:11434"
    confirm_dangerous: bool = True
    wake_word: str = "vector"
    speak_replies: bool = True
    skill_dirs: list[str] = field(default_factory=list)

    @property
    def home(self) -> Path:
        return HOME_DIR

    @property
    def resolved_model(self) -> str:
        if self.model:
            return self.model
        return "llama3.1" if self.provider == "ollama" else "claude-opus-5-5"


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
