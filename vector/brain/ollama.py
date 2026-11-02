"""Local brain using Ollama (https://ollama.com). Free, private, works offline.

Install Ollama, then pull a model that supports tool calling, e.g.:
    ollama pull llama3.1      (or qwen2.5, mistral-nemo ...)
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from vector.brain.base import MAX_TOOL_ROUNDS, Brain, BrainError, ToolExecutor
from vector.registry import Tool, ToolOutput

MAX_HISTORY = 40  # local models have small context windows


class OllamaBrain(Brain):
    name = "ollama"

    def __init__(self, model: str = "llama3.1", base_url: str = "http://localhost:11434", post=None):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.messages: list[dict] = []
        self._post = post or self._http_post

    @property
    def can_see(self) -> bool:
        """Rough check for vision models, which accept pictures."""
        name = self.model.lower()
        return any(tag in name for tag in ("vision", "-vl", "vl:", "llava", "gemma3", "qwen2.5vl",
                                           "minicpm-v", "moondream", "llama4"))

    def reset(self) -> None:
        self.messages = []

    def _http_post(self, payload: dict) -> dict:
        req = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            body = exc.read().decode(errors="replace")
            if exc.code == 404:
                raise BrainError(f"Ollama doesn't have '{self.model}'. Run: ollama pull {self.model}") from exc
            raise BrainError(f"Ollama error {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            raise BrainError(
                f"Can't reach the free local AI (Ollama) at {self.base_url}. Install it from "
                "https://ollama.com, or if it's installed, start the Ollama app. "
                "Have a Claude API key instead? Set ANTHROPIC_API_KEY."
            ) from exc

    def respond(self, user_text: str, system: str, tools: list[Tool], execute: ToolExecutor) -> str:
        checkpoint = len(self.messages)
        self.messages.append({"role": "user", "content": user_text})
        tool_defs = [
            {"type": "function",
             "function": {"name": t.name, "description": t.description, "parameters": t.parameters}}
            for t in tools
        ]
        try:
            for _ in range(MAX_TOOL_ROUNDS):
                history = self.messages[-MAX_HISTORY:]
                while history and history[0]["role"] != "user":
                    history = history[1:]
                data = self._post({
                    "model": self.model,
                    "messages": [{"role": "system", "content": system}, *history],
                    "tools": tool_defs,
                    "stream": False,
                })
                msg = data.get("message", {})
                calls = msg.get("tool_calls") or []
                self.messages.append({
                    "role": "assistant", "content": msg.get("content", ""),
                    **({"tool_calls": calls} if calls else {}),
                })
                if not calls:
                    return (msg.get("content") or "Done.").strip()
                for call in calls:
                    fn = call.get("function", {})
                    args = fn.get("arguments") or {}
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except ValueError:
                            args = {}
                    output, _ = execute(fn.get("name", ""), args)
                    message = {"role": "tool", "tool_name": fn.get("name", "")}
                    if isinstance(output, ToolOutput):
                        if output.images and self.can_see:
                            message["images"] = [data for _, data in output.image_b64()]
                        elif output.images:
                            output = ToolOutput(output.text + " (This local AI model can't see "
                                                "pictures. For screen tasks use Claude, or a vision "
                                                "model such as qwen2.5vl or gemma3.)")
                        output = output.text
                    message["content"] = output
                    self.messages.append(message)
            return "(I stopped after too many steps.)"
        except BaseException:  # errors, Esc, Ctrl+C: drop the half-finished turn
            del self.messages[checkpoint:]
            raise
