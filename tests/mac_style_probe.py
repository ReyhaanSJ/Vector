"""Which way of making the summon bar borderless works with this Mac's Tk? (CI diagnostic)

Prints, for each approach: is there a title bar, can you type into the bar, and a picture.
"""
import base64
import io
import os
import sys
import time

approach = sys.argv[1]
os.environ["VECTOR_MAC_STYLE"] = {"plain": "plain:", "document": "document:noTitleBar",
                                  "plain+mask": "plain:", "simple": "simple:"}.get(approach, "plain:")
os.environ["VECTOR_MAC_NOMASK"] = "0" if approach.endswith("+mask") else "1"

from vector import macos  # noqa: E402
from vector.app import VectorApp, _windows_identity  # noqa: E402
from vector.config import Config  # noqa: E402
from vector.ui import MAC_TITLE  # noqa: E402


class FakeAgent:
    confirm = on_action = None

    def cancel(self):
        pass

    def ask(self, text):
        return text


_windows_identity()
app = VectorApp(Config(check_updates=False, focus_mode=False), agent=FakeAgent(), enable_voice=False,
                enable_tray=True, enable_hotkey=False)


def pump(seconds):
    end = time.time() + seconds
    while time.time() < end:
        app.root.update()
        time.sleep(0.02)


app.bar.show()
pump(1.0)
mask = macos.window_mask(MAC_TITLE)
import pyautogui  # noqa: E402

pyautogui.write("hello", interval=0.03)
pump(0.8)
from PIL import ImageGrab  # noqa: E402

w = app.bar.win
shot = ImageGrab.grab()
scale = shot.width / w.winfo_screenwidth()
box = [round(v * scale) for v in (w.winfo_rootx() - 40, w.winfo_rooty() - 60,
                                  w.winfo_rootx() + w.winfo_width() + 40,
                                  w.winfo_rooty() + w.winfo_height() + 40)]
img = shot.crop(box).convert("RGB")
img.thumbnail((900, 500))
buf = io.BytesIO()
img.save(buf, "JPEG", quality=70)
print(f"PROBE {approach} tk={app.root.tk.call('info', 'patchlevel')} mask={mask} "
      f"titled={bool(mask and mask & 1)} typed={app.bar.entry.get()!r} "
      f"geometry={w.winfo_rootx()},{w.winfo_rooty()} {w.winfo_width()}x{w.winfo_height()}")
print(f"IMAGE probe-{approach} {base64.b64encode(buf.getvalue()).decode()}")
os._exit(0)
