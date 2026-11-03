"""macOS parts. These run on the macOS CI machine (a real Mac with a screen)."""

import base64
import io
import os
import subprocess
import sys
import time

import pytest

from vector import macos
from vector.hotkey import parse_hotkey

on_mac = pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")


def test_shortcut_names_turn_into_mac_key_codes():
    assert macos.parse_combo("ctrl+shift+space") == (0x1000 | 0x0200, 49)
    assert macos.parse_combo("cmd+alt+v") == (0x0100 | 0x0800, 9)
    assert macos.parse_combo("esc") == (0, 53)
    with pytest.raises(ValueError):
        macos.parse_combo("hyper+space")
    # every key the Windows shortcut parser knows works on a Mac too
    from vector.hotkey import KEYS

    missing = [k for k in KEYS if k not in macos.KEY_CODES]
    assert not missing, missing
    parse_hotkey("ctrl+shift+space")


def test_nothing_mac_happens_elsewhere():
    if sys.platform == "darwin":
        pytest.skip("this is a Mac")
    assert macos.keychain_get("ANTHROPIC_API_KEY") == ""
    assert macos.load_keys() == []
    assert macos.set_app_name() is False
    assert macos.activate() is False
    assert macos.CarbonHotkey("ctrl+space", lambda: None).register()


def test_login_item_is_a_launch_agent(tmp_path, monkeypatch):
    from vector import startup

    plist = startup.mac_plist(app_bundle=tmp_path / "missing.app")
    assert "<key>RunAtLoad</key>" in plist and startup.MAC_LABEL in plist
    bundle = tmp_path / "VECTOR.app"
    bundle.mkdir()
    plist = startup.mac_plist(app_bundle=bundle)
    assert "<string>/usr/bin/open</string>" in plist and "--background" in plist
    import plistlib

    data = plistlib.loads(plist.encode())
    assert data["ProgramArguments"][-1] == "--background"


def test_retina_clicks_land_in_the_right_place():
    from vector.skills.screen import click_scale, to_screen

    # A 2880x1800 Retina screenshot, shrunk to 1366 wide; the mouse has 1440 positions.
    s = click_scale(1366, 2880, 1440)
    assert to_screen(683, 400, s) == (720, 422)   # the middle of the image = middle of the screen
    # Windows at 100%: screenshot and mouse match, so only the shrink counts.
    assert click_scale(1366, 1920, 1920) == pytest.approx(1366 / 1920)


@on_mac
def test_shortcut_registers_without_permission():
    hotkey = macos.CarbonHotkey("ctrl+alt+shift+f12", lambda: None)
    assert hotkey.register() is None
    hotkey.unregister()


@on_mac
def test_app_is_called_vector_in_the_menu_bar():
    assert macos.set_app_name("VECTOR")
    assert macos.app_name() == "VECTOR"


@on_mac
def test_keychain_round_trip():
    name = "VECTOR_TEST_KEY"
    if not macos.keychain_set(name, "s3cret value"):
        pytest.skip("this machine's Keychain is locked")
    try:
        assert macos.keychain_get(name) == "s3cret value"
    finally:
        macos.keychain_delete(name)
    assert macos.keychain_get(name) == ""


@on_mac
def test_speaking_stops_on_esc():
    import threading

    from vector.voice import Speaker

    speaker = Speaker()
    t = threading.Thread(target=speaker.say, args=("This is a long sentence. " * 20,))
    start = time.time()
    t.start()
    time.sleep(0.8)
    speaker.stop()
    t.join(5)
    assert not t.is_alive() and time.time() - start < 4
    assert speaker.enabled


@on_mac
def test_mac_apps_are_found():
    from vector.skills.apps import best_app_match, mac_apps

    apps = mac_apps()
    assert best_app_match("calculator", apps)
    assert best_app_match("textedit", apps)


# -- the real app on a real Mac screen ---------------------------------------------------------
class FakeAgent:
    def __init__(self):
        self.confirm = None
        self.on_action = None

    def cancel(self):
        pass

    def ask(self, text):
        self.on_action("open_app", {"name": "calculator"})
        allowed = self.confirm("close_app", {"name": "calculator"})
        return f"Handled '{text}', close allowed: {allowed}"


def _show_image(img, label):
    """Prints a small JPEG into the CI log (base64), so the Mac look can be checked."""
    img = img.convert("RGB")
    if img.width > 900:
        img = img.resize((900, round(img.height * 900 / img.width)))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=70)
    print(f"\nIMAGE {label} {base64.b64encode(buf.getvalue()).decode()}\n")


