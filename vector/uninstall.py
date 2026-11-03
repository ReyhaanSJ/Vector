"""Removing VECTOR: type /uninstall in the summon bar, run `vector --uninstall`, or use
Windows Settings > Apps > VECTOR > Uninstall. On a Mac, dragging VECTOR to the Bin leaves its
Python and settings behind, so /uninstall is the clean way.

You choose whether to keep your data (settings, memory) so a later reinstall remembers you.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

DATA_HELP = ("Your data is your settings, VECTOR's memory of you and your saved preferences "
             "(in your .vector folder).")


def uninstaller() -> Path | None:
    """The uninstall script of the installed copy (or of this source tree when developing)."""
    if sys.platform == "darwin":
        from vector.macos import APP_DIR

        candidates = [APP_DIR / "src" / "scripts" / "uninstall-macos.sh",
                      Path(__file__).resolve().parents[1] / "scripts" / "uninstall-macos.sh"]
        return next((p for p in candidates if p.exists()), None)
    candidates = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "VECTOR" / "src" / "scripts"
        / "uninstall-windows.ps1",
        Path(__file__).resolve().parents[1] / "scripts" / "uninstall-windows.ps1",
    ]
    return next((p for p in candidates if p.exists()), None)


def start(keep_data: bool) -> None:
    """Run the uninstaller in its own window. VECTOR should quit right after calling this."""
    if sys.platform not in ("win32", "darwin"):
        raise RuntimeError("Uninstalling from VECTOR is for Windows and macOS. "
                           "Elsewhere: pip uninstall vector-assistant")
    script = uninstaller()
    if script is None:
        where = "Windows Settings > Apps > VECTOR" if sys.platform == "win32" else "vector --uninstall"
        raise RuntimeError(f"Couldn't find VECTOR's uninstaller. Try {where}.")
    env = dict(os.environ, VECTOR_UNINSTALL_YES="1", VECTOR_UNINSTALL_KEEP_DATA="1" if keep_data else "0")
    if sys.platform == "darwin":
        # Copy it out first: the uninstaller deletes the folder it lives in.
        import shutil
        import tempfile

        copy = Path(tempfile.mkdtemp(prefix="vector-uninstall-")) / script.name
        shutil.copy2(script, copy)
        subprocess.Popen(["/bin/bash", str(copy)], env=env, stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
        return
    subprocess.Popen(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)],
                     env=env, creationflags=subprocess.CREATE_NEW_CONSOLE)
