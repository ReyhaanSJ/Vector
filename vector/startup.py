"""Start VECTOR automatically when you log in (Windows)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from vector.osutil import IS_WINDOWS

SCRIPT_NAME = "VECTOR.bat"


def startup_folder() -> Path:
    appdata = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
    return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def enable(voice: bool = True, folder: Path | None = None) -> Path:
    """Write a small launcher into the Startup folder. Returns its path."""
    folder = folder or startup_folder()
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / SCRIPT_NAME
    mode = " --voice" if voice else ""
    path.write_text(
        "@echo off\r\n"
        "rem Started by VECTOR. Remove with: vector --startup off\r\n"
        f'start "VECTOR" "{sys.executable}" -m vector{mode}\r\n',
        encoding="utf-8",
    )
    return path


def disable(folder: Path | None = None) -> bool:
    path = (folder or startup_folder()) / SCRIPT_NAME
    if path.exists():
        path.unlink()
        return True
    return False


def supported() -> bool:
    return IS_WINDOWS
