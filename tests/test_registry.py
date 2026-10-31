from typing import Literal

from vector.registry import REGISTRY, Registry, build_tool, load_builtin_skills, load_skill_dir


def sample(path: str, count: int = 3, mode: Literal["a", "b"] = "a", tags: list[str] | None = None):
    """Do a sample thing.

    Example: this line is part of the summary, not a parameter.

    path: Where to look.
    count: How many.
    """


def test_schema_from_signature_and_docstring():
    t = build_tool(sample)
    assert t.description.startswith("Do a sample thing.")
    props = t.parameters["properties"]
    assert props["path"] == {"type": "string", "description": "Where to look."}
    assert props["count"]["type"] == "integer" and props["count"]["default"] == 3
    assert props["mode"]["enum"] == ["a", "b"]
    assert props["tags"]["type"] == "array"
    assert t.parameters["required"] == ["path"]
    assert set(t.schema()) == {"name", "description", "input_schema"}


def test_builtin_skills_load_and_risky_ones_are_flagged():
    load_builtin_skills()
    assert len(REGISTRY) >= 25
    for name in ("run_shell_command", "delete_path", "move_or_rename", "write_text_file", "type_text"):
        assert REGISTRY.get(name).dangerous, name
    assert not REGISTRY.get("open_app").dangerous


def test_user_skill_dir(tmp_path):
    (tmp_path / "hello.py").write_text(
        "from vector import tool\n\n@tool\ndef say_hi_test(name: str) -> str:\n"
        '    """Say hi."""\n    return "hi " + name\n'
    )
    (tmp_path / "broken.py").write_text("raise RuntimeError('boom')\n")
    loaded = load_skill_dir(tmp_path)
    assert loaded == ["hello.py"]
    assert REGISTRY.get("say_hi_test")(name="Ada") == "hi Ada"


def test_registry_isolated():
    reg = Registry()
    reg.register(build_tool(sample))
    assert "sample" in reg and len(reg) == 1
