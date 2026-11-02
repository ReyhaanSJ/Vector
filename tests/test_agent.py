from types import SimpleNamespace as NS

import pytest

from vector.agent import Vector
from vector.brain import BrainError
from vector.brain.claude import ClaudeBrain
from vector.brain.ollama import OllamaBrain
from vector.config import Config
from vector.registry import Registry, build_tool

calls = []


def greet(name: str) -> str:
    """Greet someone.

    name: Who.
    """
    calls.append(name)
    return f"Hello {name}"


def wipe(path: str) -> str:
    """Pretend to delete something."""
    calls.append(("wipe", path))
    return "wiped"


def make_registry():
    reg = Registry()
    reg.register(build_tool(greet))
    reg.register(build_tool(wipe, dangerous=True))
    return reg


class FakeClaude:
    """Mimics client.beta.messages.create with scripted responses."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []
        self.beta = NS(messages=NS(create=self._create))

    def _create(self, **params):
        self.requests.append({**params, "messages": list(params["messages"])})
        return self.responses.pop(0)


def text(t):
    return NS(type="text", text=t)


def tool_use(id_, name, input_):
    return NS(type="tool_use", id=id_, name=name, input=input_)


def make_vector(brain, confirm=None):
    calls.clear()
    return Vector(Config(user_name="Tester"), brain, confirm=confirm, registry=make_registry())


def test_claude_tool_loop():
    fake = FakeClaude([
        NS(stop_reason="tool_use", content=[text("On it."), tool_use("t1", "greet", {"name": "Ada"})]),
        NS(stop_reason="end_turn", content=[text("Said hello to Ada.")]),
    ])
    v = make_vector(ClaudeBrain(client=fake))
    assert v.ask("say hi to Ada") == "Said hello to Ada."
    assert calls == ["Ada"]

    first, second = fake.requests
    assert first["model"] == "claude-opus-5-5"
    assert first["fallbacks"] == "default" and first["betas"] == ["server-side-fallback-2026-07-01"]
    assert first["output_config"] == {"effort": "low"}
    assert {t["name"] for t in first["tools"]} == {"greet", "wipe"}
    assert "VECTOR" in first["system"] and "Tester" in first["system"]
    result = second["messages"][-1]["content"][0]
    assert result["tool_use_id"] == "t1" and result["content"] == "Hello Ada"
    assert result["is_error"] is False


def test_dangerous_tool_needs_confirmation():
    def run(confirm):
        fake = FakeClaude([
            NS(stop_reason="tool_use", content=[tool_use("t1", "wipe", {"path": "/tmp/x"})]),
            NS(stop_reason="end_turn", content=[text("ok")]),
        ])
        v = make_vector(ClaudeBrain(client=fake), confirm=confirm)
        v.ask("wipe it")
        return fake.requests[1]["messages"][-1]["content"][0]

    denied = run(lambda n, a: False)
    assert denied["is_error"] and "declined" in denied["content"] and calls == []
    allowed = run(lambda n, a: True)
    assert allowed["content"] == "wiped" and calls == [("wipe", "/tmp/x")]


def test_unknown_tool_and_bad_args_are_errors_not_crashes():
    v = make_vector(ClaudeBrain(client=FakeClaude([])))
    assert v.execute("nope", {}) == ("Unknown tool 'nope'.", True)
    out, err = v.execute("greet", {"wrong": 1})
    assert err and "Bad arguments" in out


def test_refusal_rolls_back_history():
    fake = FakeClaude([NS(stop_reason="refusal", content=[])])
    brain = ClaudeBrain(client=fake)
    v = make_vector(brain)
    with pytest.raises(BrainError):
        v.ask("something")
    assert brain.messages == []


def test_ollama_tool_loop():
    replies = [
        {"message": {"content": "", "tool_calls": [{"function": {"name": "greet", "arguments": {"name": "Bo"}}}]}},
        {"message": {"content": "Greeted Bo."}},
    ]
    sent = []

    def post(payload):
        sent.append(payload)
        return replies.pop(0)

    v = make_vector(OllamaBrain(post=post))
    assert v.ask("greet Bo") == "Greeted Bo."
    assert calls == ["Bo"]
    assert sent[0]["messages"][0]["role"] == "system"
    assert sent[1]["messages"][-1] == {"role": "tool", "content": "Hello Bo", "tool_name": "greet"}
    assert sent[0]["tools"][0]["type"] == "function"


def test_openrouter_tool_loop():
    from vector.brain.openai_compat import OpenAICompatBrain

    replies = [
        {"choices": [{"message": {"content": None, "tool_calls": [
            {"id": "c1", "type": "function", "function": {"name": "greet", "arguments": '{"name": "Cy"}'}}]}}]},
        {"choices": [{"message": {"content": "Greeted Cy."}}]},
    ]
    sent = []

    def post(payload):
        sent.append(payload)
        return replies.pop(0)

    v = make_vector(OpenAICompatBrain("google/gemma-4-31b-it:free", api_key="k", post=post))
    assert v.ask("greet Cy") == "Greeted Cy."
    assert calls == ["Cy"]
    assert sent[0]["model"] == "google/gemma-4-31b-it:free" and sent[0]["tool_choice"] == "auto"
    assert sent[1]["messages"][-1] == {"role": "tool", "tool_call_id": "c1", "content": "Hello Cy"}


def test_openrouter_needs_key():
    from vector.brain.openai_compat import OpenAICompatBrain

    brain = OpenAICompatBrain("m:free", api_key="")
    v = make_vector(brain)
    with pytest.raises(BrainError, match="openrouter.ai/keys"):
        v.ask("hi")
    assert brain.messages == []


def test_openrouter_auto_picks_and_recovers():
    from vector.brain.openai_compat import OpenAICompatBrain, list_free_tool_models, pick_free_model

    catalog = {"data": [
        {"id": "a/no-tools:free", "supported_parameters": []},
        {"id": "a/paid", "supported_parameters": ["tools"]},
        {"id": "google/gemma-4-31b-it:free", "supported_parameters": ["tools"]},
        {"id": "x/other:free", "supported_parameters": ["tools", "temperature"]},
    ]}
    fetch = lambda url: catalog  # noqa: E731
    assert list_free_tool_models(fetch=fetch) == ["google/gemma-4-31b-it:free", "x/other:free"]
    assert pick_free_model(["x/other:free"]) == "x/other:free"
    assert pick_free_model([]) is None

    import io
    import urllib.error

    sent = []

    def post(payload):
        sent.append(payload["model"])
        if payload["model"] == "google/gemma-4-31b-it:free":
            raise urllib.error.HTTPError("u", 404, "gone", {}, io.BytesIO(b""))
        return {"choices": [{"message": {"content": "hi from other"}}]}

    brain = OpenAICompatBrain(api_key="k", fetch=fetch)
    brain._post = lambda p: brain_post(p)

    def brain_post(p):  # route through the real error handling
        try:
            return post(p)
        except urllib.error.HTTPError as exc:
            from vector.brain.openai_compat import _ModelGone
            raise _ModelGone("gone") from exc

    v = make_vector(brain)
    assert v.ask("hello") == "hi from other"
    assert sent == ["google/gemma-4-31b-it:free", "x/other:free"]
    assert brain.model == "x/other:free"


def test_openrouter_fixed_model_is_not_switched():
    from vector.brain.openai_compat import OpenAICompatBrain, _ModelGone

    def post(payload):
        raise _ModelGone("OpenRouter doesn't have the model")

    v = make_vector(OpenAICompatBrain("me/my-model:free", api_key="k", post=post))
    with pytest.raises(BrainError, match="doesn't have"):
        v.ask("hi")
