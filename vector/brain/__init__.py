"""AI back-ends ("brains") that decide which skills to run."""

from __future__ import annotations

from typing import TYPE_CHECKING

from vector.brain.base import Brain, BrainError, ToolExecutor

if TYPE_CHECKING:
    from vector.config import Config

__all__ = ["Brain", "BrainError", "ToolExecutor", "create_brain"]


def create_brain(config: Config) -> Brain:
    provider = config.provider.lower()
    if provider in {"anthropic", "claude"}:
        from vector.brain.claude import ClaudeBrain

        return ClaudeBrain(model=config.resolved_model, effort=config.effort)
    if provider == "ollama":
        from vector.brain.ollama import OllamaBrain

        return OllamaBrain(model=config.resolved_model, base_url=config.ollama_url)
    raise BrainError(f"Unknown provider '{config.provider}'. Use 'anthropic' or 'ollama'.")
