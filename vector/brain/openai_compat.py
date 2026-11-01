"""Brain for OpenAI-style chat APIs, used for OpenRouter (free cloud models such as
qwen/qwen3.8-27b:free). Get a free key at https://openrouter.ai/keys and set
OPENROUTER_API_KEY, or let the installer do it."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from vector.brain.base import MAX_TOOL_ROUNDS, Brain, BrainError, ToolExecutor
from vector.registry import Tool

OPENROUTER_URL = "https://openrouter.ai/api/v1"
MAX_HISTORY = 60


class OpenAICompatBrain(Brain):
    name = "openrouter"

    def __init__(self, model: str, base_url: str = OPENROUTER_URL, api_key: str | None = None,
                 post=None):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key if api_key is not None else os.environ.get("OPENROUTER_API_KEY", "")
        self.messages: list[dict] = []
        self._post = post or self._http_post

    def reset(self) -> None:
        self.messages = []

    def _http_post(self, payload: dict) -> dict:
        if not self.api_key:
            raise BrainError("OpenRouter needs a free API key: make one at https://openrouter.ai/keys, "
                             "then set OPENROUTER_API_KEY (or run VECTOR's setup again).")
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
                "HTTP-Referer": "https://github.com/ReyhaanSJ/Vector",
                "X-Title": "VECTOR",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")[:300]
            if exc.code == 401:
                raise BrainError("OpenRouter rejected the API key. Check OPENROUTER_API_KEY.") from exc
            if exc.code == 402:
                raise BrainError("That OpenRouter model isn't free. Use one ending in ':free', e.g. "
                                 "vector --set model=qwen/qwen3.8-27b:free") from exc
            if exc.code == 404:
                raise BrainError(f"OpenRouter doesn't know the model '{self.model}'.") from exc
            if exc.code == 429:
                raise BrainError("Free OpenRouter limit reached for now. Wait a bit, or switch to the "
                                 "local AI: vector --set provider=ollama") from exc
            raise BrainError(f"OpenRouter error {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise BrainError("Couldn't reach OpenRouter. Check your internet connection.") from exc

    def respond(self, user_text: str, system: str, tools: list[Tool], execute: ToolExecutor) -> str:
        checkpoint = len(self.messages)
        self.messages.append({"role": "user", "content": user_text})
        tool_defs = [{"type": "function", "function": {
            "name": t.name, "description": t.description, "parameters": t.parameters}} for t in tools]
        try:
            for _ in range(MAX_TOOL_ROUNDS):
                history = self.messages[-MAX_HISTORY:]
                while history and history[0]["role"] != "user":
                    history = history[1:]
                data = self._post({
                    "model": self.model,
                    "messages": [{"role": "system", "content": system}, *history],
                    "tools": tool_defs,
                    "tool_choice": "auto",
                })
                if data.get("error"):
                    raise BrainError(f"OpenRouter error: {data['error'].get('message', data['error'])}")
                msg = (data.get("choices") or [{}])[0].get("message") or {}
                calls = msg.get("tool_calls") or []
                entry = {"role": "assistant", "content": msg.get("content") or ""}
                if calls:
                    entry["tool_calls"] = calls
                self.messages.append(entry)
                if not calls:
                    return (msg.get("content") or "Done.").strip()
                for call in calls:
                    fn = call.get("function", {})
                    try:
                        args = json.loads(fn.get("arguments") or "{}")
                    except ValueError:
                        args = {}
                    output, _ = execute(fn.get("name", ""), args if isinstance(args, dict) else {})
                    self.messages.append({"role": "tool", "tool_call_id": call.get("id", ""),
                                          "content": output})
            return "(I stopped after too many steps.)"
        except BrainError:
            del self.messages[checkpoint:]
            raise
