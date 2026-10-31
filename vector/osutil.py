"""Small cross-platform helpers (Windows, macOS, Linux)."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys

SYSTEM = platform.system()  # "Windows", "Darwin" or "Linux"
IS_WINDOWS = SYSTEM == "Windows"
IS_MAC = SYSTEM == "Darwin"
IS_LINUX = SYSTEM == "Linux"


def run(cmd: list[str] | str, shell: bool = False, timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, shell=shell, capture_output=True, text=True, timeout=timeout, check=False
    )


def spawn(cmd: list[str] | str, shell: bool = False) -> None:
    """Start a program without waiting for it."""
    kwargs = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if IS_WINDOWS:
        kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen(cmd, shell=shell, **kwargs)


def open_with_default_app(target: str) -> None:
    """Open a file, folder or URL with whatever the OS normally uses."""
    if IS_WINDOWS:
        os.startfile(target)  # type: ignore[attr-defined]
    elif IS_MAC:
        spawn(["open", target])
    else:
        spawn(["xdg-open", target])


def notify(title: str, message: str) -> bool:
    """Show a desktop notification. Returns False if nothing could show it."""
    try:
        if IS_MAC:
            script = f'display notification {_osa(message)} with title {_osa(title)}'
            run(["osascript", "-e", script])
            return True
        if IS_LINUX and shutil.which("notify-send"):
            run(["notify-send", title, message])
            return True
        if IS_WINDOWS:
            ps = (
                "[reflection.assembly]::loadwithpartialname('System.Windows.Forms') | Out-Null;"
                "$n = New-Object System.Windows.Forms.NotifyIcon;"
                "$n.Icon = [System.Drawing.SystemIcons]::Information; $n.Visible = $true;"
                f"$n.ShowBalloonTip(5000, {_ps(title)}, {_ps(message)}, 'Info');"
                "Start-Sleep -Seconds 6; $n.Dispose()"
            )
            spawn(["powershell", "-NoProfile", "-Command", ps])
            return True
    except Exception:
        pass
    print(f"\a[{title}] {message}", file=sys.stderr)
    return False


def _osa(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _ps(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"
