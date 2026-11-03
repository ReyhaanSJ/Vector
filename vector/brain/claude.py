"""Claude (Anthropic API) brain. Needs ANTHROPIC_API_KEY or an `ant auth login` profile."""

from __future__ import annotations

import re

from vector.brain.base import MAX_TOOL_ROUNDS, Brain, BrainError, ToolExecutor
from vector.registry import Tool

FALLBACK_BETA = "server-side-fallback-2026-07-01"
# Claude's thinking is tied to the conversation it came from. If earlier history ever differs
# (an older VECTOR, a changed setting), drop that stale thinking instead of failing the request.
BINDING_BETA = "thinking-binding-controls-2026-08-01"
# Models with adaptive thinking (Claude 4.6 and newer; not Haiku 4.5 or older models).
_ADAPTIVE = re.compile(r"claude-(opus|sonnet|fable|mythos)-(4-[6-9]|[5-9])|claude-haiku-[5-9]")
_STALE_THINKING = "bound to a different conversation"


class _StaleThinking(Exception):
    """Claude rejected thinking blocks from earlier in the chat."""


def _tool_content(output):
    """Text, or text plus images (screenshots) in the shape Claude's tool results take."""
    from vector.registry import ToolOutput

    if not isinstance(output, ToolOutput):
        return output
    blocks = [{"type": "image", "source": {"type": "base64", "media_type": mt, "data": data}}
              for mt, data in output.image_b64()]
    return blocks + [{"type": "text", "text": output.text}]


def _block_type(block) -> str:
    return block.get("type", "") if isinstance(block, dict) else getattr(block, "type", "")


class ClaudeBrain(Brain):
    name = "claude"

    def __init__(self, model: str = "claude-opus-5-5", effort: str = "low", client=None):
        if client is None:
            try:
                import anthropic
            except ImportError as exc:  # pragma: no cover
                raise BrainError("The 'anthropic' package is missing: pip install anthropic") from exc
            client = anthropic.Anthropic()
        self.client = client
        self.model = model
        self.effort = effort
        self.messages: list[dict] = []

    def reset(self) -> None:
        self.messages = []

    def _request(self, system: str, tools: list[Tool]) -> dict:
        params = {
            "model": self.model,
            "max_tokens": 16000,
            "system": system,
            "tools": [t.schema() for t in tools],
            "messages": self.messages,
        }
        if self.effort:
            params["output_config"] = {"effort": self.effort}
        betas = []
        if _ADAPTIVE.match(self.model):
            betas.append(BINDING_BETA)
            params["thinking"] = {"type": "adaptive",
                                  "block_binding": {"prefix_mismatch_behavior": "drop_block"}}
        # If a safety classifier declines a request, let the API retry it on Anthropic's
        # recommended fallback model instead of failing. (Haiku has no server-side fallback.)
        if "haiku" not in self.model:
            betas.append(FALLBACK_BETA)
            params["fallbacks"] = "default"
        if betas:
            params["betas"] = betas
        return params

    def _strip_thinking(self) -> None:
        """Last resort when Claude still rejects old thinking: forget it (the replies stay)."""
        for message in self.messages:
            content = message.get("content")
            if message.get("role") == "assistant" and isinstance(content, list):
                message["content"] = [b for b in content if _block_type(b) not in
                                      ("thinking", "redacted_thinking")] or [
                                          {"type": "text", "text": "(done)"}]

    def _call(self, params: dict):
        import anthropic

        no_key = (
            "Claude needs an API key. Set ANTHROPIC_API_KEY (get one at "
            "https://console.anthropic.com) or use the free local option: --provider ollama"
        )
        try:
            return self.client.beta.messages.create(**params)
        except TypeError as exc:
            if "authentication" in str(exc).lower():
                raise BrainError(no_key) from exc
            raise
        except anthropic.AuthenticationError as exc:
            raise BrainError("Claude rejected the API key. " + no_key) from exc
        except anthropic.NotFoundError as exc:
            raise BrainError(f"Model '{self.model}' was not found. Check 'model' in your config.") from exc
        except anthropic.BadRequestError as exc:
            if _STALE_THINKING in str(exc.message):
                raise _StaleThinking() from exc
            raise BrainError(f"Claude API error ({exc.status_code}): {exc.message}") from exc
        except anthropic.RateLimitError as exc:
            raise BrainError("Claude is rate-limiting us. Give it a few seconds and try again.") from exc
        except anthropic.APIStatusError as exc:
            raise BrainError(f"Claude API error ({exc.status_code}): {exc.message}") from exc
        except anthropic.APIConnectionError as exc:
            raise BrainError("Couldn't reach Claude. Check your internet connection.") from exc

    def respond(self, user_text: str, system: str, tools: list[Tool], execute: ToolExecutor) -> str:
        checkpoint = len(self.messages)
        self.messages.append({"role": "user", "content": user_text})
        try:
            return self._loop(system, tools, execute)
        except BaseException:  # errors, Esc, Ctrl+C: drop the half-finished turn
            del self.messages[checkpoint:]  # keep history valid so the next request works
            raise

    def _loop(self, system: str, tools: list[Tool], execute: ToolExecutor) -> str:
        spoken: list[str] = []
        for _ in range(MAX_TOOL_ROUNDS):
            try:
                response = self._call(self._request(system, tools))
            except _StaleThinking:
                self._strip_thinking()
                try:
                    response = self._call(self._request(system, tools))
                except _StaleThinking as exc:
                    raise BrainError("Claude couldn't continue this chat. Type /reset to start "
                                     "a fresh one.") from exc

            if response.stop_reason == "refusal":
                raise BrainError("Sorry, I can't help with that one.")

            # Keep the full content (including thinking blocks) so the history stays valid.
            self.messages.append({"role": "assistant", "content": response.content})
            text = "".join(b.text for b in response.content if b.type == "text").strip()
            if text:
                spoken.append(text)

            if response.stop_reason == "pause_turn":
                continue
            if response.stop_reason != "tool_use":
                break

            results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                output, is_error = execute(block.name, dict(block.input or {}))
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": _tool_content(output),
                    "is_error": is_error,
                })
            self.messages.append({"role": "user", "content": results})
        else:
            spoken.append("(I stopped after too many steps - tell me if you want me to keep going.)")
        return spoken[-1] if spoken else "Done."
