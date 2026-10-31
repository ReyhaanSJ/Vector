"""Opening and closing apps, websites and searches."""

from __future__ import annotations

import shutil
import urllib.parse
import webbrowser
from pathlib import Path

import psutil

from vector.osutil import IS_MAC, IS_WINDOWS, open_with_default_app, run, spawn
from vector.registry import tool

# Friendly names -> the command/app name on each OS. Add your own via a custom skill.
APP_ALIASES: dict[str, dict[str, str]] = {
    "chrome": {"windows": "chrome", "mac": "Google Chrome", "linux": "google-chrome"},
    "firefox": {"windows": "firefox", "mac": "Firefox", "linux": "firefox"},
    "vscode": {"windows": "code", "mac": "Visual Studio Code", "linux": "code"},
    "code": {"windows": "code", "mac": "Visual Studio Code", "linux": "code"},
    "terminal": {"windows": "wt", "mac": "Terminal", "linux": "x-terminal-emulator"},
    "notepad": {"windows": "notepad", "mac": "TextEdit", "linux": "gedit"},
    "calculator": {"windows": "calc", "mac": "Calculator", "linux": "gnome-calculator"},
    "spotify": {"windows": "spotify", "mac": "Spotify", "linux": "spotify"},
    "discord": {"windows": "discord", "mac": "Discord", "linux": "discord"},
    "slack": {"windows": "slack", "mac": "Slack", "linux": "slack"},
    "settings": {"windows": "ms-settings:", "mac": "System Settings", "linux": "gnome-control-center"},
}

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
    """Open an application on the computer, e.g. "chrome", "spotify", "vscode", "terminal".

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
            if target.endswith(":"):
                open_with_default_app(target)
            else:
                spawn(f'start "" "{target}"', shell=True)
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
def web_search(query: str, engine: str = "google") -> str:
    """Search the web in the browser (Google, YouTube, GitHub, Maps, Wikipedia, DuckDuckGo).

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
