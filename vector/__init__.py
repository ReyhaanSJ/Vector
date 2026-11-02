"""VECTOR - an open-source, JARVIS-style AI assistant that automates your laptop."""

__version__ = "0.2.2"

from vector.registry import tool  # noqa: E402  (re-exported for skill authors)

__all__ = ["tool", "__version__"]
