"""On a real computer: start VECTOR Remote with the real screen and mouse, then fetch a live
screenshot and move the mouse through it, like a phone would. Run by CI's installer jobs."""
import io
import json
import sys
import urllib.request

from vector.remote import Remote, RemoteBridge


class App:  # just enough of VectorApp for the phone server
    def submit_remote(self, text):
        pass

    def ui(self, fn, *args):
        pass

    def stop_all(self):
        pass


server = Remote(RemoteBridge(App()), "ci-key-" + "x" * 36, port=0, host="127.0.0.1")
assert server.start(), server.error


def get(path, body=None):
    req = urllib.request.Request(f"http://127.0.0.1:{server.port}{path}",
                                 data=None if body is None else json.dumps(body).encode(),
                                 headers={"X-Vector-Key": server.key, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read(), resp.headers


hello = json.loads(get("/api/hello")[0])
print("computer:", hello)
jpeg, headers = get("/api/screen?w=1024&q=60")
from PIL import Image  # noqa: E402

img = Image.open(io.BytesIO(jpeg))
print("screenshot:", img.size, len(jpeg), "bytes, mouse at", headers["X-Mouse"])
assert img.format == "JPEG" and 320 <= img.size[0] <= 1024
assert json.loads(get("/api/move", {"x": 0.5, "y": 0.5})[0]) == {"ok": True}
import pyautogui  # noqa: E402

x, y = pyautogui.position()
w, h = pyautogui.size()
print("mouse moved to", (x, y), "of", (w, h))
assert abs(x - w // 2) <= 2 and abs(y - h // 2) <= 2
server.stop()
print("VECTOR Remote works with the real screen and mouse.")
sys.exit(0)
