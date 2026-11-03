"""Finds which Mac-only touch makes the summon bar freeze (run by CI on macOS).

    python tests/mac_bisect.py round=1 activate=1 focus=1
"""
import os
import sys
import threading
import time

flags = dict(a.split("=") for a in sys.argv[1:])
os.environ["VECTOR_MAC_ROUND"] = flags.get("round", "1")
os.environ["VECTOR_MAC_ACTIVATE"] = flags.get("activate", "1")
sys.path.insert(0, os.path.dirname(__file__))

from test_app_ui import FakeAgent  # noqa: E402

from vector.app import VectorApp  # noqa: E402
from vector.config import Config  # noqa: E402


def stage(name):
    print(f"  stage: {name}", flush=True)


def watchdog():
    time.sleep(40)
    print(f"FROZE {flags}", flush=True)
    os._exit(3)


threading.Thread(target=watchdog, daemon=True).start()
app = VectorApp(Config(focus_mode=flags.get("focus", "1") == "1", check_updates=False),
                agent=FakeAgent(), enable_voice=False, enable_tray=False, enable_hotkey=False)


def pump(seconds):
    end = time.time() + seconds
    while time.time() < end:
        app.root.update()
        time.sleep(0.02)


stage("show")
app.bar.show()
pump(0.5)
stage("submit")
app.bar.entry.insert(0, "open calculator")
app.bar._submit()
for i in range(10):
    stage(f"pump {i}")
    pump(0.1)
stage(f"confirm card: {app.bar._confirm_cb is not None}")
app.bar._answer(True)
pump(1.0)
stage(f"reply: {app.bar.reply.cget('text')!r}")
print(f"OK {flags}", flush=True)
os._exit(0)
