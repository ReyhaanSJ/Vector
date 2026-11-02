"""Windows 10/11-only skills. Only registered when VECTOR runs on Windows."""

from __future__ import annotations

from vector.osutil import open_with_default_app, powershell, run
from vector.registry import tool

# Friendly name -> ms-settings: page (https://learn.microsoft.com/windows/apps/develop/launch/launch-settings-app)
SETTINGS_PAGES = {
    "home": "ms-settings:",
    "wifi": "ms-settings:network-wifi",
    "network": "ms-settings:network-status",
    "bluetooth": "ms-settings:bluetooth",
    "display": "ms-settings:display",
    "night light": "ms-settings:nightlight",
    "sound": "ms-settings:sound",
    "notifications": "ms-settings:notifications",
    "focus": "ms-settings:focus",
    "power": "ms-settings:powersleep",
    "battery": "ms-settings:batterysaver",
    "storage": "ms-settings:storagesense",
    "apps": "ms-settings:appsfeatures",
    "default apps": "ms-settings:defaultapps",
    "startup apps": "ms-settings:startupapps",
    "personalization": "ms-settings:personalization",
    "background": "ms-settings:personalization-background",
    "colors": "ms-settings:personalization-colors",
    "taskbar": "ms-settings:taskbar",
    "mouse": "ms-settings:mousetouchpad",
    "touchpad": "ms-settings:devices-touchpad",
    "keyboard": "ms-settings:typing",
    "printers": "ms-settings:printers",
    "accounts": "ms-settings:yourinfo",
    "time": "ms-settings:dateandtime",
    "language": "ms-settings:regionlanguage",
    "privacy": "ms-settings:privacy",
    "microphone": "ms-settings:privacy-microphone",
    "camera": "ms-settings:privacy-webcam",
    "windows update": "ms-settings:windowsupdate",
    "security": "windowsdefender:",
    "vpn": "ms-settings:network-vpn",
    "hotspot": "ms-settings:network-mobilehotspot",
    "about": "ms-settings:about",
}


def settings_uri(page: str) -> str | None:
    key = page.lower().strip().replace("-", " ").replace("wi fi", "wifi")
    if key in SETTINGS_PAGES:
        return SETTINGS_PAGES[key]
    return next((uri for name, uri in SETTINGS_PAGES.items() if key in name or name in key), None)


@tool
def open_windows_settings(page: str = "home") -> str:
    """Open a page of the Windows Settings app, e.g. "wifi", "bluetooth", "display", "sound",
    "battery", "windows update", "default apps", "startup apps", "microphone", "storage".

    page: Which settings page to open.
    """
    uri = settings_uri(page)
    if not uri:
        return f"No settings page called '{page}'. Options: {', '.join(SETTINGS_PAGES)}"
    open_with_default_app(uri)
    return f"Opened {page} settings."


@tool
def set_dark_mode(enabled: bool) -> str:
    """Switch Windows between dark mode and light mode.

    enabled: True for dark mode, False for light mode.
    """
    import winreg

    path = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
    value = 0 if enabled else 1
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, "AppsUseLightTheme", 0, winreg.REG_DWORD, value)
        winreg.SetValueEx(key, "SystemUsesLightTheme", 0, winreg.REG_DWORD, value)
    return f"{'Dark' if enabled else 'Light'} mode on."


@tool
def set_brightness(level: int) -> str:
    """Set the laptop screen brightness (built-in display only, not external monitors).

    level: Brightness from 0 to 100.
    """
    level = max(0, min(100, int(level)))
    result = powershell(
        "(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods)"
        f" | Invoke-CimMethod -MethodName WmiSetBrightness -Arguments @{{Timeout=1; Brightness={level}}}"
    )
    if result.returncode != 0:
        return "Couldn't change brightness. This only works on a laptop's built-in screen."
    return f"Brightness set to {level}%."


@tool
def show_desktop() -> str:
    """Minimise all windows to show the desktop."""
    powershell("(New-Object -ComObject Shell.Application).MinimizeAll()")
    return "All windows minimised."


@tool
def wifi_status() -> str:
    """Show which Wi-Fi network the laptop is on and the signal strength."""
    result = run(["netsh", "wlan", "show", "interfaces"])
    wanted = ("SSID", "State", "Signal", "Receive rate", "Transmit rate", "Radio type")
    lines = []
    for line in result.stdout.splitlines():
        label = line.split(":", 1)[0].strip()
        if label in wanted and ":" in line:
            lines.append(f"{label}: {line.split(':', 1)[1].strip()}")
    return "\n".join(lines) or "No Wi-Fi adapter found, or Wi-Fi is off."


@tool(dangerous=True)
def empty_recycle_bin() -> str:
    """Permanently empty the Recycle Bin."""
    result = powershell("Clear-RecycleBin -Force -ErrorAction SilentlyContinue")
    return "Recycle Bin emptied." if result.returncode == 0 else f"Failed: {result.stderr.strip()}"
