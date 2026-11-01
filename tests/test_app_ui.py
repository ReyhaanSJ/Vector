"""Drives the real summon bar with a fake brain. Needs a screen, so it runs on Windows CI."""

import sys
import time

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="needs a desktop session")


class FakeAgent:
    def __init__(self):
        self.confirm = None
        self.on_action = None

    def ask(self, text):
        self.on_action("open_app", {"name": "calculator"})
        allowed = self.confirm("close_app", {"name": "calculator"})
        return f"Handled '{text}', close allowed: {allowed}"


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
        assert app.bar.steps.winfo_children()           # the step was listed
        app.bar._answer(True)
        pump(app, 1.0)
        assert "close allowed: True" in app.bar.reply.cget("text")
        assert app.bar.busy is False
        app.bar.hide()
        pump(app, 0.2)
        assert not app.bar.visible()
    finally:
        app.quit()
        pump(app, 0.2)
