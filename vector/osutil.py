"""Small cross-platform helpers (Windows, macOS, Linux)."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

SYSTEM = platform.system()  # "Windows", "Darwin" or "Linux"
IS_WINDOWS = SYSTEM == "Windows"
IS_MAC = SYSTEM == "Darwin"
IS_LINUX = SYSTEM == "Linux"


def _no_window() -> dict:
    # Stops a black console window flashing up every time VECTOR runs a helper on Windows.
    return {"creationflags": subprocess.CREATE_NO_WINDOW} if IS_WINDOWS else {}


def run(cmd: list[str] | str, shell: bool = False, timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, shell=shell, capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=timeout, check=False, **_no_window(),
    )


def powershell(script: str, timeout: int = 30) -> subprocess.CompletedProcess:
    """Run a Windows PowerShell script, with UTF-8 output so non-English text survives."""
    prefix = "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
    return run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
         "-Command", prefix + script],
        timeout=timeout,
    )


def ps_quote(text: str) -> str:
    """Quote a string as a PowerShell single-quoted literal."""
    return "'" + text.replace("'", "''") + "'"


# Windows registry names for the user's personal folders (they can be moved, e.g. by OneDrive).
_WINDOWS_FOLDER_KEYS = {
    "desktop": "Desktop",
    "documents": "Personal",
    "downloads": "{374DE290-123F-4565-9164-39C4925E467B}",
    "pictures": "My Pictures",
    "music": "My Music",
    "videos": "My Video",
}


def personal_folders() -> dict[str, Path]:
    """Desktop, Documents, Downloads ... where they really are on this machine."""
    home = Path.home()
    folders = {
        "home": home,
        "desktop": home / "Desktop",
        "documents": home / "Documents",
        "downloads": home / "Downloads",
        "pictures": home / "Pictures",
        "music": home / "Music",
        "videos": home / ("Movies" if IS_MAC else "Videos"),
    }
    if IS_WINDOWS:
        try:
            import winreg

            key_path = r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                for name, value_name in _WINDOWS_FOLDER_KEYS.items():
                    try:
                        value, _ = winreg.QueryValueEx(key, value_name)
                        folders[name] = Path(os.path.expandvars(value))
                    except OSError:
                        pass
        except OSError:
            pass
    return folders


def spawn(cmd: list[str] | str, shell: bool = False) -> None:
    """Start a program without waiting for it."""
    kwargs = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if IS_WINDOWS:
        kwargs["creationflags"] = (
            subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
            | subprocess.CREATE_NO_WINDOW
        )
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
            toast = (
                "$ErrorActionPreference = 'Stop';"
                "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications,"
                " ContentType = WindowsRuntime] > $null;"
                "$t = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent("
                "[Windows.UI.Notifications.ToastTemplateType]::ToastText02);"
                "$x = $t.GetElementsByTagName('text');"
                f"$x.Item(0).AppendChild($t.CreateTextNode({_ps(title)})) > $null;"
                f"$x.Item(1).AppendChild($t.CreateTextNode({_ps(message)})) > $null;"
                "$n = [Windows.UI.Notifications.ToastNotification]::new($t);"
                "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("
                "'{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\\WindowsPowerShell\\v1.0\\powershell.exe'"
                ").Show($n)"
            )
            if powershell(toast).returncode == 0:
                return True
            ps = (
                "[reflection.assembly]::loadwithpartialname('System.Windows.Forms') | Out-Null;"
                "$n = New-Object System.Windows.Forms.NotifyIcon;"
                "$n.Icon = [System.Drawing.SystemIcons]::Information; $n.Visible = $true;"
                f"$n.ShowBalloonTip(5000, {_ps(title)}, {_ps(message)}, 'Info');"
                "Start-Sleep -Seconds 6; $n.Dispose()"
            )
            spawn(["powershell.exe", "-NoProfile", "-Command", ps])
            return True
    except Exception:
        pass
    print(f"\a[{title}] {message}", file=sys.stderr)
    return False


def _osa(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


_ps = ps_quote
