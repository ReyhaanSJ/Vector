"""Start VECTOR automatically when you log in (Windows: a Startup shortcut, macOS: a LaunchAgent)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from vector.osutil import IS_MAC, IS_WINDOWS

SCRIPT_NAME = "VECTOR.bat"


def startup_folder() -> Path:
    appdata = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
    return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


SHORTCUT_NAME = "VECTOR.lnk"
ICON = Path(__file__).parent / "assets" / "icon.ico"


def app_launcher() -> tuple[str, str]:
    """(program, arguments) that start the background app without a console window."""
    scripts = Path(sys.executable).parent
    exe = scripts / ("vector-app.exe" if IS_WINDOWS else "vector-app")
    if exe.exists():
        return str(exe), "--background"
    pythonw = scripts / "pythonw.exe"
    return str(pythonw if pythonw.exists() else sys.executable), "-m vector.app --background"


MAC_LABEL = "com.vector.assistant"


def launch_agents() -> Path:
    return Path.home() / "Library" / "LaunchAgents"


def mac_plist(app_bundle: Path | None = None) -> str:
    """The LaunchAgent that opens VECTOR (in the background) when you log in."""
    from xml.sax.saxutils import escape

    from vector.macos import APP_BUNDLE

    bundle = app_bundle or APP_BUNDLE
    if bundle.exists():  # the installed app: open it the normal way, so macOS knows it's VECTOR
        args = ["/usr/bin/open", "-g", "-a", str(bundle), "--args", "--background"]
    else:
        target, arguments = app_launcher()
        args = [target, *arguments.split()]
    items = "\n".join(f"    <string>{escape(a)}</string>" for a in args)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>{MAC_LABEL}</string>
  <key>ProgramArguments</key>
  <array>
{items}
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>ProcessType</key>
  <string>Interactive</string>
</dict>
</plist>
"""


def enable(app: bool = True, folder: Path | None = None) -> Path:
    """Start VECTOR at login. app=True: the background app (tray, shortcut, voice);
    app=False: the terminal version. Returns the file created."""
    if IS_MAC:
        folder = folder or launch_agents()
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{MAC_LABEL}.plist"
        path.write_text(mac_plist(), encoding="utf-8")
        return path
    folder = folder or startup_folder()
    folder.mkdir(parents=True, exist_ok=True)
    disable(folder)
    if app and IS_WINDOWS:
        from vector.osutil import powershell, ps_quote

        target, arguments = app_launcher()
        path = folder / SHORTCUT_NAME
        result = powershell(
            "$s = (New-Object -ComObject WScript.Shell).CreateShortcut(" + ps_quote(str(path)) + ");"
            f"$s.TargetPath = {ps_quote(target)}; $s.Arguments = {ps_quote(arguments)};"
            "$s.Description = 'VECTOR';"
            + (f"$s.IconLocation = {ps_quote(str(ICON) + ',0')};" if ICON.exists() else "")
            + "$s.Save()"
        )
        if result.returncode == 0 and path.exists():
            return path
    path = folder / SCRIPT_NAME
    if app:
        target, arguments = app_launcher()
        line = f'start "" "{target}" {arguments}'
    else:
        line = f'start "VECTOR" "{sys.executable}" -m vector'
    path.write_text(
        "@echo off\r\nrem Started by VECTOR. Remove with: vector --startup off\r\n" + line + "\r\n",
        encoding="utf-8",
    )
    return path


def disable(folder: Path | None = None) -> bool:
    if IS_MAC:
        path = (folder or launch_agents()) / f"{MAC_LABEL}.plist"
        if path.exists():
            path.unlink()
            return True
        return False
    folder = folder or startup_folder()
    removed = False
    for name in (SCRIPT_NAME, SHORTCUT_NAME):
        if (folder / name).exists():
            (folder / name).unlink()
            removed = True
    return removed


def is_enabled() -> bool:
    if IS_MAC:
        return (launch_agents() / f"{MAC_LABEL}.plist").exists()
    folder = startup_folder()
    return any((folder / name).exists() for name in (SCRIPT_NAME, SHORTCUT_NAME))


def supported() -> bool:
    return IS_WINDOWS or IS_MAC
