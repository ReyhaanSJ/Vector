from vector.config import load_config, write_default_config


def test_defaults_file_and_env(tmp_path, monkeypatch):
    path = tmp_path / "c.toml"
    write_default_config(path)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    cfg = load_config(path)
    assert cfg.provider == "auto" and cfg.resolved_provider == "ollama"
    assert cfg.resolved_model == "llama3.2"
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-test")
    assert cfg.resolved_provider == "openrouter" and cfg.resolved_model == "auto:free"
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    assert cfg.resolved_provider == "anthropic" and cfg.resolved_model == "claude-opus-5-5"
    path.write_text('provider = "ollama"\nuser_name = "Ray"\n')
    monkeypatch.setenv("VECTOR_CONFIRM_DANGEROUS", "false")
    cfg = load_config(path)
    assert cfg.user_name == "Ray" and cfg.resolved_model == "llama3.2"
    assert cfg.confirm_dangerous is False


def test_set_config_value_keeps_comments(tmp_path):
    import pytest

    from vector.config import set_config_value

    path = tmp_path / "c.toml"
    set_config_value("model", "qwen2.5:7b", path)
    set_config_value("provider", "ollama", path)
    set_config_value("confirm_dangerous", "no", path)
    set_config_value("skill_dirs", "", path)
    text = path.read_text()
    assert "# VECTOR configuration" in text
    cfg = load_config(path)
    assert (cfg.model, cfg.provider, cfg.confirm_dangerous) == ("qwen2.5:7b", "ollama", False)
    with pytest.raises(KeyError):
        set_config_value("nope", "1", path)


def test_claude_model_names_mean_claude(monkeypatch):
    from vector.config import Config

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    cfg = Config(provider="openrouter", model="claude-haiku-5-5")
    assert cfg.resolved_provider == "anthropic"
    assert Config(provider="openrouter", model="google/gemma-4-31b-it:free").resolved_provider == "openrouter"


def test_describe_model():
    from vector.config import describe_model

    assert describe_model("anthropic", "claude-haiku-5-5") == "Claude Haiku 5.5"
    assert describe_model("anthropic", "claude-opus-5-5") == "Claude Opus 5.5"
    assert describe_model("openrouter", "auto:free") == "Free cloud AI (auto)"
    assert describe_model("openrouter", "google/gemma-4-31b-it:free") == "gemma-4-31b-it (free cloud)"
    assert describe_model("ollama", "qwen2.5:7b") == "qwen2.5:7b (local)"


def test_pasted_keys_are_cleaned_and_checked():
    from vector import keys

    assert keys.clean('  "sk-or-v1-abc"\n') == "sk-or-v1-abc"
    assert keys.wrong_kind("openrouter", "sk-or-v1-abc") is None
    assert "Claude" in keys.wrong_kind("openrouter", "sk-ant-api03-xyz")
    assert "OpenRouter" in keys.wrong_kind("claude", "sk-or-v1-abc")
    assert "start with sk-or-" in keys.wrong_kind("openrouter", "hello")


def test_openrouter_401_says_how_to_fix_it():
    import io
    import urllib.error

    from vector.brain import BrainError
    from vector.brain.openai_compat import OpenAICompatBrain

    brain = OpenAICompatBrain(model="x:free", api_key=' "sk-ant-oops" ')
    assert brain.api_key == "sk-ant-oops"

    def refuse(*a, **k):
        raise urllib.error.HTTPError("u", 401, "no", {}, io.BytesIO(b"{}"))

    import urllib.request

    original = urllib.request.urlopen
    urllib.request.urlopen = refuse
    try:
        try:
            brain._http_post({})
        except BrainError as exc:
            message = str(exc)
    finally:
        urllib.request.urlopen = original
    assert "Claude (Anthropic) key" in message and "vector --set-key openrouter" in message
