import pytest


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    """Keep tests away from the real ~/.vector folder."""
    from vector.skills import productivity

    monkeypatch.setattr(productivity, "MEMORY_FILE", tmp_path / "vector-home" / "memory.json")
    monkeypatch.setenv("VECTOR_CONFIG", str(tmp_path / "vector-home" / "config.toml"))
    monkeypatch.setenv("VECTOR_NO_KEYCHAIN", "1")  # never read the real Mac Keychain in tests
    return tmp_path
