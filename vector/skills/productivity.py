"""Memory, notes, reminders, clipboard and notifications."""

from __future__ import annotations

import datetime as dt
import json
import threading

from vector.config import HOME_DIR
from vector.osutil import notify
from vector.registry import tool

MEMORY_FILE = HOME_DIR / "memory.json"


def _load_memory() -> dict:
    try:
        return json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"facts": []}


def _save_memory(data: dict) -> None:
    MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    MEMORY_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def memory_summary() -> str:
    """Saved facts, injected into VECTOR's system prompt so it remembers across sessions."""
    facts = _load_memory().get("facts", [])
    return "\n".join(f"- {f['text']}" for f in facts[-50:])


@tool
def remember(fact: str) -> str:
    """Save a fact or preference about the user to long-term memory (persists between sessions).

    fact: The thing to remember, e.g. "My project folder is ~/code/robotics".
    """
    data = _load_memory()
    data.setdefault("facts", []).append({"text": fact, "saved": dt.datetime.now().isoformat()})
    _save_memory(data)
    return "Got it, I'll remember that."


@tool
def recall(query: str = "") -> str:
    """Look up saved memories. Leave query empty to list everything.

    query: Words to search for.
    """
    facts = _load_memory().get("facts", [])
    if query:
        words = query.lower().split()
        facts = [f for f in facts if any(w in f["text"].lower() for w in words)]
    return "\n".join(f"{i + 1}. {f['text']}" for i, f in enumerate(facts)) or "Nothing saved yet."


@tool
def forget(query: str) -> str:
    """Delete saved memories that contain the given text.

    query: Text the memory contains.
    """
    data = _load_memory()
    before = len(data.get("facts", []))
    data["facts"] = [f for f in data.get("facts", []) if query.lower() not in f["text"].lower()]
    _save_memory(data)
    return f"Forgot {before - len(data['facts'])} memory item(s)."


_timers: list[threading.Timer] = []


@tool
def set_reminder(message: str, minutes: float) -> str:
    """Set a timer/reminder that pops up a desktop notification after some minutes.
    VECTOR must stay running for it to fire.

    message: What to remind the user about.
    minutes: How many minutes from now (can be fractional, e.g. 0.5).
    """
    seconds = max(1.0, float(minutes) * 60)
    timer = threading.Timer(seconds, notify, args=("VECTOR reminder", message))
    timer.daemon = True
    timer.start()
    _timers.append(timer)
    at = dt.datetime.now() + dt.timedelta(seconds=seconds)
    return f"Reminder set for {at:%I:%M %p}: {message}"


@tool
def show_notification(title: str, message: str) -> str:
    """Show a desktop notification right now.

    title: Notification title.
    message: Notification text.
    """
    notify(title, message)
    return "Notification shown."


@tool
def read_clipboard() -> str:
    """Get the text currently copied to the clipboard."""
    import pyperclip

    try:
        text = pyperclip.paste()
    except pyperclip.PyperclipException as exc:
        return f"Clipboard unavailable: {exc}"
    return text[:8000] or "(clipboard is empty)"


@tool
def write_clipboard(text: str) -> str:
    """Copy text to the clipboard so the user can paste it anywhere.

    text: The text to copy.
    """
    import pyperclip

    try:
        pyperclip.copy(text)
    except pyperclip.PyperclipException as exc:
        return f"Clipboard unavailable: {exc}"
    return "Copied to clipboard."
