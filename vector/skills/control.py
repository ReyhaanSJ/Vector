"""Keyboard and media control (needs the optional 'control' extra: pyautogui)."""

from __future__ import annotations

from vector.registry import tool
from vector.skills.screen import _prepare

_MISSING = "Keyboard control needs pyautogui: pip install 'vector-assistant[control]'"


def _gui():
    try:
        import pyautogui

        return pyautogui
    except Exception:  # ImportError, or no display available
        return None


@tool(screen=True)
def type_text(text: str) -> str:
    """Type text into whatever window is focused, as if on the keyboard.

    text: The text to type.
    """
    gui = _gui()
    if not gui:
        return _MISSING
    _prepare()
    gui.write(text, interval=0.01)
    return "Typed it."


@tool(screen=True)
def press_keys(keys: list[str]) -> str:
    """Press a keyboard shortcut, e.g. ["ctrl", "s"] to save or ["alt", "tab"] to switch windows.

    keys: Keys to hold together, e.g. ["ctrl", "shift", "t"]. Use "command" for the Mac key.
    """
    gui = _gui()
    if not gui:
        return _MISSING
    _prepare()
    gui.hotkey(*[k.lower() for k in keys])
    return f"Pressed {'+'.join(keys)}."


@tool
def media_control(action: str) -> str:
    """Control music/video playback.

    action: One of "playpause", "next", "previous", "mute", "volumeup", "volumedown".
    """
    keymap = {
        "playpause": "playpause", "play": "playpause", "pause": "playpause",
        "next": "nexttrack", "previous": "prevtrack", "mute": "volumemute",
        "volumeup": "volumeup", "volumedown": "volumedown",
    }
    key = keymap.get(action.lower().replace(" ", "").replace("_", ""))
    if not key:
        return f"Unknown media action '{action}'."
    gui = _gui()
    if not gui:
        return _MISSING
    gui.press(key)
    return f"Media: {action}."
