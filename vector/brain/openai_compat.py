"""Brain for OpenAI-style chat APIs, used for OpenRouter's free cloud models.
Get a free key at https://openrouter.ai/keys and set OPENROUTER_API_KEY (setup does this).

Free models come and go, so by default (model "auto:free") VECTOR asks OpenRouter which
free models can use tools right now and picks the best one it knows.
`vector --models` lists them; `vector --set model=<id>` picks one yourself."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

from vector.brain.base import MAX_TOOL_ROUNDS, Brain, BrainError, ToolExecutor
from vector.registry import Tool

OPENROUTER_URL = "https://openrouter.ai/api/v1"
MAX_HISTORY = 60
AUTO_FREE = "auto:free"

# Best first. Anything else that's free and supports tools is used if none of these are there.
FREE_MODEL_PREFERENCE = [
    "google/gemma-4-31b-it:free",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "qwen/qwen3.8-27b:free",
    "nvidia/nemotron-3.5-super-vl:free",
    "google/gemma-4-26b-a4b-it:free",
    "xingchen-agi/xing4.0-29b-a4b:free",
]


def list_free_tool_models(base_url: str = OPENROUTER_URL, fetch=None) -> list[str]:
    """IDs of OpenRouter's free models that support tool calling, right now."""
    if fetch is None:
        def fetch(url):
            req = urllib.request.Request(url, headers={"User-Agent": "VECTOR"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read())
    try:
        data = fetch(f"{base_url.rstrip('/')}/models").get("data", [])
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise BrainError("Couldn't get OpenRouter's model list. Check your internet connection.") from exc
    return [m["id"] for m in data
            if m.get("id", "").endswith(":free") and "tools" in (m.get("supported_parameters") or [])]


def pick_free_model(available: list[str]) -> str | None:
    for preferred in FREE_MODEL_PREFERENCE:
        if preferred in available:
            return preferred
    return available[0] if available else None


class _ModelGone(BrainError):
    pass


class _ModelBusy(BrainError):
    pass


def describe_429(detail: str, model: str) -> tuple[str, bool]:
    """Turn OpenRouter's 429 error into (message, is_daily_limit)."""
    text = detail.lower()
    if "per-day" in text or "per day" in text or "daily" in text:
        return ("You've used today's free OpenRouter requests. They reset at midnight UTC. "
                "Until then, use the local AI: vector --set provider=ollama", True)
    return (f"The free model '{model}' is busy right now (lots of people share it). "
            "Try again in a minute, or let VECTOR switch models when one is busy: "
            "vector --set model=auto:free", False)


class OpenAICompatBrain(Brain):
    name = "openrouter"

    def __init__(self, model: str = AUTO_FREE, base_url: str = OPENROUTER_URL,
                 api_key: str | None = None, post=None, fetch=None):
        self.auto = model in ("", AUTO_FREE)
        self.model = model or AUTO_FREE
        self._fetch = fetch
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
                raise BrainError("That OpenRouter model isn't free. See the free ones with "
                                 "vector --models") from exc
            if exc.code == 404:
                raise _ModelGone(f"OpenRouter doesn't have the model '{self.model}' (any more). "
                                 "See what's available with: vector --models") from exc
            if exc.code == 429:
                message, daily = describe_429(detail, self.model)
                raise (BrainError if daily else _ModelBusy)(message) from exc
            raise BrainError(f"OpenRouter error {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise BrainError("Couldn't reach OpenRouter. Check your internet connection.") from exc

    def _choose_model(self, avoid: set[str] | None = None) -> None:
        if not self.auto or (self.model != AUTO_FREE and not avoid):
            return
        available = [m for m in list_free_tool_models(self.base_url, self._fetch)
                     if m not in (avoid or set())]
        choice = pick_free_model(available)
        if not choice:
            raise BrainError("No free OpenRouter model with tool support is available right now. "
                             "Try again later, or use the local AI: vector --set provider=ollama")
        self.model = choice

    def respond(self, user_text: str, system: str, tools: list[Tool], execute: ToolExecutor) -> str:
        self._choose_model()
        tried: set[str] = set()
        retried_same = False
        while True:
            try:
                return self._respond(user_text, system, tools, execute)
            except _ModelBusy:
                if not retried_same:          # busy models often free up within seconds
                    retried_same = True
                    time.sleep(2)
                    continue
                if not self.auto or len(tried) >= 3:
                    raise
            except _ModelGone:
                if not self.auto or len(tried) >= 3:
                    raise
            tried.add(self.model)             # auto mode: move on to the next free model
            retried_same = False
            self._choose_model(avoid=tried)

    def _respond(self, user_text: str, system: str, tools: list[Tool], execute: ToolExecutor) -> str:
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
        except BaseException:  # errors, Esc, Ctrl+C: drop the half-finished turn
            del self.messages[checkpoint:]
            raise
