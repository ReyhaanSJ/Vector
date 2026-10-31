"""System status, volume, screen lock, screenshots and shell commands."""

from __future__ import annotations

import datetime as dt
import platform
import shutil
from pathlib import Path

import psutil

from vector.osutil import IS_LINUX, IS_MAC, IS_WINDOWS, run
from vector.registry import tool


@tool
def current_time() -> str:
    """Get the current local date and time."""
    return dt.datetime.now().strftime("%A, %d %B %Y, %I:%M %p")


@tool
def system_status() -> str:
    """Report battery, CPU, memory, disk usage and uptime."""
    lines = [f"OS: {platform.system()} {platform.release()}"]
    lines.append(f"CPU: {psutil.cpu_percent(interval=0.5):.0f}% used, {psutil.cpu_count()} cores")
    mem = psutil.virtual_memory()
    lines.append(f"Memory: {mem.percent:.0f}% used ({mem.used / 2**30:.1f} of {mem.total / 2**30:.1f} GB)")
    disk = psutil.disk_usage(str(Path.home()))
    lines.append(f"Disk: {disk.percent:.0f}% used ({disk.free / 2**30:.0f} GB free)")
    battery = psutil.sensors_battery() if hasattr(psutil, "sensors_battery") else None
    if battery:
        state = "charging" if battery.power_plugged else "on battery"
        lines.append(f"Battery: {battery.percent:.0f}% ({state})")
    boot = dt.datetime.fromtimestamp(psutil.boot_time())
    uptime = dt.datetime.now() - boot
    lines.append(f"Uptime: {uptime.days}d {uptime.seconds // 3600}h {(uptime.seconds // 60) % 60}m")
    return "\n".join(lines)


@tool
def set_volume(level: int) -> str:
    """Set the speaker volume.

    level: Volume from 0 (mute) to 100.
    """
    level = max(0, min(100, int(level)))
    if IS_MAC:
        run(["osascript", "-e", f"set volume output volume {level}"])
    elif IS_LINUX:
        if shutil.which("pactl"):
            run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{level}%"])
        elif shutil.which("amixer"):
            run(["amixer", "-q", "set", "Master", f"{level}%"])
        else:
            return "No volume tool found (install pulseaudio-utils or alsa-utils)."
    elif IS_WINDOWS:
        # Press the volume-down key 50 times (to 0) then up level/2 times (each press = 2%).
        ps = (
            "$w = New-Object -ComObject WScript.Shell;"
            "1..50 | % { $w.SendKeys([char]174) };"
            f"1..{level // 2} | % {{ $w.SendKeys([char]175) }}"
        )
        if level >= 2:
            run(["powershell", "-NoProfile", "-Command", ps])
        else:
            run(["powershell", "-NoProfile", "-Command",
                 "$w = New-Object -ComObject WScript.Shell; 1..50 | % { $w.SendKeys([char]174) }"])
    return f"Volume set to {level}%."


@tool
def lock_screen() -> str:
    """Lock the computer screen."""
    if IS_WINDOWS:
        run(["rundll32.exe", "user32.dll,LockWorkStation"])
    elif IS_MAC:
        run(["pmset", "displaysleepnow"])
    elif shutil.which("loginctl"):
        run(["loginctl", "lock-session"])
    elif shutil.which("xdg-screensaver"):
        run(["xdg-screensaver", "lock"])
    else:
        return "Couldn't find a way to lock the screen on this system."
    return "Screen locked."


@tool
def take_screenshot(filename: str = "") -> str:
    """Take a screenshot and save it to the Pictures folder.

    filename: Optional file name; defaults to a timestamp.
    """
    folder = Path.home() / "Pictures" / "VECTOR"
    folder.mkdir(parents=True, exist_ok=True)
    name = filename or f"screenshot-{dt.datetime.now():%Y%m%d-%H%M%S}.png"
    if not name.lower().endswith(".png"):
        name += ".png"
    path = folder / name
    try:
        import pyautogui  # optional dependency

        pyautogui.screenshot(str(path))
    except ImportError:
        if IS_MAC:
            run(["screencapture", "-x", str(path)])
        elif IS_LINUX and shutil.which("gnome-screenshot"):
            run(["gnome-screenshot", "-f", str(path)])
        elif IS_LINUX and shutil.which("scrot"):
            run(["scrot", str(path)])
        else:
            return "Install the 'control' extra (pip install vector-assistant[control]) for screenshots."
    return f"Screenshot saved to {path}" if path.exists() else "Screenshot failed."


@tool(dangerous=True)
def run_shell_command(command: str, timeout_seconds: int = 60) -> str:
    """Run a shell/terminal command and return its output. Use for tasks no other skill covers.

    command: The exact command to run.
    timeout_seconds: Give up after this many seconds.
    """
    try:
        result = run(command, shell=True, timeout=timeout_seconds)
    except Exception as exc:
        return f"Command failed to run: {exc}"
    out = (result.stdout or "") + (("\n[stderr]\n" + result.stderr) if result.stderr else "")
    out = out.strip() or "(no output)"
    if len(out) > 6000:
        out = out[:6000] + "\n... (output truncated)"
    return f"exit code {result.returncode}\n{out}"


@tool(dangerous=True)
def power_action(action: str) -> str:
    """Shut down, restart or put the computer to sleep.

    action: One of "shutdown", "restart", "sleep".
    """
    action = action.lower()
    commands = {
        "windows": {"shutdown": "shutdown /s /t 0", "restart": "shutdown /r /t 0",
                    "sleep": "rundll32.exe powrprof.dll,SetSuspendState 0,1,0"},
        "mac": {"shutdown": "osascript -e 'tell app \"System Events\" to shut down'",
                "restart": "osascript -e 'tell app \"System Events\" to restart'",
                "sleep": "pmset sleepnow"},
        "linux": {"shutdown": "systemctl poweroff", "restart": "systemctl reboot",
                  "sleep": "systemctl suspend"},
    }
    key = "windows" if IS_WINDOWS else "mac" if IS_MAC else "linux"
    cmd = commands[key].get(action)
    if not cmd:
        return "Action must be shutdown, restart or sleep."
    run(cmd, shell=True)
    return f"{action.capitalize()} requested."
