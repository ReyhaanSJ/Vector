"""Working with files and folders."""

from __future__ import annotations

import fnmatch
import os
import shutil
from pathlib import Path

from vector.osutil import open_with_default_app
from vector.registry import tool

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "AppData", "Library", ".cache"}
SHORTCUTS = {
    "home": Path.home(),
    "desktop": Path.home() / "Desktop",
    "documents": Path.home() / "Documents",
    "downloads": Path.home() / "Downloads",
    "pictures": Path.home() / "Pictures",
    "music": Path.home() / "Music",
    "videos": Path.home() / "Videos",
}


def resolve(path: str) -> Path:
    """Expand ~, env vars and shortcuts like "downloads" or "desktop/notes.txt"."""
    raw = os.path.expandvars(path.strip().strip('"'))
    first, _, rest = raw.replace("\\", "/").partition("/")
    if first.lower() in SHORTCUTS:
        base = SHORTCUTS[first.lower()]
        return (base / rest) if rest else base
    return Path(raw).expanduser()


def _size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


@tool
def list_folder(path: str = "home", show_hidden: bool = False) -> str:
    """List what is inside a folder.

    path: Folder path or a shortcut like "downloads", "desktop", "documents".
    show_hidden: Include hidden files.
    """
    folder = resolve(path)
    if not folder.is_dir():
        return f"{folder} is not a folder."
    entries = []
    for item in sorted(folder.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
        if not show_hidden and item.name.startswith("."):
            continue
        try:
            label = "[dir] " if item.is_dir() else f"({_size(item.stat().st_size)}) "
        except OSError:
            label = ""
        entries.append(f"{label}{item.name}")
        if len(entries) >= 200:
            entries.append("... (more not shown)")
            break
    return f"{folder}:\n" + ("\n".join(entries) or "(empty)")


@tool
def find_files(pattern: str, folder: str = "home", max_results: int = 25) -> str:
    """Search for files by name. Supports wildcards like "*.pdf" or "*resume*".

    pattern: File name or wildcard pattern (case-insensitive).
    folder: Where to start searching.
    max_results: Stop after this many matches.
    """
    root = resolve(folder)
    if "*" not in pattern and "?" not in pattern:
        pattern = f"*{pattern}*"
    pattern = pattern.lower()
    matches = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for name in dirnames + filenames:
            if fnmatch.fnmatch(name.lower(), pattern):
                matches.append(str(Path(dirpath) / name))
                if len(matches) >= max_results:
                    return "\n".join(matches) + "\n... (stopped, more may exist)"
    return "\n".join(matches) or f"No matches for '{pattern}' in {root}."


@tool
def open_file(path: str) -> str:
    """Open a file or folder with its default app.

    path: Path to the file or folder.
    """
    target = resolve(path)
    if not target.exists():
        return f"{target} does not exist."
    open_with_default_app(str(target))
    return f"Opened {target}"


@tool
def read_text_file(path: str, max_chars: int = 8000) -> str:
    """Read a text file's contents (code, notes, logs, CSV ...).

    path: Path to the file.
    max_chars: Only return this many characters.
    """
    target = resolve(path)
    if not target.is_file():
        return f"{target} is not a file."
    try:
        text = target.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return f"Couldn't read {target}: {exc}"
    return text[:max_chars] + ("\n... (truncated)" if len(text) > max_chars else "")


@tool(dangerous=True)
def write_text_file(path: str, content: str, append: bool = False) -> str:
    """Create or overwrite a text file (or append to it).

    path: Where to save the file.
    content: The text to write.
    append: Add to the end instead of replacing.
    """
    target = resolve(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a" if append else "w", encoding="utf-8") as fh:
        fh.write(content)
    return f"{'Appended to' if append else 'Saved'} {target}"


@tool
def create_folder(path: str) -> str:
    """Create a new folder (and any missing parent folders).

    path: The folder to create.
    """
    target = resolve(path)
    target.mkdir(parents=True, exist_ok=True)
    return f"Folder ready: {target}"


@tool(dangerous=True)
def move_or_rename(source: str, destination: str) -> str:
    """Move or rename a file or folder.

    source: What to move.
    destination: New path (or a folder to move it into).
    """
    src, dst = resolve(source), resolve(destination)
    if not src.exists():
        return f"{src} does not exist."
    final = shutil.move(str(src), str(dst))
    return f"Moved {src} -> {final}"


@tool(dangerous=True)
def delete_path(path: str) -> str:
    """Delete a file or folder permanently. Only use when the user clearly asks.

    path: What to delete.
    """
    target = resolve(path)
    if not target.exists():
        return f"{target} does not exist."
    if target in SHORTCUTS.values() or target == Path(target.anchor):
        return "Refusing to delete a top-level personal folder or drive."
    if target.is_dir():
        shutil.rmtree(target)
    else:
        target.unlink()
    return f"Deleted {target}"


CATEGORIES = {
    "Images": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".svg", ".bmp"},
    "Documents": {".pdf", ".doc", ".docx", ".txt", ".md", ".rtf", ".odt", ".pages"},
    "Spreadsheets": {".xls", ".xlsx", ".csv", ".ods", ".numbers"},
    "Slides": {".ppt", ".pptx", ".key", ".odp"},
    "Archives": {".zip", ".rar", ".7z", ".tar", ".gz"},
    "Audio": {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg"},
    "Video": {".mp4", ".mov", ".mkv", ".avi", ".webm"},
    "Installers": {".exe", ".msi", ".dmg", ".pkg", ".deb", ".rpm", ".appimage"},
    "Code": {".py", ".js", ".ts", ".html", ".css", ".json", ".java", ".c", ".cpp", ".ipynb"},
}


@tool(dangerous=True)
def organize_folder(path: str = "downloads", dry_run: bool = False) -> str:
    """Tidy a messy folder by sorting its files into subfolders (Images, Documents, Video ...).

    path: The folder to organize.
    dry_run: Only describe what would happen without moving anything.
    """
    folder = resolve(path)
    if not folder.is_dir():
        return f"{folder} is not a folder."
    moves: dict[str, int] = {}
    for item in folder.iterdir():
        if not item.is_file() or item.name.startswith("."):
            continue
        category = next((c for c, exts in CATEGORIES.items() if item.suffix.lower() in exts), "Other")
        moves[category] = moves.get(category, 0) + 1
        if not dry_run:
            dest = folder / category
            dest.mkdir(exist_ok=True)
            target = dest / item.name
            n = 1
            while target.exists():
                target = dest / f"{item.stem} ({n}){item.suffix}"
                n += 1
            shutil.move(str(item), str(target))
    if not moves:
        return f"Nothing to organize in {folder}."
    summary = ", ".join(f"{count} -> {cat}" for cat, count in sorted(moves.items()))
    return f"{'Would move' if dry_run else 'Moved'} files in {folder}: {summary}"
