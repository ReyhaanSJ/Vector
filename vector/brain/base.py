from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable

from vector.registry import Tool

# execute(tool_name, arguments) -> (result_text, is_error)
ToolExecutor = Callable[[str, dict], tuple[str, bool]]

MAX_TOOL_ROUNDS = 15


class BrainError(RuntimeError):
    """A problem talking to the AI provider, phrased for the user."""


class Brain(ABC):
    """Holds one conversation and runs the think -> act -> observe loop."""

    name = "brain"

    @abstractmethod
    def respond(self, user_text: str, system: str, tools: list[Tool], execute: ToolExecutor) -> str:
        """Handle one user request, calling tools as needed, and return the final reply."""

    @abstractmethod
    def reset(self) -> None:
        """Forget the conversation so far."""
