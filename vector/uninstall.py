"""Removing VECTOR: type /uninstall in the summon bar, run `vector --uninstall`, or use
Windows Settings > Apps > VECTOR > Uninstall.

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
    candidates = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "VECTOR" / "src" / "scripts"
        / "uninstall-windows.ps1",
        Path(__file__).resolve().parents[1] / "scripts" / "uninstall-windows.ps1",
    ]
    return next((p for p in candidates if p.exists()), None)


def start(keep_data: bool) -> None:
    """Run the uninstaller in its own window. VECTOR should quit right after calling this."""
    if sys.platform != "win32":
        raise RuntimeError("Uninstalling from VECTOR is Windows-only. Elsewhere: pip uninstall vector-assistant")
    script = uninstaller()
    if script is None:
        raise RuntimeError("Couldn't find VECTOR's uninstaller. Use Windows Settings > Apps > VECTOR.")
    env = dict(os.environ, VECTOR_UNINSTALL_YES="1", VECTOR_UNINSTALL_KEEP_DATA="1" if keep_data else "0")
    subprocess.Popen(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)],
                     env=env, creationflags=subprocess.CREATE_NEW_CONSOLE)