def _pump(root, seconds):
    end = time.time() + seconds
    while time.time() < end:
        root.update()
        time.sleep(0.02)


@on_mac
@pytest.mark.skipif(not os.environ.get("VECTOR_MAC_UI"), reason="set VECTOR_MAC_UI=1 on a Mac")
def test_summon_bar_on_a_mac():
    """Shows the bar, types into it like a person would, opens the menu and the shortcut."""
    from PIL import ImageGrab

    from vector.app import VectorApp, _windows_identity
    from vector.config import Config

    _windows_identity()
    report = {}
    app = VectorApp(Config(check_updates=False), agent=FakeAgent(), enable_voice=False,
                    enable_tray=True, enable_hotkey=True)
    try:
        report["tk"] = app.root.tk.call("info", "patchlevel")
        report["menu"] = app._mac_menu is not None
        report["hotkey"] = app.hotkey.error or "ok"
        app.bar.show()
        _pump(app.root, 1.0)
        report["rounded"] = app.bar._rounded
        report["visible"] = app.bar.visible()
        report["focus"] = str(app.root.focus_get())
        _show_image(ImageGrab.grab(), "screen-with-bar")
        try:
            import pyautogui

            pyautogui.write("hello", interval=0.03)
            _pump(app.root, 0.8)
            report["typed"] = app.bar.entry.get()
        except Exception as exc:  # no Accessibility permission for this runner
            report["typed"] = f"error: {exc}"
        app.bar.hide()
        _pump(app.root, 0.3)
        summoned = []
        app.summon = lambda: summoned.append(1)  # noqa: B023
        app.hotkey.callback = lambda: app.ui(app.summon)
        try:
            import pyautogui

            pyautogui.hotkey("ctrl", "shift", "space")
            _pump(app.root, 1.0)
        except Exception as exc:
            report["hotkey_press"] = f"error: {exc}"
        report["hotkey_fired"] = bool(summoned)
        app.bar.show()
        app.bar.entry.delete(0, "end")
        app.bar.entry.insert(0, "open calculator")
        app.bar._submit()
        _pump(app.root, 1.2)
        _show_image(ImageGrab.grab(), "bar-asking")
        app.bar._answer(True)
        _pump(app.root, 1.0)
        _show_image(ImageGrab.grab(), "bar-reply")
    finally:
        print("\nMAC UI REPORT", report)
        app.quit()
        _pump(app.root, 0.3)
    assert report["menu"] and report["visible"]
    assert report["hotkey"] == "ok"


@on_mac
@pytest.mark.skipif(not os.environ.get("VECTOR_MAC_UI"), reason="set VECTOR_MAC_UI=1 on a Mac")
def test_guide_pages_on_a_mac(tmp_path):
    import tkinter as tk

    from PIL import ImageGrab

    from vector import guide

    titles = [p[0] for p in guide.PAGES]
    assert "Find it in the menu bar" in titles and "Allow VECTOR on your Mac" in titles
    root = tk.Tk()
    root.withdraw()
    try:
        g = guide.GuideWindow(root)
        for _ in range(len(guide.PAGES)):
            _pump(root, 0.3)
            if g.index in (titles.index("Find it in the menu bar"),
                           titles.index("Allow VECTOR on your Mac"), 1):
                w = g.win
                x, y = w.winfo_rootx(), w.winfo_rooty()
                scale = ImageGrab.grab().width / w.winfo_screenwidth()
                box = [round(v * scale) for v in (x, y, x + w.winfo_width(), y + w.winfo_height())]
                _show_image(ImageGrab.grab(bbox=box), f"guide-{g.index}")
            g.next()
    finally:
        root.destroy()


@pytest.mark.skipif(sys.platform == "win32", reason="needs a real bash")
def test_installer_scripts_are_valid_bash():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    for script in ("install.sh", "Install VECTOR.command", "scripts/uninstall-macos.sh"):
        path = root / script
        assert path.exists(), script
        assert subprocess.run(["bash", "-n", str(path)]).returncode == 0, script
        assert b"\r\n" not in path.read_bytes(), f"{script} has Windows line endings"


@on_mac
def test_start_at_login_on_a_mac(tmp_path):
    from vector import startup

    path = startup.enable(app=True, folder=tmp_path)
    assert path.name == "com.vector.assistant.plist" and "--background" in path.read_text()
    assert startup.disable(folder=tmp_path) is True
    assert startup.disable(folder=tmp_path) is False
