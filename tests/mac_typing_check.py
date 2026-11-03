"""Checks, on a real Mac, that typing reaches the summon bar (run by CI on macOS).
macOS never gives the keyboard to some kinds of borderless window, so this guards against that.

    python tests/mac_typing_check.py focus=1 make_key=1
"""
import os
import sys
import threading
import time

flags = dict(a.split("=") for a in sys.argv[1:])
os.environ["VECTOR_MAC_MAKE_KEY"] = flags.get("make_key", "1")
if "style" in flags:
    os.environ["VECTOR_MAC_STYLE"] = flags["style"]
sys.path.insert(0, os.path.dirname(__file__))

from vector import macos  # noqa: E402
from vector.app import VectorApp, _windows_identity  # noqa: E402
from vector.config import Config  # noqa: E402
from vector.ui import MAC_TITLE  # noqa: E402


class FakeAgent:
    confirm = on_action = None

    def cancel(self):
        pass

    def ask(self, text):
        return f"Handled '{text}'"


def watchdog():
    time.sleep(40)
    print(f"FROZE {flags}", flush=True)
    os._exit(3)


threading.Thread(target=watchdog, daemon=True).start()
_windows_identity()
app = VectorApp(Config(focus_mode=flags.get("focus", "1") == "1", check_updates=False),
                agent=FakeAgent(), enable_voice=False, enable_tray=True, enable_hotkey=False)


def pump(seconds):
    end = time.time() + seconds
    while time.time() < end:
        app.root.update()
        time.sleep(0.02)


app.bar.show()
pump(0.8)
state = macos.window_state(MAC_TITLE)
import pyautogui  # noqa: E402

pyautogui.write("hello", interval=0.03)
pump(0.8)
typed = app.bar.entry.get()
app.bar.hide()
pump(0.3)
app.bar.show()                       # second time, like pressing the shortcut again
pump(0.8)
pyautogui.write("again", interval=0.03)
pump(0.8)
again = app.bar.entry.get()
print(f"RESULT {flags} typed={typed!r} second={again!r} window={state}", flush=True)
os._exit(0)
