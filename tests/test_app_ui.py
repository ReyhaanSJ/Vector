"""Drives the real summon bar with a fake brain. Needs a screen, so it runs on Windows CI."""

import sys
import time

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="needs a desktop session")


class FakeAgent:
    def __init__(self):
        self.confirm = None
        self.on_action = None
        self.stopped = False

    def cancel(self):
        self.stopped = True

    def ask(self, text):
        from vector.brain import Cancelled

        self.stopped = False
        self.on_action("open_app", {"name": "calculator"})
        allowed = self.confirm("close_app", {"name": "calculator"})
        if self.stopped:
            raise Cancelled()
        return f"Handled '{text}', close allowed: {allowed}"


def _screenshot(app, name):
    """Saved for CI to upload, so the real Windows look can be checked."""
    import os

    folder = os.environ.get("VECTOR_SCREENSHOTS")
    if not folder:
        return
    from PIL import ImageGrab

    w = app.bar.win
    w.update()
    x, y = w.winfo_rootx(), w.winfo_rooty()
    os.makedirs(folder, exist_ok=True)
    ImageGrab.grab(bbox=(x - 24, y - 24, x + w.winfo_width() + 24, y + w.winfo_height() + 24)).save(
        os.path.join(folder, name))


def pump(app, seconds):
    end = time.time() + seconds
    while time.time() < end:
        app.root.update()
        time.sleep(0.02)


def test_summon_bar_round_trip():
    from vector.app import VectorApp
    from vector.config import Config

    app = VectorApp(Config(), agent=FakeAgent(), enable_voice=False, enable_tray=False,
                    enable_hotkey=False)
    try:
        app.bar.show()
        pump(app, 0.3)
        assert app.bar.visible()
        app.bar.entry.insert(0, "open calculator")
        app.bar._submit()
        pump(app, 1.0)
        assert app.bar._confirm_cb is not None          # Allow / Deny card is showing
        assert app.bar.confirm.winfo_ismapped()
        app.root.update()
        _screenshot(app, "summon-bar-confirm.png")
        assert app.bar.steps.winfo_children()           # the step was listed
        app.bar._answer(True)
        pump(app, 1.0)
        assert "close allowed: True" in app.bar.reply.cget("text")
        _screenshot(app, "summon-bar-done.png")
        assert app.bar.busy is False
        app.bar.hide()
        pump(app, 0.2)
        assert not app.bar.visible()
    finally:
        app.quit()
        pump(app, 0.2)


def test_escape_stops_everything():
    from vector.app import VectorApp
    from vector.config import Config

    agent = FakeAgent()
    app = VectorApp(Config(), agent=agent, enable_voice=False, enable_tray=False, enable_hotkey=False)
    try:
        app.bar.show()
        app.bar.entry.insert(0, "close calculator")
        app.bar._submit()
        pump(app, 1.0)
        assert app.bar._confirm_cb is not None   # waiting for Allow / Deny
        app.bar.win.event_generate("<Escape>")    # the user presses Esc
        pump(app, 1.0)
        assert agent.stopped
        assert app.bar.busy is False and not app.bar.visible()
        assert app.bar.reply.cget("text") == "Stopped."
        assert app._esc is None                   # Esc is given back to other apps when idle
    finally:
        app.quit()
        pump(app, 0.2)
