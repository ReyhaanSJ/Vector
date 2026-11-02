"""Opening and closing apps, websites and searches."""

from __future__ import annotations

import functools
import json
import shutil
import urllib.parse
import webbrowser
from pathlib import Path

import psutil

from vector.osutil import IS_MAC, IS_WINDOWS, open_with_default_app, powershell, run, spawn
from vector.registry import tool

# Friendly names -> the app's name on each OS. On Windows this is the Start-menu name.
APP_ALIASES: dict[str, dict[str, str]] = {
    "chrome": {"windows": "Google Chrome", "mac": "Google Chrome", "linux": "google-chrome"},
    "edge": {"windows": "Microsoft Edge", "mac": "Microsoft Edge", "linux": "microsoft-edge"},
    "firefox": {"windows": "Firefox", "mac": "Firefox", "linux": "firefox"},
    "vscode": {"windows": "Visual Studio Code", "mac": "Visual Studio Code", "linux": "code"},
    "vs code": {"windows": "Visual Studio Code", "mac": "Visual Studio Code", "linux": "code"},
    "code": {"windows": "Visual Studio Code", "mac": "Visual Studio Code", "linux": "code"},
    "terminal": {"windows": "Terminal", "mac": "Terminal", "linux": "x-terminal-emulator"},
    "cmd": {"windows": "Command Prompt", "mac": "Terminal", "linux": "x-terminal-emulator"},
    "notepad": {"windows": "Notepad", "mac": "TextEdit", "linux": "gedit"},
    "calculator": {"windows": "Calculator", "mac": "Calculator", "linux": "gnome-calculator"},
    "word": {"windows": "Word", "mac": "Microsoft Word", "linux": "libreoffice --writer"},
    "excel": {"windows": "Excel", "mac": "Microsoft Excel", "linux": "libreoffice --calc"},
    "powerpoint": {"windows": "PowerPoint", "mac": "Microsoft PowerPoint", "linux": "libreoffice --impress"},
    "teams": {"windows": "Microsoft Teams", "mac": "Microsoft Teams", "linux": "teams"},
    "spotify": {"windows": "Spotify", "mac": "Spotify", "linux": "spotify"},
    "discord": {"windows": "Discord", "mac": "Discord", "linux": "discord"},
    "slack": {"windows": "Slack", "mac": "Slack", "linux": "slack"},
    "task manager": {"windows": "Task Manager", "mac": "Activity Monitor", "linux": "gnome-system-monitor"},
    "settings": {"windows": "ms-settings:", "mac": "System Settings", "linux": "gnome-control-center"},
}


@functools.lru_cache(maxsize=1)
def windows_start_apps() -> tuple[tuple[str, str], ...]:
    """Every app in the Windows Start menu as (name, AppID), including Microsoft Store apps."""
    result = powershell("Get-StartApps | Select-Object Name, AppID | ConvertTo-Json -Compress")
    try:
        data = json.loads(result.stdout or "[]")
    except ValueError:
        return ()
    if isinstance(data, dict):
        data = [data]
    return tuple((d["Name"], d["AppID"]) for d in data if d.get("Name") and d.get("AppID"))


def best_app_match(query: str, apps) -> tuple[str, str] | None:
    """Pick the app whose name best matches what the user said."""
    q = query.lower().strip()
    if not q:
        return None
    names = [(name.lower(), (name, app_id)) for name, app_id in apps]
    for test in (
        lambda n: n == q,
        lambda n: n.startswith(q),
        lambda n: any(word.startswith(q) for word in n.split()),
        lambda n: q in n,
    ):
        hits = [app for n, app in names if test(n)]
        if hits:
            return min(hits, key=lambda app: len(app[0]))  # shortest = least specific match
    return None


