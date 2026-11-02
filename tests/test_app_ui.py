"""Drives the real summon bar with a fake brain. Needs a screen, so it runs on Windows CI."""

import os
import sys
import time

import pytest

pytestmark = pytest.mark.skipif(
    sys.platform != "win32" and not os.environ.get("VECTOR_UI_TESTS"),
    reason="needs a desktop session (Windows CI, or set VECTOR_UI_TESTS=1 with a display)")


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


_ROOT = None


def shared_root():
    """One window system for all UI tests (Windows can fail to start many in a row)."""
    global _ROOT
    import tkinter as tk

    if _ROOT is None:
        _ROOT = tk.Tk()
        _ROOT.withdraw()
    return _ROOT


def make_app(**kwargs):
    from vector.app import VectorApp
    from vector.config import Config

    config = kwargs.pop("config", None) or Config()
    return VectorApp(config, agent=kwargs.pop("agent", None) or FakeAgent(), enable_voice=False,
                     enable_tray=False, enable_hotkey=False, root=shared_root(), **kwargs)


def close(app, real_quit=None):
    (real_quit or app.quit)()
    pump(app, 0.2)


def pump(app, seconds):
    end = time.time() + seconds
    while time.time() < end:
        app.root.update()
        time.sleep(0.02)


def test_summon_bar_round_trip():

    app = make_app()
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
        close(app)


def test_escape_stops_everything():

    agent = FakeAgent()
    app = make_app(agent=agent)
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
        close(app)


def test_read_aloud_button(monkeypatch, tmp_path):

    monkeypatch.setenv("VECTOR_CONFIG", str(tmp_path / "config.toml"))
    app = make_app()
    spoken = []
    app._reader.say = lambda text: spoken.append(text)
    app._reader.stop = lambda: spoken.append("<stop>")
    try:
        app.bar.show()
        app.bar.entry.insert(0, "hello")
        app.bar._submit()
        pump(app, 0.8)
        app.bar._answer(True)
        pump(app, 0.8)
        assert spoken == []                                   # read-aloud is off by default
        app.bar.aloud_btn.event_generate("<Button-1>")       # clicked too late: reads it now
        pump(app, 0.5)
        assert spoken and spoken[0].startswith("Handled 'hello'")
        assert app.read_aloud and "read_aloud = true" in (tmp_path / "config.toml").read_text()
        spoken.clear()
        app.bar.entry.insert(0, "again")                     # clicked before: next reply is read
        app.bar._submit()
        pump(app, 0.8)
        app.bar._answer(False)
        pump(app, 0.8)
        assert spoken and spoken[-1].startswith("Handled 'again'")
        app.bar.aloud_btn.event_generate("<Button-1>")       # off again: stops reading
        pump(app, 0.3)
        assert not app.read_aloud and spoken[-1] == "<stop>"
    finally:
        close(app)


def test_focus_mode_blocks_the_screen_until_esc():

    app = make_app()
    try:
        app.bar.show()
        pump(app, 0.4)
        assert app.bar.overlay_visible() and app.bar.visible()
        app.bar.overlay.event_generate("<Button-1>", x=5, y=5)   # click outside the bar
        pump(app, 0.4)
        assert app.bar.visible() and app.bar.overlay_visible()  # nothing else is reachable
        app.bar.tuck()                                           # VECTOR using the screen
        pump(app, 0.2)
        assert not app.bar.overlay_visible()
        app.bar.show()
        pump(app, 0.3)
        app.bar.win.event_generate("<Escape>")
        pump(app, 0.4)
        assert not app.bar.visible() and not app.bar.overlay_visible()
        app.bar.show(focus=False)                                # notices / "Vector" don't dim
        pump(app, 0.3)
        assert app.bar.visible() and not app.bar.overlay_visible()
    finally:
        close(app)


def test_focus_mode_can_be_turned_off():
    from vector.config import Config

    app = make_app(config=Config(focus_mode=False))
    try:
        app.bar.show()
        pump(app, 0.3)
        assert app.bar.visible() and not app.bar.overlay_visible()
    finally:
        close(app)


def _app():
    return make_app()


def _type(app, text):
    app.bar.show()
    app.bar.entry.insert(0, text)
    app.bar._submit()
    pump(app, 0.4)


def test_uninstall_command_asks_twice_and_esc_never_deletes(monkeypatch):
    from vector import uninstall

    started = []
    monkeypatch.setattr(uninstall, "start", lambda keep_data: started.append(keep_data))
    app = _app()
    real_quit = app.quit
    app.quit = lambda: started.append("quit")
    try:
        _type(app, "/uninstall")                         # 1. Esc at "are you sure?" cancels
        assert app.bar.confirm_title.cget("text") == "Uninstall VECTOR?"
        app.bar.win.event_generate("<Escape>")
        pump(app, 0.3)
        assert started == []

        _type(app, "/uninstall")                         # 2. yes, then Esc at "keep data?"
        app.bar._answer(True)
        pump(app, 0.4)
        assert app.bar.confirm_title.cget("text") == "Keep your data?"
        app.bar.win.event_generate("<Escape>")
        pump(app, 0.3)
        assert started == []                             # nothing deleted, nothing uninstalled

        _type(app, "/uninstall")                         # 3. yes, keep my data
        app.bar._answer(True)
        pump(app, 0.4)
        app.bar._answer(True)
        pump(app, 1.2)
        assert started[0] is True and "quit" in started

        started.clear()
        _type(app, "/uninstall")                         # 4. yes, delete my data
        app.bar._answer(True)
        pump(app, 0.4)
        app.bar._answer(False)
        pump(app, 1.2)
        assert started[0] is False
    finally:
        close(app, real_quit)


def test_guide_and_help_commands(tmp_path, monkeypatch):
    from vector import guide

    monkeypatch.setattr(guide, "STATE_FILE", tmp_path / "state.json")
    app = _app()
    try:
        _type(app, "/help")
        assert "/uninstall" in app.bar.reply.cget("text")
        assert guide.should_show()
        _type(app, "/guide")
        g = app._guide
        assert g is not None and not app.bar.visible()
        for _ in range(len(guide.PAGES) - 1):            # every page draws without errors
            g.next()
            pump(app, 0.1)
            assert g.canvas.find_all()
        g.next()                                          # "Done"
        pump(app, 0.2)
        assert app._guide is None and not guide.should_show()
    finally:
        close(app)


def test_terminal_commands_work_in_the_bar(tmp_path, monkeypatch):
    monkeypatch.setenv("VECTOR_CONFIG", str(tmp_path / "config.toml"))
    app = _app()
    quits = []
    real_quit = app.quit
    app.quit = lambda: quits.append(True)
    app.agent.reset = lambda: quits.append("reset")
    app.agent.registry = __import__("vector.registry", fromlist=["REGISTRY"]).REGISTRY
    try:
        for command, expect in (("/help", "/quit"), ("/model", "AI MODEL"), ("/skills", "SKILLS"),
                                ("/reset", "FRESH START")):
            _type(app, command)
            shown = app.bar.reply_label.cget("text") + " " + app.bar.reply.cget("text")
            assert expect in shown, (command, shown)
            assert app.bar.entry.get() == ""             # never sent to the AI
        assert "reset" in quits
        _type(app, "/aloud")
        assert app.read_aloud
        _type(app, "/aloud")
        assert not app.read_aloud
        _type(app, "/quit")
        _type(app, "/exit")
        assert quits.count(True) == 2
    finally:
        close(app, real_quit)
