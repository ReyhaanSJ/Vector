"""macOS pieces: the global shortcut, the app's name and icon, and API keys in the Keychain.

Everything here uses what ships with macOS (Carbon, the Objective-C runtime, the `security`
tool) through ctypes, so no extra packages are needed. Every function is safe to call on other
systems: it just does nothing.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

IS_MAC = sys.platform == "darwin"

APP_NAME = "VECTOR"
APP_BUNDLE = Path.home() / "Applications" / "VECTOR.app"
APP_DIR = Path.home() / "Library" / "Application Support" / "VECTOR"
KEYCHAIN_SERVICE = "VECTOR"
KEY_NAMES = ("ANTHROPIC_API_KEY", "OPENROUTER_API_KEY")

# -- API keys in the Keychain ------------------------------------------------------------------
# Apps opened from the Dock or at login don't see the shell's environment variables, so the
# installer keeps API keys in the user's login Keychain and VECTOR loads them at start.


def keychain_get(name: str) -> str:
    if not IS_MAC:
        return ""
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-a", name, "-w"],
            capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def keychain_set(name: str, value: str) -> bool:
    if not IS_MAC:
        return False
    try:
        result = subprocess.run(
            ["security", "add-generic-password", "-U", "-s", KEYCHAIN_SERVICE, "-a", name,
             "-l", f"VECTOR {name}", "-w", value],
            capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def keychain_delete(name: str) -> bool:
    if not IS_MAC:
        return False
    try:
        result = subprocess.run(
            ["security", "delete-generic-password", "-s", KEYCHAIN_SERVICE, "-a", name],
            capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def load_keys() -> list[str]:
    """Put saved API keys into os.environ (unless already set). Returns the names loaded."""
    loaded = []
    if not IS_MAC or os.environ.get("VECTOR_NO_KEYCHAIN") == "1":
        return loaded
    for name in KEY_NAMES:
        if not os.environ.get(name):
            value = keychain_get(name).strip().strip("\"'").strip()
            if value:
                os.environ[name] = value
                loaded.append(name)
    return loaded


# -- the Objective-C runtime (just enough to rename the app) -----------------------------------
_objc = None


def _runtime():
    global _objc
    if _objc is None:
        path = ctypes.util.find_library("objc") or "/usr/lib/libobjc.A.dylib"
        _objc = ctypes.CDLL(path)
        _objc.objc_getClass.restype = ctypes.c_void_p
        _objc.objc_getClass.argtypes = [ctypes.c_char_p]
        _objc.sel_registerName.restype = ctypes.c_void_p
        _objc.sel_registerName.argtypes = [ctypes.c_char_p]
        ctypes.CDLL("/System/Library/Frameworks/Foundation.framework/Foundation")
    return _objc


def _send(obj, selector: str, *args, restype=ctypes.c_void_p, argtypes=()):
    """[obj selector:args...] with the right C types (needed on Apple silicon)."""
    objc = _runtime()
    fn = ctypes.cast(objc.objc_msgSend, ctypes.CFUNCTYPE(restype, ctypes.c_void_p, ctypes.c_void_p,
                                                         *argtypes))
    return fn(obj, objc.sel_registerName(selector.encode()), *args)


def _nsstring(text: str):
    cls = _runtime().objc_getClass(b"NSString")
    return _send(cls, "stringWithUTF8String:", text.encode(), argtypes=(ctypes.c_char_p,))


def set_app_name(name: str = APP_NAME) -> bool:
    """Show "VECTOR" (not "Python") in the menu bar and Dock. Call before creating Tk."""
    if not IS_MAC:
        return False
    try:
        bundle = _send(_runtime().objc_getClass(b"NSBundle"), "mainBundle")
        for getter in ("localizedInfoDictionary", "infoDictionary"):
            info = _send(bundle, getter)
            if info:
                _send(info, "setObject:forKey:", _nsstring(name), _nsstring("CFBundleName"),
                      argtypes=(ctypes.c_void_p, ctypes.c_void_p))
        return app_name() == name
    except Exception:
        return False


def app_name() -> str:
    if not IS_MAC:
        return ""
    bundle = _send(_runtime().objc_getClass(b"NSBundle"), "mainBundle")
    info = _send(bundle, "infoDictionary")
    value = _send(info, "objectForKey:", _nsstring("CFBundleName"), argtypes=(ctypes.c_void_p,))
    if not value:
        return ""
    raw = _send(value, "UTF8String", restype=ctypes.c_char_p)
    return raw.decode() if raw else ""


# -- the global shortcut (Carbon RegisterEventHotKey) -------------------------------------------
# Carbon hotkeys need no Accessibility permission and arrive on the main thread through the
# normal event loop (which Tk runs), so they're safe to use together with Tk.

# Key codes from Carbon's Events.h (kVK_*): they're positions on the keyboard, not letters.
KEY_CODES = {
    "a": 0, "s": 1, "d": 2, "f": 3, "h": 4, "g": 5, "z": 6, "x": 7, "c": 8, "v": 9, "b": 11,
    "q": 12, "w": 13, "e": 14, "r": 15, "y": 16, "t": 17, "1": 18, "2": 19, "3": 20, "4": 21,
    "6": 22, "5": 23, "9": 25, "7": 26, "8": 28, "0": 29, "o": 31, "u": 32, "i": 34, "p": 35,
    "l": 37, "j": 38, "k": 40, "n": 45, "m": 46,
    "enter": 36, "return": 36, "tab": 48, "space": 49, "backquote": 50, "`": 50,
    "esc": 53, "escape": 53, "home": 115, "pageup": 116, "end": 119, "pagedown": 121,
    "insert": 114,
    "f1": 122, "f2": 120, "f3": 99, "f4": 118, "f5": 96, "f6": 97, "f7": 98, "f8": 100,
    "f9": 101, "f10": 109, "f11": 103, "f12": 111,
}
MODIFIER_BITS = {"cmd": 0x0100, "command": 0x0100, "win": 0x0100, "windows": 0x0100,
                 "shift": 0x0200, "alt": 0x0800, "option": 0x0800,
                 "ctrl": 0x1000, "control": 0x1000}

_EVENT_CLASS_KEYBOARD = int.from_bytes(b"keyb", "big")
_EVENT_HOTKEY_PRESSED = 5
_PARAM_DIRECT_OBJECT = int.from_bytes(b"----", "big")
_TYPE_HOTKEY_ID = int.from_bytes(b"hkid", "big")
_SIGNATURE = int.from_bytes(b"VCTR", "big")


class _EventTypeSpec(ctypes.Structure):
    _fields_ = [("eventClass", ctypes.c_uint32), ("eventKind", ctypes.c_uint32)]


class _EventHotKeyID(ctypes.Structure):
    _fields_ = [("signature", ctypes.c_uint32), ("id", ctypes.c_uint32)]


_HANDLER = ctypes.CFUNCTYPE(ctypes.c_int32, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
_carbon = None
_handler_ref = None   # keeps the C callback alive
_callbacks: dict[int, Callable[[], None]] = {}
_next_id = [1]


def parse_combo(text: str) -> tuple[int, int]:
    """'ctrl+shift+space' -> (Carbon modifier bits, key code). Raises ValueError."""
    parts = [p.strip().lower() for p in text.replace(" ", "").split("+") if p.strip()]
    if not parts:
        raise ValueError("Empty shortcut")
    *mods, key = parts
    bits = 0
    for m in mods:
        if m not in MODIFIER_BITS:
            raise ValueError(f"Unknown modifier '{m}' (use ctrl, shift, alt/option or cmd)")
        bits |= MODIFIER_BITS[m]
    if key not in KEY_CODES:
        raise ValueError(f"Unknown key '{key}'")
    return bits, KEY_CODES[key]


def _load_carbon():
    global _carbon, _handler_ref
    if _carbon is not None:
        return _carbon
    carbon = ctypes.CDLL("/System/Library/Frameworks/Carbon.framework/Carbon")
    carbon.GetApplicationEventTarget.restype = ctypes.c_void_p
    carbon.GetApplicationEventTarget.argtypes = []
    carbon.InstallEventHandler.restype = ctypes.c_int32
    carbon.InstallEventHandler.argtypes = [ctypes.c_void_p, _HANDLER, ctypes.c_ulong,
                                           ctypes.POINTER(_EventTypeSpec), ctypes.c_void_p,
                                           ctypes.POINTER(ctypes.c_void_p)]
    carbon.RegisterEventHotKey.restype = ctypes.c_int32
    carbon.RegisterEventHotKey.argtypes = [ctypes.c_uint32, ctypes.c_uint32, _EventHotKeyID,
                                           ctypes.c_void_p, ctypes.c_uint32,
                                           ctypes.POINTER(ctypes.c_void_p)]
    carbon.UnregisterEventHotKey.restype = ctypes.c_int32
    carbon.UnregisterEventHotKey.argtypes = [ctypes.c_void_p]
    carbon.GetEventParameter.restype = ctypes.c_int32
    carbon.GetEventParameter.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32,
                                         ctypes.c_void_p, ctypes.c_ulong, ctypes.c_void_p,
                                         ctypes.c_void_p]

    def on_event(_next, event, _data):
        hotkey = _EventHotKeyID()
        status = carbon.GetEventParameter(event, _PARAM_DIRECT_OBJECT, _TYPE_HOTKEY_ID, None,
                                          ctypes.sizeof(hotkey), None, ctypes.byref(hotkey))
        callback = _callbacks.get(hotkey.id) if status == 0 else None
        if callback is not None:
            try:
                callback()
            except Exception:
                pass
        return 0

    _handler_ref = _HANDLER(on_event)
    spec = _EventTypeSpec(_EVENT_CLASS_KEYBOARD, _EVENT_HOTKEY_PRESSED)
    status = carbon.InstallEventHandler(carbon.GetApplicationEventTarget(), _handler_ref, 1,
                                        ctypes.byref(spec), None, None)
    if status != 0:
        raise OSError(f"InstallEventHandler failed ({status})")
    _carbon = carbon
    return carbon


class CarbonHotkey:
    """A system-wide shortcut. Register it from the main (Tk) thread."""

    def __init__(self, combo: str, callback: Callable[[], None]):
        self.combo = combo
        self.callback = callback
        self._ref = None
        self._id = 0

    def register(self) -> str | None:
        """None if it worked, otherwise a message saying why not."""
        if not IS_MAC:
            return "Carbon shortcuts only exist on macOS"
        try:
            bits, code = parse_combo(self.combo)
            carbon = _load_carbon()
        except (ValueError, OSError) as exc:
            return str(exc)
        self._id = _next_id[0]
        _next_id[0] += 1
        _callbacks[self._id] = self.callback
        ref = ctypes.c_void_p()
        status = carbon.RegisterEventHotKey(code, bits, _EventHotKeyID(_SIGNATURE, self._id),
                                            carbon.GetApplicationEventTarget(), 0,
                                            ctypes.byref(ref))
        if status != 0:
            _callbacks.pop(self._id, None)
            return (f"{self.combo} is already used by another app or by macOS. "
                    "Pick another with: vector --set hotkey=ctrl+alt+v")
        self._ref = ref
        return None

    def unregister(self) -> None:
        if self._ref is not None and _carbon is not None:
            _carbon.UnregisterEventHotKey(self._ref)
        self._ref = None
        _callbacks.pop(self._id, None)


# -- windows: bring VECTOR to the front, round the summon bar's corners --------------------------
def _ns_app():
    return _send(_runtime().objc_getClass(b"NSApplication"), "sharedApplication")


def activate() -> bool:
    """Make VECTOR the active app, so the summon bar gets the keyboard straight away."""
    if not IS_MAC:
        return False
    try:
        _send(_ns_app(), "activateIgnoringOtherApps:", True, restype=None, argtypes=(ctypes.c_bool,))
        return True
    except Exception:
        return False


def _find_window(title: str):
    windows = _send(_ns_app(), "windows")
    count = _send(windows, "count", restype=ctypes.c_ulong)
    for i in range(count):
        window = _send(windows, "objectAtIndex:", i, argtypes=(ctypes.c_ulong,))
        name = _send(window, "title")
        raw = _send(name, "UTF8String", restype=ctypes.c_char_p) if name else None
        if raw and raw.decode("utf-8", "replace") == title:
            return window
    return None


def round_window(title: str, radius: float = 14.0) -> bool:
    """Give the Tk window with this title rounded corners and a soft shadow, like the
    Windows 11 version. Returns False (and changes nothing) if it can't."""
    if not IS_MAC:
        return False
    try:
        window = _find_window(title)
        if not window:
            return False
        view = _send(window, "contentView")
        if not view:
            return False
        clear = _send(_runtime().objc_getClass(b"NSColor"), "clearColor")
        _send(window, "setOpaque:", False, restype=None, argtypes=(ctypes.c_bool,))
        _send(window, "setBackgroundColor:", clear, restype=None, argtypes=(ctypes.c_void_p,))
        _send(view, "setWantsLayer:", True, restype=None, argtypes=(ctypes.c_bool,))
        layer = _send(view, "layer")
        if not layer:
            return False
        _send(layer, "setCornerRadius:", radius, restype=None, argtypes=(ctypes.c_double,))
        _send(layer, "setMasksToBounds:", True, restype=None, argtypes=(ctypes.c_bool,))
        _send(window, "setHasShadow:", True, restype=None, argtypes=(ctypes.c_bool,))
        _send(window, "invalidateShadow", restype=None)
        return True
    except Exception:
        return False


