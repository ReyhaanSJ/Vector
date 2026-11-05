"""VECTOR Remote (the phone app): pairing, safety checks, and every phone action."""

import io
import json
import urllib.error
import urllib.request

import pytest

from vector import remote
from vector.remote import Remote, RemoteState, is_private, load_key


class FakeDesktop:
    def __init__(self):
        self.did = []

    def size(self):
        return (1920, 1080)

    def screenshot(self, max_width, quality):
        self.did.append(("screenshot", max_width, quality))
        return b"\xff\xd8fake-jpeg", {"mouse_x": 0.5, "mouse_y": 0.25}

    def click(self, x, y, button, clicks):
        self.did.append(("click", x, y, button, clicks))

    def move(self, x, y):
        self.did.append(("move", x, y))

    def scroll(self, steps):
        self.did.append(("scroll", steps))

    def type(self, text):
        self.did.append(("type", text))

    def keys(self, combo):
        self.did.append(("keys", combo))


class FakeBridge:
    def __init__(self):
        self.state = RemoteState()
        self.asked = []
        self.stopped = 0

    def ask(self, text):
        self.asked.append(text)

    def stop(self):
        self.stopped += 1


@pytest.fixture
def server():
    connected = []
    srv = Remote(FakeBridge(), "k" * 43, port=0, host="127.0.0.1", desktop=FakeDesktop(),
                 on_connect=connected.append)
    assert srv.start()
    srv.connected = connected
    yield srv
    srv.stop()


def call(srv, path, body=None, key=None):
    """(status, headers, parsed body) for a request to the phone server."""
    req = urllib.request.Request(f"http://127.0.0.1:{srv.port}{path}",
                                 data=None if body is None else json.dumps(body).encode(),
                                 method="GET" if body is None else "POST")
    if key is not False:
        req.add_header("X-Vector-Key", key or srv.key)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            status, headers, raw = resp.status, resp.headers, resp.read()
    except urllib.error.HTTPError as exc:
        status, headers, raw = exc.code, exc.headers, exc.read()
    kind = headers.get("Content-Type", "")
    return status, headers, json.loads(raw) if "json" in kind else raw


def test_key_is_made_once_and_can_be_reset(tmp_path):
    path = tmp_path / "remote.json"
    first = load_key(path)
    assert len(first) >= 40 and load_key(path) == first
    assert load_key(path, reset=True) != first


def test_only_your_own_network_is_allowed():
    for ok in ("192.168.1.20", "10.0.0.5", "172.16.3.4", "127.0.0.1", "100.101.102.103", "fe80::1",
               "::ffff:192.168.1.9"):
        assert is_private(ok), ok
    for bad in ("8.8.8.8", "1.2.3.4", "2001:4860::1", "not an ip"):
        assert not is_private(bad), bad


def test_the_page_opens_but_nothing_works_without_the_key(server):
    status, headers, page = call(server, "/", key=False)
    assert status == 200 and b"VECTOR Remote" in page
    assert "default-src 'self'" in headers["Content-Security-Policy"]
    assert call(server, "/icon.png", key=False)[0] == 200
    for path in ("/api/hello", "/api/state", "/api/screen"):
        assert call(server, path, key=False)[0] == 401
    assert call(server, "/api/click", {"x": 0.5, "y": 0.5}, key="wrong")[0] == 401
    assert server.desktop.did == []                       # no click got through
    assert server.connected == []


def test_guessing_keys_gets_you_locked_out(server):
    for _ in range(remote.LOCKOUT_ATTEMPTS):
        call(server, "/api/state", key="guess")
    assert call(server, "/api/state")[0] == 429           # even the right key, for a while


def test_paired_phone_sees_the_screen(server):
    status, _, hello = call(server, "/api/hello")
    assert status == 200 and hello["screen"] == {"w": 1920, "h": 1080}
    assert server.connected == ["127.0.0.1"]              # the computer is told a phone connected
    status, headers, jpeg = call(server, "/api/screen?w=99999&q=5")
    assert status == 200 and jpeg.startswith(b"\xff\xd8") and headers["X-Mouse"] == "0.5,0.25"
    assert server.desktop.did[-1] == ("screenshot", remote.MAX_SCREEN_WIDTH, 30)  # limits kept


