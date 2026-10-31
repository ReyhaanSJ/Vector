from vector.config import load_config, write_default_config


def test_defaults_file_and_env(tmp_path, monkeypatch):
    path = tmp_path / "c.toml"
    write_default_config(path)
    cfg = load_config(path)
    assert cfg.provider == "anthropic" and cfg.resolved_model == "claude-opus-5-5"
    path.write_text('provider = "ollama"\nuser_name = "Ray"\n')
    monkeypatch.setenv("VECTOR_CONFIRM_DANGEROUS", "false")
    cfg = load_config(path)
    assert cfg.user_name == "Ray" and cfg.resolved_model == "llama3.1"
    assert cfg.confirm_dangerous is False
