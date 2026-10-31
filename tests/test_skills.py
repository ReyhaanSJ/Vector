from vector.skills import files, productivity
from vector.voice import strip_wake_word


def test_write_read_find_and_organize(tmp_path):
    files.write_text_file(str(tmp_path / "notes" / "todo.txt"), "buy milk")
    assert files.read_text_file(str(tmp_path / "notes" / "todo.txt")) == "buy milk"
    assert "todo.txt" in files.find_files("todo", str(tmp_path))
    assert "todo.txt" in files.list_folder(str(tmp_path / "notes"))

    messy = tmp_path / "messy"
    messy.mkdir()
    for name in ("a.jpg", "b.pdf", "c.mp4", "d.weird"):
        (messy / name).write_text("x")
    (messy / "Images").mkdir()
    (messy / "Images" / "a.jpg").write_text("existing")

    preview = files.organize_folder(str(messy), dry_run=True)
    assert "Would move" in preview and (messy / "a.jpg").exists()

    files.organize_folder(str(messy))
    assert (messy / "Images" / "a (1).jpg").exists()
    assert (messy / "Documents" / "b.pdf").exists()
    assert (messy / "Video" / "c.mp4").exists()
    assert (messy / "Other" / "d.weird").exists()


def test_delete_refuses_personal_roots():
    assert "Refusing" in files.delete_path("downloads") or "does not exist" in files.delete_path("downloads")


def test_resolve_shortcuts():
    from pathlib import Path

    assert files.resolve("downloads/x.zip") == Path.home() / "Downloads" / "x.zip"
    assert files.resolve("~") == Path.home()


def test_memory_roundtrip():
    productivity.remember("My favourite editor is VS Code")
    productivity.remember("I study at night")
    assert "VS Code" in productivity.recall("editor")
    assert "VS Code" in productivity.memory_summary()
    assert productivity.forget("editor").startswith("Forgot 1")
    assert "VS Code" not in productivity.recall()


def test_wake_word():
    assert strip_wake_word("Vector, open Spotify", "vector") == "open Spotify"
    assert strip_wake_word("hey victor what time is it", "vector") == "what time is it"
    assert strip_wake_word("vector", "vector") == ""
    assert strip_wake_word("just talking", "vector") is None