def test_taps_land_where_the_finger_was(server):
    call(server, "/api/click", {"x": 0.5, "y": 0.5})
    call(server, "/api/click", {"x": 1.2, "y": -1, "button": "right"})   # off the edge: clamped
    call(server, "/api/scroll", {"steps": -500})
    call(server, "/api/type", {"text": "héllo"})
    call(server, "/api/keys", {"keys": ["ctrl", "c"]})
    assert server.desktop.did == [("click", 960, 540, "left", 1), ("click", 1919, 0, "right", 1),
                                  ("scroll", -30), ("type", "héllo"), ("keys", ["ctrl", "c"])]
    assert call(server, "/api/keys", {"keys": ["rm -rf"]})[0] == 400
    assert call(server, "/api/click", {"x": 0.5, "y": 0.5, "button": "evil"})[0] == 400
    assert call(server, "/api/click", {})[0] == 400


def test_asking_vector_from_the_phone(server):
    bridge = server.bridge
    assert call(server, "/api/ask", {"text": "  "})[0] == 400
    assert call(server, "/api/ask", {"text": "open spotify"})[2] == {"ok": True}
    assert bridge.asked == ["open spotify"]

    state = bridge.state
    state.started("open spotify")
    assert call(server, "/api/ask", {"text": "another"})[0] == 400        # one thing at a time
    state.step("Open app: spotify")
    answers = []
    state.ask("Needs your OK", "close_app(name='spotify')", answers.append)
    shown = call(server, "/api/state")[2]
    assert shown["busy"] and shown["steps"] == ["Open app: spotify"]
    assert shown["confirm"]["detail"] == "close_app(name='spotify')"
    assert call(server, "/api/answer", {"allow": True})[2] == {"ok": True}
    assert answers == [True]
    assert call(server, "/api/answer", {"allow": False})[2] == {"ok": False}  # nothing waiting
    call(server, "/api/stop", {})
    assert bridge.stopped == 1
    state.finished("Opened Spotify.")
    done = call(server, "/api/state")[2]
    assert not done["busy"] and done["reply"] == "Opened Spotify." and done["seq"] > shown["seq"]


def test_home_screen_link_keeps_the_key(server):
    good = call(server, f"/manifest.json?k={server.key}", key=False)[2]
    assert good["start_url"] == f"/?k={server.key}" and good["display"] == "standalone"
    assert call(server, "/manifest.json?k=wrong", key=False)[2]["start_url"] == "/"


def test_pairing_link_and_qr_code():
    url = remote.phone_url("abc", host="192.168.1.5")
    assert url == f"http://192.168.1.5:{remote.PORT}/?k=abc"
    png = remote.qr_png(url)
    assert png.startswith(b"\x89PNG")
    image = pytest.importorskip("PIL.Image")
    assert image.open(io.BytesIO(png)).size[0] > 100
    assert "█" in remote.qr_text(url) or "▀" in remote.qr_text(url)


def test_second_server_on_the_same_port_says_why(server):
    other = Remote(FakeBridge(), "x" * 43, port=server.port, host="127.0.0.1", desktop=FakeDesktop())
    assert not other.start() and "already in use" in other.error


def test_tailscale_address_is_found(monkeypatch):
    import socket
    from types import SimpleNamespace as NS

    import psutil

    fake = {"Wi-Fi": [NS(family=socket.AF_INET, address="192.168.1.4")],
            "Tailscale": [NS(family=socket.AF_INET, address="100.88.1.2")]}
    monkeypatch.setattr(psutil, "net_if_addrs", lambda: fake)
    assert remote.tailscale_address() == "100.88.1.2"
    monkeypatch.setattr(psutil, "net_if_addrs", lambda: {"Wi-Fi": fake["Wi-Fi"]})
    assert remote.tailscale_address() is None