def make_key(title: str) -> bool:
    """Make this window the one that receives typing (macOS' "key" window)."""
    if not IS_MAC:
        return False
    try:
        window = _find_window(title)
        if not window:
            return False
        _send(window, "makeKeyAndOrderFront:", None, restype=None, argtypes=(ctypes.c_void_p,))
        return bool(_send(window, "isKeyWindow", restype=ctypes.c_bool))
    except Exception:
        return False


def window_state(title: str) -> dict:
    """For diagnostics: can this window take typing, and does it have it right now?"""
    if not IS_MAC:
        return {}
    window = _find_window(title)
    if not window:
        return {"found": False}
    return {"found": True,
            "can_be_key": bool(_send(window, "canBecomeKeyWindow", restype=ctypes.c_bool)),
            "is_key": bool(_send(window, "isKeyWindow", restype=ctypes.c_bool)),
            "app_active": bool(_send(_ns_app(), "isActive", restype=ctypes.c_bool))}


# Style mask bits (NSWindowStyleMask): titled, closable, miniaturizable, resizable.
_TITLED_BITS = 1 | 2 | 4 | 8


def window_mask(title: str) -> int | None:
    if not IS_MAC:
        return None
    window = _find_window(title)
    if not window:
        return None
    return int(_send(window, "styleMask", restype=ctypes.c_ulong))


def remove_title_bar(title: str) -> bool:
    """Take the title bar (and its three buttons) off a window that Tk gave one. Newer Tk
    versions (9.0) keep the title bar for "plain" windows, which the summon bar must not have."""
    if not IS_MAC:
        return False
    try:
        window = _find_window(title)
        if not window:
            return False
        mask = int(_send(window, "styleMask", restype=ctypes.c_ulong))
        if not mask & 1:
            return True  # already borderless
        _send(window, "setStyleMask:", mask & ~_TITLED_BITS, restype=None,
              argtypes=(ctypes.c_ulong,))
        return not int(_send(window, "styleMask", restype=ctypes.c_ulong)) & 1
    except Exception:
        return False
