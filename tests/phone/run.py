"""Opens VECTOR Remote in a pretend iPhone (Playwright) against a pretend computer, then checks
that taps, scrolling, keys, asking and Allow all reached the computer. Run by CI:

    npm install playwright@1.63.0 && npx playwright install chromium
    python tests/phone/run.py [folder for screenshots]
"""
import io
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent), str(HERE.parents[1])]

from PIL import Image, ImageDraw  # noqa: E402
from test_remote import FakeBridge, FakeDesktop  # noqa: E402

from vector.remote import Remote  # noqa: E402

desk = Image.new("RGB", (1920, 1080), (40, 70, 110))
draw = ImageDraw.Draw(desk)
for i in range(0, 1920, 160):
    draw.rectangle((i + 40, 60, i + 120, 140), fill=(230, 237, 243))
bar = Image.open(HERE.parents[1] / "docs" / "images" / "summon-bar.png").convert("RGB")
bar.thumbnail((900, 600))
desk.paste(bar, ((1920 - bar.width) // 2, 220))
buf = io.BytesIO()
desk.save(buf, "JPEG", quality=70)
JPEG = buf.getvalue()


class Desk(FakeDesktop):
    def screenshot(self, max_width, quality):
        return JPEG, {"mouse_x": 0.25, "mouse_y": 0.5}


class Bridge(FakeBridge):
    def ask(self, text):
        super().ask(text)
        state = self.state

        def finish(ok):
            time.sleep(0.3)
            state.finished("Closed the calculator." if ok else "Okay, I left it open.")

        def run():
            state.started(text)
            time.sleep(0.3)
            state.step("Open app: calculator")
            time.sleep(0.2)
            state.ask("Needs your OK", "close_app(name='calculator')",
                      lambda ok: threading.Thread(target=finish, args=(ok,)).start())

        threading.Thread(target=run).start()


def main() -> int:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else HERE / "screenshots")
    out.mkdir(parents=True, exist_ok=True)
    server = Remote(Bridge(), "test-key-" + "x" * 34, port=0, host="127.0.0.1", desktop=Desk())
    assert server.start()
    try:
        url = f"http://127.0.0.1:{server.port}/?k={server.key}"
        result = subprocess.run(["node", str(HERE / "check.js"), url, str(out)], capture_output=True,
                                text=True, timeout=120, env=dict(os.environ))
        print(result.stdout, result.stderr)
        assert result.returncode == 0, "the phone check crashed"
        errors = json.loads(result.stdout.strip().splitlines()[-1])["errors"]
        assert errors == [], errors
        did = server.desktop.did
        assert did[0] == ("click", 480, 540, "left", 1), did     # the tap landed where the finger was
        assert any(d[0] == "scroll" and d[1] < 0 for d in did), did  # dragging up scrolls down
        assert ("keys", ["enter"]) in did, did
        assert server.bridge.asked == ["close calculator"]
        assert server.bridge.state.reply == "Closed the calculator."  # Allow was pressed
    finally:
        server.stop()
    print("VECTOR Remote works in a pretend iPhone. Screenshots:", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
