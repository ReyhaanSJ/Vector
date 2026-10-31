"""Example personal skills. Copy this file to ~/.vector/skills/ and edit to taste."""

import webbrowser

from vector import tool
from vector.skills.apps import open_app


@tool
def start_work_mode() -> str:
    """Set up the user's work/study workspace: open the editor, music and key websites.
    Use when the user says things like "work mode", "let's get to work" or "study time"."""
    opened = [open_app("vscode"), open_app("spotify")]
    for url in ("https://github.com", "https://calendar.google.com"):
        webbrowser.open(url)
        opened.append(f"Opened {url}")
    return "\n".join(opened)


@tool
def convert_temperature(value: float, to: str = "celsius") -> str:
    """Convert a temperature between Celsius and Fahrenheit.

    value: The temperature to convert.
    to: "celsius" or "fahrenheit".
    """
    result = (value - 32) * 5 / 9 if to == "celsius" else value * 9 / 5 + 32
    return f"{result:.1f} degrees {to}"
