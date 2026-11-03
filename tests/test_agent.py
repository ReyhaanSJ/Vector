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
    assert first["fallbacks"] == "default" and "server-side-fallback-2026-07-01" in first["betas"]
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


def test_openrouter_auto_picks_and_recovers(monkeypatch):
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
    import vector.brain.openai_compat as oc
    monkeypatch.setattr(oc.time, "sleep", lambda s: None)

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


def test_openrouter_busy_model_retries_then_switches(monkeypatch):
    import vector.brain.openai_compat as oc
    from vector.brain.openai_compat import OpenAICompatBrain, _ModelBusy

    monkeypatch.setattr(oc.time, "sleep", lambda s: None)
    catalog = {"data": [{"id": m, "supported_parameters": ["tools"]}
                        for m in ("google/gemma-4-31b-it:free", "x/other:free")]}
    sent = []

    def post(payload):
        sent.append(payload["model"])
        if payload["model"] == "google/gemma-4-31b-it:free":
            raise _ModelBusy("busy")
        return {"choices": [{"message": {"content": "ok"}}]}

    v = make_vector(OpenAICompatBrain(api_key="k", post=post, fetch=lambda u: catalog))
    assert v.ask("hi") == "ok"
    assert sent == ["google/gemma-4-31b-it:free", "google/gemma-4-31b-it:free", "x/other:free"]


def test_openrouter_429_messages():
    from vector.brain.openai_compat import describe_429

    msg, daily = describe_429('{"error":{"message":"Rate limit exceeded: free-models-per-day"}}', "m")
    assert daily and "midnight UTC" in msg
    msg, daily = describe_429('{"error":{"message":"m is temporarily rate-limited upstream"}}', "m")
    assert not daily and "busy" in msg


def test_stop_during_approval_cancels_and_rolls_back():
    from vector.brain import Cancelled

    fake = FakeClaude([
        NS(stop_reason="tool_use", content=[tool_use("t1", "wipe", {"path": "/x"})]),
        NS(stop_reason="end_turn", content=[text("should never be reached")]),
    ])
    brain = ClaudeBrain(client=fake)
    v = make_vector(brain)

    def press_esc(name, args):
        v.cancel()
        return False

    v.confirm = press_esc
    with pytest.raises(Cancelled):
        v.ask("wipe it")
    assert calls == [] and len(fake.requests) == 1
    assert brain.messages == []          # history stays valid for the next request
    fake.responses = [NS(stop_reason="end_turn", content=[text("fresh start")])]
    assert v.ask("hello") == "fresh start"  # cancel flag clears for the next request


def test_stop_while_ai_is_answering_drops_the_reply():
    from vector.brain import Cancelled

    v = make_vector(ClaudeBrain(client=FakeClaude([])))

    class SlowBrain:
        model = "x"

        def respond(self, text, system, tools, execute):
            v.cancel()                   # Esc pressed while the AI was still thinking
            return "late reply"

        def reset(self):
            pass

    v.brain = SlowBrain()
    with pytest.raises(Cancelled):
        v.ask("hi")


def test_ctrl_c_mid_request_keeps_history_valid():
    fake = FakeClaude([NS(stop_reason="tool_use", content=[tool_use("t1", "greet", {"name": "A"})])])
    brain = ClaudeBrain(client=fake)
    v = make_vector(brain)

    def interrupted(name, args):
        raise KeyboardInterrupt

    v.execute = interrupted
    with pytest.raises(KeyboardInterrupt):
        brain.respond("hi", "sys", [], v.execute)
    assert brain.messages == []


def _screen_registry():
    from vector.registry import ToolOutput

    def look_at_screen():
        """Look."""
        calls.append("look")
        return ToolOutput("Screenshot 10x10", [("image/jpeg", b"\xff\xd8jpeg")])

    def click(x: int, y: int):
        """Click."""
        calls.append(("click", x, y))
        return "clicked"

    reg = make_registry()
    reg.register(build_tool(look_at_screen, screen=True))
    reg.register(build_tool(click, screen=True))
    return reg


def test_screen_ok_is_asked_once_per_request_and_images_reach_claude():
    asked = []
    fake = FakeClaude([
        NS(stop_reason="tool_use", content=[tool_use("a", "look_at_screen", {}),
                                            tool_use("b", "click", {"x": 1, "y": 2})]),
        NS(stop_reason="end_turn", content=[text("done")]),
        NS(stop_reason="tool_use", content=[tool_use("c", "look_at_screen", {})]),
        NS(stop_reason="end_turn", content=[text("done again")]),
    ])
    calls.clear()
    v = Vector(Config(), ClaudeBrain(client=fake), registry=_screen_registry(),
               confirm=lambda n, a: asked.append(n) or True)
    assert v.ask("click the button") == "done"
    assert asked == ["use_your_screen"]                       # once for both screen actions
    results = fake.requests[1]["messages"][-1]["content"]
    image, words = results[0]["content"]
    assert image["type"] == "image" and image["source"]["media_type"] == "image/jpeg"
    assert words == {"type": "text", "text": "Screenshot 10x10"}
    assert v.ask("look again") == "done again"
    assert asked == ["use_your_screen", "use_your_screen"]   # a new request asks again


