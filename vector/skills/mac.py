"""macOS-only skills: dark mode, System Settings pages, Wi-Fi, the Bin. Loaded only on a Mac.

Dark mode and the Bin go through AppleScript, so the first time macOS asks whether VECTOR may
control "System Events" / "Finder". Click OK.
"""

from __future__ import annotations

from vector.osutil import open_with_default_app, run
from vector.registry import tool

# Friendly names -> System Settings pages (x-apple.systempreferences: links).
SETTINGS_PAGES = {
    "home": "",
    "wifi": "com.apple.wifi-settings-extension",
    "bluetooth": "com.apple.BluetoothSettings",
    "network": "com.apple.Network-Settings.extension",
    "sound": "com.apple.Sound-Settings.extension",
    "display": "com.apple.Displays-Settings.extension",
    "displays": "com.apple.Displays-Settings.extension",
    "battery": "com.apple.Battery-Settings.extension",
    "appearance": "com.apple.Appearance-Settings.extension",
    "notifications": "com.apple.Notifications-Settings.extension",
    "privacy": "com.apple.settings.PrivacySecurity.extension",
    "keyboard": "com.apple.Keyboard-Settings.extension",
    "wallpaper": "com.apple.Wallpaper-Settings.extension",
    "general": "com.apple.systempreferences.GeneralSettings",
    "software update": "com.apple.Software-Update-Settings.extension",
    "users": "com.apple.Users-Groups-Settings.extension",
}


def _osa(script: str) -> tuple[bool, str]:
    result = run(["osascript", "-e", script])
    return result.returncode == 0, (result.stdout or result.stderr).strip()


def _wifi_device() -> str:
    """The Wi-Fi interface's name (usually en0)."""
    ports = run(["networksetup", "-listallhardwareports"]).stdout.splitlines()
    for i, line in enumerate(ports):
        if line.strip() in ("Hardware Port: Wi-Fi", "Hardware Port: AirPort") and i + 1 < len(ports):
            return ports[i + 1].split(":", 1)[-1].strip() or "en0"
    return "en0"


@tool
def open_mac_settings(page: str = "home") -> str:
    """Open System Settings, optionally on a page: wifi, bluetooth, network, sound, display,
    battery, appearance, notifications, privacy, keyboard, wallpaper, general, software update,
    users.

    page: Which page to open.
    """
    key = page.strip().lower().replace("-", " ")
    pane = SETTINGS_PAGES.get(key, "")
    open_with_default_app(f"x-apple.systempreferences:{pane}" if pane else "/System/Applications/System Settings.app")
    return f"Opened System Settings{f' ({page})' if pane else ''}."


@tool
def set_dark_mode(enabled: bool) -> str:
    """Turn macOS dark mode on or off.

    enabled: True for dark mode, False for light mode.
    """
    ok, out = _osa("tell application \"System Events\" to tell appearance preferences to "
                   f"set dark mode to {'true' if enabled else 'false'}")
    if not ok:
        return (f"Couldn't change it ({out}). Allow VECTOR to control System Events in System "
                "Settings > Privacy & Security > Automation.")
    return f"Dark mode {'on' if enabled else 'off'}."


@tool
def wifi_status() -> str:
    """Whether Wi-Fi is on and connected, and the Mac's network address."""
    device = _wifi_device()
    power = run(["networksetup", "-getairportpower", device]).stdout.strip()
    address = run(["ipconfig", "getifaddr", device]).stdout.strip()
    state = "connected" if address else "not connected"
    return f"{power or 'Wi-Fi: unknown'}; {state}{f' (address {address})' if address else ''}."


@tool(dangerous=True)
def set_wifi(enabled: bool) -> str:
    """Turn Wi-Fi on or off.

    enabled: True to turn Wi-Fi on, False to turn it off.
    """
    device = _wifi_device()
    result = run(["networksetup", "-setairportpower", device, "on" if enabled else "off"])
    if result.returncode != 0:
        return f"Couldn't change Wi-Fi: {(result.stderr or result.stdout).strip()}"
    return f"Wi-Fi turned {'on' if enabled else 'off'}."


@tool
def show_desktop() -> str:
    """Hide every app's windows to show the desktop."""
    ok, out = _osa('tell application "System Events" to set visible of (every process whose '
                   'visible is true and name is not "Finder") to false')
    return "Showing the desktop." if ok else f"Couldn't do that ({out})."


@tool(dangerous=True)
def empty_bin() -> str:
    """Empty the Bin (Trash). Files in it are deleted for good."""
    ok, out = _osa('tell application "Finder" to empty trash')
    return "Emptied the Bin." if ok else f"Couldn't empty the Bin ({out})."
