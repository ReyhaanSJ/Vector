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