def test_screen_access_never_and_always():
    calls.clear()
    reg = _screen_registry()
    never = Vector(Config(screen_access="never"), ClaudeBrain(client=FakeClaude([])), registry=reg,
                   confirm=lambda n, a: True)
    out, err = never.execute("look_at_screen", {})
    assert err and "turned off" in out and calls == []
    always = Vector(Config(screen_access="always"), ClaudeBrain(client=FakeClaude([])), registry=reg,
                    confirm=lambda n, a: pytest.fail("should not ask"))
    out, err = always.execute("click", {"x": 3, "y": 4})
    assert not err and calls == [("click", 3, 4)]


def test_screenshots_reach_openrouter_and_ollama():
    from vector.brain.openai_compat import OpenAICompatBrain

    calls.clear()
    sent = []
    replies = [
        {"choices": [{"message": {"content": "", "tool_calls": [
            {"id": "c1", "function": {"name": "look_at_screen", "arguments": "{}"}}]}}]},
        {"choices": [{"message": {"content": "I can see it"}}]},
    ]

    def post(payload):
        sent.append(payload)
        return replies.pop(0)

    v = Vector(Config(screen_access="always"), OpenAICompatBrain("m:free", api_key="k", post=post),
               registry=_screen_registry())
    assert v.ask("what's on screen") == "I can see it"
    tool_msg, picture_msg = sent[1]["messages"][-2:]
    assert tool_msg["role"] == "tool" and "picture follows" in tool_msg["content"]
    assert picture_msg["content"][1]["image_url"]["url"].startswith("data:image/jpeg;base64,")

    ollama_sent = []
    o_replies = [
        {"message": {"content": "", "tool_calls": [{"function": {"name": "look_at_screen", "arguments": {}}}]}},
        {"message": {"content": "ok"}},
    ]

    def o_post(payload):
        ollama_sent.append(payload)
        return o_replies.pop(0)

    text_only = Vector(Config(screen_access="always"), OllamaBrain(model="llama3.2", post=o_post),
                       registry=_screen_registry())
    text_only.ask("look")
    msg = ollama_sent[1]["messages"][-1]
    assert "can't see pictures" in msg["content"] and "images" not in msg


def test_system_prompt_stays_the_same_for_a_whole_chat(monkeypatch):
    """Claude ties its thinking to the system prompt; changing it mid-chat gets a 400."""
    import datetime as dt

    from vector import agent as agent_module
    from vector.skills import productivity

    fake = FakeClaude([NS(stop_reason="end_turn", content=[text("one")]),
                       NS(stop_reason="end_turn", content=[text("two")])])
    v = make_vector(ClaudeBrain(client=fake))
    clock = [dt.datetime(2026, 11, 3, 9, 59)]

    class Clock(dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return clock[0]

    monkeypatch.setattr(agent_module.dt, "datetime", Clock)
    v.ask("hi")
    productivity.remember("favourite editor is VS Code")   # memory changes mid-chat
    clock[0] = dt.datetime(2026, 11, 3, 10, 5)             # and the hour changes
    v.ask("again")
    first, second = fake.requests
    assert first["system"] == second["system"]
    assert "9:59 AM" in first["messages"][0]["content"]
    assert second["messages"][-1]["content"].startswith("[Context: it is Tuesday 3 November 2026, 10:05 AM")
    assert "VS Code" in second["messages"][-1]["content"]


def test_old_thinking_is_dropped_not_fatal():
    import anthropic
    import httpx2

    brain = ClaudeBrain(model="claude-opus-5-5", client=FakeClaude([]))
    params = brain._request("sys", [])
    assert params["thinking"]["block_binding"] == {"prefix_mismatch_behavior": "drop_block"}
    assert "thinking-binding-controls-2026-08-01" in params["betas"]
    old = ClaudeBrain(model="claude-haiku-4-5", client=FakeClaude([]))._request("sys", [])
    assert "thinking" not in old  # older models don't take adaptive thinking

    # If Claude still rejects old thinking, VECTOR forgets that thinking and tries once more.
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    error = anthropic.BadRequestError(
        "messages.1.content.0: Invalid `signature` in `thinking` block. The block is bound to a "
        "different conversation.", response=httpx2.Response(400, request=request), body=None)
    fake = FakeClaude([NS(stop_reason="end_turn", content=[text("fine")])])
    seen = []

    def create(**params):
        seen.append([m["content"] for m in params["messages"]])
        if len(seen) == 1:
            raise error
        return fake.responses.pop(0)

    fake.beta.messages.create = create
    brain = ClaudeBrain(client=fake)
    brain.messages = [{"role": "user", "content": "hi"},
                      {"role": "assistant", "content": [NS(type="thinking", thinking=""),
                                                        text("hello")]}]
    assert brain.respond("more", "sys", [], lambda n, a: ("", False)) == "fine"
    assert [b.type for b in seen[1][1]] == ["text"]
