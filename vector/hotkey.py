"""System-wide keyboard shortcut (default Ctrl+Shift+Space) that opens the summon bar.

Windows uses the built-in RegisterHotKey API (no extra packages, no admin rights).
Other systems use pynput if it is installed.
"""

from __future__ import annotations

import sys
import threading
from collections.abc import Callable

MODIFIERS = {"alt": 0x0001, "ctrl": 0x0002, "control": 0x0002, "shift": 0x0004,
             "win": 0x0008, "windows": 0x0008, "cmd": 0x0008}
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012

KEYS = {"space": 0x20, "enter": 0x0D, "tab": 0x09, "esc": 0x1B, "escape": 0x1B,
        "backquote": 0xC0, "`": 0xC0, "insert": 0x2D, "home": 0x24, "end": 0x23,
        "pageup": 0x21, "pagedown": 0x22}
KEYS.update({f"f{i}": 0x6F + i for i in range(1, 13)})
KEYS.update({chr(c).lower(): c for c in range(ord("A"), ord("Z") + 1)})
KEYS.update({str(d): 0x30 + d for d in range(10)})


class HotkeyError(ValueError):
    pass


def parse_hotkey(text: str, allow_bare: bool = False) -> tuple[int, int]:
    """'ctrl+shift+space' -> (modifier flags, virtual-key code)."""
    parts = [p.strip().lower() for p in text.replace(" ", "").split("+") if p.strip()]
    if not parts:
        raise HotkeyError("Empty shortcut")
    *mods, key = parts
    flags = 0
    for m in mods:
        if m not in MODIFIERS:
            raise HotkeyError(f"Unknown modifier '{m}' (use ctrl, shift, alt or win)")
        flags |= MODIFIERS[m]
    if key not in KEYS:
        raise HotkeyError(f"Unknown key '{key}'")
    if not flags and not allow_bare:
        raise HotkeyError("A shortcut needs at least one of ctrl, shift, alt or win")
    return flags, KEYS[key]


def to_pynput(text: str) -> str:
    """'ctrl+shift+space' -> '<ctrl>+<shift>+<space>'."""
    out = []
    for p in text.lower().replace(" ", "").split("+"):
        p = {"control": "ctrl", "win": "cmd", "windows": "cmd", "escape": "esc"}.get(p, p)
        out.append(p if len(p) == 1 else f"<{p}>")
    return "+".join(out)


class GlobalHotkey:
    """Calls `callback` (from a background thread) whenever the shortcut is pressed."""

    def __init__(self, combo: str, callback: Callable[[], None], allow_bare: bool = False):
        self.combo = combo
        self.allow_bare = allow_bare
        self.callback = callback
        self.error: str | None = None
        self._thread: threading.Thread | None = None
        self._thread_id = None
        self._listener = None
        self._ready = threading.Event()

    def start(self) -> bool:
        """Start listening. False (with .error set) if the shortcut can't be used."""
        try:
            parse_hotkey(self.combo, self.allow_bare)
        except HotkeyError as exc:
            self.error = str(exc)
            return False
        if sys.platform == "win32":
            self._thread = threading.Thread(target=self._windows_loop, name="vector-hotkey", daemon=True)
            self._thread.start()
            self._ready.wait(3)
            return self.error is None
        try:
            from pynput import keyboard

            self._listener = keyboard.GlobalHotKeys({to_pynput(self.combo): self.callback})
            self._listener.start()
            return True
        except Exception as exc:
            self.error = f"Keyboard shortcuts need pynput on this system ({exc})"
            return False

    def _windows_loop(self) -> None:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        self._thread_id = kernel32.GetCurrentThreadId()
        flags, vk = parse_hotkey(self.combo, self.allow_bare)
        if not user32.RegisterHotKey(None, 1, flags | MOD_NOREPEAT, vk):
            self.error = (f"{self.combo} is already used by another app. "
                          "Pick another with: vector --set hotkey=ctrl+alt+v")
            self._ready.set()
            return
        self._ready.set()
        msg = wintypes.MSG()
        try:
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == WM_HOTKEY:
                    try:
                        self.callback()
                    except Exception:
                        pass
        finally:
            user32.UnregisterHotKey(None, 1)

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
        if sys.platform == "win32" and self._thread_id:
            import ctypes

            ctypes.windll.user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