def _open_windows_app(name: str, target: str) -> str:
    if target.endswith(":"):  # a URI like ms-settings:
        open_with_default_app(target)
        return f"Opened {name}."
    match = best_app_match(target, windows_start_apps()) or best_app_match(name, windows_start_apps())
    if match:
        app_name, app_id = match
        spawn(["explorer.exe", f"shell:AppsFolder\\{app_id}"])
        return f"Opened {app_name}."
    if shutil.which(target) or shutil.which(name):
        spawn(f'start "" "{shutil.which(target) or shutil.which(name)}"', shell=True)
        return f"Opened {name}."
    return f"Couldn't find an app called '{name}' in the Start menu. Is it installed?"

SEARCH_ENGINES = {
    "google": "https://www.google.com/search?q={}",
    "youtube": "https://www.youtube.com/results?search_query={}",
    "duckduckgo": "https://duckduckgo.com/?q={}",
    "github": "https://github.com/search?q={}",
    "maps": "https://www.google.com/maps/search/{}",
    "wikipedia": "https://en.wikipedia.org/w/index.php?search={}",
}


def _os_key() -> str:
    return "windows" if IS_WINDOWS else "mac" if IS_MAC else "linux"


@tool
def open_app(name: str) -> str:
    """Open any installed application, e.g. "chrome", "spotify", "vscode", "word", "terminal".

    name: The app's name as the user said it.
    """
    key = name.strip().lower()
    if key in {"browser", "web browser", "internet"}:
        webbrowser.open("https://www.google.com")
        return "Opened the browser."
    if key in {"files", "file manager", "explorer", "finder"}:
        open_with_default_app(str(Path.home()))
        return "Opened the file manager."
    target = APP_ALIASES.get(key, {}).get(_os_key(), name.strip())
    try:
        if IS_MAC:
            result = run(["open", "-a", target])
            if result.returncode != 0:
                return f"Couldn't find an app called '{name}' ({result.stderr.strip()})"
        elif IS_WINDOWS:
            return _open_windows_app(name, target)
        else:
            parts = target.split()
            if not shutil.which(parts[0]):
                return f"Couldn't find '{parts[0]}' on this system. Is it installed?"
            spawn(parts)
    except Exception as exc:
        return f"Failed to open {name}: {exc}"
    return f"Opened {name}."


@tool(dangerous=True)
def close_app(name: str) -> str:
    """Close (quit) every running process whose name matches the app name.

    name: App/process name, e.g. "spotify" or "chrome".
    """
    needle = name.strip().lower()
    closed = []
    for proc in psutil.process_iter(["name"]):
        pname = (proc.info.get("name") or "").lower()
        if needle in pname:
            try:
                proc.terminate()
                closed.append(pname)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    if not closed:
        return f"No running app matched '{name}'."
    return f"Closed {len(closed)} process(es): {', '.join(sorted(set(closed)))}"


@tool
def open_website(url: str) -> str:
    """Open a website in the default browser.

    url: The address, e.g. "github.com" or "https://news.ycombinator.com".
    """
    if "://" not in url:
        url = "https://" + url
    webbrowser.open(url)
    return f"Opened {url}"


@tool
def search_in_browser(query: str, engine: str = "google") -> str:
    """Open a search in the user's browser (Google, YouTube, GitHub, Maps, Wikipedia, DuckDuckGo),
    for when the user wants to see the results themselves. To read results yourself, use search_web.

    query: What to search for.
    engine: One of google, youtube, duckduckgo, github, maps, wikipedia.
    """
    template = SEARCH_ENGINES.get(engine.lower(), SEARCH_ENGINES["google"])
    url = template.format(urllib.parse.quote_plus(query))
    webbrowser.open(url)
    return f"Searching {engine} for '{query}'."


@tool
def list_running_apps(limit: int = 15) -> str:
    """List the apps using the most memory right now.

    limit: How many to show.
    """
    procs = []
    for proc in psutil.process_iter(["name", "memory_info"]):
        mem = proc.info.get("memory_info")
        if mem and proc.info.get("name"):
            procs.append((mem.rss, proc.info["name"]))
    procs.sort(reverse=True)
    lines = [f"{name}: {rss / 1_048_576:.0f} MB" for rss, name in procs[:limit]]
    return "\n".join(lines) or "No processes found."
