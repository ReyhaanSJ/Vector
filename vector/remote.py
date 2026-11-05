"""VECTOR Remote: use VECTOR and see your screen from your phone.

VECTOR serves a small web app on your home network. Scan the QR code it shows (type /phone in
the summon bar) with your iPhone or Android phone, then "Add to Home Screen" and it opens like
an app: a live view of the screen (tap to click, drag to scroll), a keyboard, and a chat box to
ask VECTOR things, with Allow / Deny for risky actions and a Stop button.

Safety:
- Off until you turn it on (/phone). Turn it off any time (/phone off).
- Only phones that scanned the QR code shown on this computer get in: each link carries a
  long random key, checked on every request. /phone reset makes old links stop working.
- Only devices on your own network (or your Tailscale network) can connect; anything coming
  from the internet is refused. Too many wrong keys and that device is locked out for a while.
- The page isn't encrypted (plain http on your Wi-Fi), so use it on networks you trust.
"""

from __future__ import annotations

import hmac
import io
import ipaddress
import json
import logging
import os
import platform
import secrets
import socket
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from vector import __version__
from vector.config import HOME_DIR

log = logging.getLogger("vector.remote")

PORT = 47617
ASSETS = Path(__file__).parent / "assets"
STATE_FILE = HOME_DIR / "remote.json"
MAX_SCREEN_WIDTH = 1600
LOCKOUT_ATTEMPTS = 20         # wrong keys from one address...
LOCKOUT_SECONDS = 300         # ...lock it out for this long


# -- the pairing key -------------------------------------------------------------------------
def load_key(path: Path | None = None, reset: bool = False) -> str:
    """The secret every phone link carries. Made once, kept in ~/.vector/remote.json."""
    path = path or STATE_FILE
    data = {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    if reset or not isinstance(data.get("key"), str) or len(data["key"]) < 32:
        data["key"] = secrets.token_urlsafe(32)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            if os.name != "nt":
                path.chmod(0o600)
        except OSError:
            log.exception("couldn't save the phone key")
    return data["key"]


def local_address() -> str:
    """This computer's address on the home network (what the phone connects to)."""
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("192.168.0.1", 9))  # no packet is sent; it just picks the right network
        return probe.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        probe.close()


def tailscale_address() -> str | None:
    """This computer's Tailscale address (100.x.y.z), if Tailscale is installed and on."""
    try:
        import psutil

        network = ipaddress.ip_network("100.64.0.0/10")
        for addresses in psutil.net_if_addrs().values():
            for a in addresses:
                if a.family == socket.AF_INET and ipaddress.ip_address(a.address) in network:
                    return a.address
    except Exception:
        pass
    return None


def is_private(address: str) -> bool:
    """Home network, this computer, or Tailscale (100.64.0.0/10). Not the open internet."""
    try:
        ip = ipaddress.ip_address(address.split("%")[0])
    except ValueError:
        return False
    if getattr(ip, "ipv4_mapped", None):
        ip = ip.ipv4_mapped
    tailscale = ipaddress.ip_network("100.64.0.0/10")
    return ip.is_private or ip.is_loopback or ip.is_link_local or (ip.version == 4 and ip in tailscale)


def phone_url(key: str, host: str | None = None, port: int = PORT) -> str:
    return f"http://{host or local_address()}:{port}/?k={key}"


def qr_png(text: str, scale: int = 8) -> bytes:
    """A QR code (PNG) for the pairing link."""
    import segno

    buf = io.BytesIO()
    segno.make(text, error="m").save(buf, kind="png", scale=scale, border=2,
                                     dark="#0B1016", light="#FFFFFF")
    return buf.getvalue()


def qr_text(text: str) -> str:
    """The same QR code drawn with characters, for the terminal."""
    import segno

    buf = io.StringIO()
    segno.make(text, error="m").terminal(out=buf, compact=True)
    return buf.getvalue()


# -- what the phone sees -------------------------------------------------------------------------
@dataclass
class RemoteState:
    """VECTOR's current request, as the phone shows it. The app updates it; the phone reads it."""
    busy: bool = False
    request: str = ""
    steps: list[str] = field(default_factory=list)
    reply: str = ""
    error: bool = False
    confirm: dict | None = None
    model: str = ""
    seq: int = 0                       # bumps on every change, so the phone knows to redraw
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _answer: Callable[[bool], None] | None = field(default=None, repr=False)

    def _bump(self) -> None:
        self.seq += 1

    def started(self, text: str) -> None:
        with self._lock:
            self.busy, self.request, self.steps, self.reply, self.error = True, text, [], "", False
            self._bump()

    def step(self, description: str) -> None:
        with self._lock:
            self.steps.append(description)
            self._bump()

    def finished(self, reply: str | None, error: bool = False) -> None:
        with self._lock:
            self.busy = False
            self.reply = "Stopped." if reply is None else reply
            self.error = error
            self.confirm, self._answer = None, None
            self._bump()

    def ask(self, title: str, detail: str, answer: Callable[[bool], None]) -> None:
        with self._lock:
            self.confirm, self._answer = {"title": title, "detail": detail}, answer
            self._bump()

    def asked_done(self) -> None:
        with self._lock:
            if self.confirm is not None:
                self.confirm, self._answer = None, None
                self._bump()

    def answer(self, allowed: bool) -> bool:
        with self._lock:
            answer, self._answer, self.confirm = self._answer, None, None
            self._bump()
        if answer is None:
            return False
        answer(allowed)
        return True

    def snapshot(self) -> dict:
        with self._lock:
            return {"busy": self.busy, "request": self.request, "steps": list(self.steps),
                    "reply": self.reply, "error": self.error, "confirm": self.confirm,
                    "model": self.model, "seq": self.seq}


# -- mouse, keyboard and screen -------------------------------------------------------------------
class Desktop:
    """The real screen, mouse and keyboard (tests swap in a fake)."""

    def __init__(self):
        import pyautogui

        pyautogui.FAILSAFE = False  # the phone can tap right into a corner; that's not an emergency
        pyautogui.PAUSE = 0.02
        self.gui = pyautogui

    def size(self) -> tuple[int, int]:
        w, h = self.gui.size()
        return int(w), int(h)

    def screenshot(self, max_width: int, quality: int) -> tuple[bytes, dict]:
        from PIL import Image, ImageGrab

        try:
            img = ImageGrab.grab()
        except Exception:
            img = self.gui.screenshot()
        if img.width > max_width:
            img = img.resize((max_width, round(img.height * max_width / img.width)), Image.BILINEAR)
        buf = io.BytesIO()
        img.convert("RGB").save(buf, "JPEG", quality=quality)
        mx, my = self.gui.position()
        w, h = self.size()
        return buf.getvalue(), {"mouse_x": round(mx / w, 4), "mouse_y": round(my / h, 4)}

    def click(self, x: int, y: int, button: str, clicks: int) -> None:
        self.gui.click(x, y, clicks=clicks, interval=0.08, button=button)

    def move(self, x: int, y: int) -> None:
        self.gui.moveTo(x, y)

    def scroll(self, steps: int) -> None:
        import sys

        self.gui.scroll(steps * (120 if sys.platform == "win32" else 1))

    def type(self, text: str) -> None:
        if text.isascii():
            self.gui.write(text, interval=0.01)
            return
        import sys

        import pyperclip

        previous = pyperclip.paste()  # letters pyautogui can't type: paste them instead
        pyperclip.copy(text)
        self.gui.hotkey("command" if sys.platform == "darwin" else "ctrl", "v")
        time.sleep(0.2)
        pyperclip.copy(previous)

    def keys(self, combo: list[str]) -> None:
        self.gui.hotkey(*combo)


ALLOWED_KEYS = {"enter", "esc", "backspace", "tab", "space", "up", "down", "left", "right",
                "home", "end", "pageup", "pagedown", "delete", "ctrl", "alt", "shift", "command",
                "win", "option", "volumeup", "volumedown", "volumemute", "playpause", "nexttrack",
                "prevtrack"} | {chr(c) for c in range(ord("a"), ord("z") + 1)} | set("0123456789") \
    | {f"f{i}" for i in range(1, 13)}


# -- the web server -------------------------------------------------------------------------------
class Remote:
    """Serves the phone app. `app` is anything with ask(text), stop(), answer(bool)
    (VectorApp provides them through RemoteBridge)."""

    def __init__(self, bridge, key: str, port: int = PORT, host: str = "0.0.0.0",
                 desktop=None, on_connect: Callable[[str], None] | None = None):
        self.bridge = bridge
        self.key = key
        self.port = port
        self.host = host
        self._desktop = desktop
        self.on_connect = on_connect
        self.server: ThreadingHTTPServer | None = None
        self._failures: dict[str, list[float]] = {}
        self._seen: set[str] = set()
        self.error: str | None = None

    @property
    def desktop(self):
        if self._desktop is None:
            self._desktop = Desktop()
        return self._desktop

    @property
    def running(self) -> bool:
        return self.server is not None

    def url(self, host: str | None = None) -> str:
        return phone_url(self.key, host, self.port)

    def start(self) -> bool:
        if self.server is not None:
            return True
        remote = self

        class Handler(_Handler):
            owner = remote

        try:
            self.server = ThreadingHTTPServer((self.host, self.port), Handler)
        except OSError as exc:
            self.error = (f"Port {self.port} is already in use, so the phone remote can't start. "
                          "Is another VECTOR running?" if getattr(exc, "errno", 0) in (48, 98, 10048)
                          else f"The phone remote couldn't start: {exc}")
            return False
        self.server.daemon_threads = True
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, name="vector-remote", daemon=True).start()
        self.error = None
        return True

    def stop(self) -> None:
        server, self.server = self.server, None
        if server is not None:
            server.shutdown()
            server.server_close()

    # -- checks shared by every request --
    def locked_out(self, address: str) -> bool:
        now = time.monotonic()
        recent = [t for t in self._failures.get(address, []) if now - t < LOCKOUT_SECONDS]
        self._failures[address] = recent
        return len(recent) >= LOCKOUT_ATTEMPTS

    def check_key(self, address: str, given: str) -> bool:
        if hmac.compare_digest(given.encode(), self.key.encode()):
            if address not in self._seen:
                self._seen.add(address)
                if self.on_connect:
                    try:
                        self.on_connect(address)
                    except Exception:
                        log.exception("on_connect failed")
            return True
        self._failures.setdefault(address, []).append(time.monotonic())
        return False


class _Handler(BaseHTTPRequestHandler):
    owner: Remote
    protocol_version = "HTTP/1.1"  # keep the connection open between frames: a smoother picture
    timeout = 30
    server_version = "VECTOR"
    sys_version = ""

    def log_message(self, fmt, *args):  # quiet: never write keys (in URLs) to the logs
        pass

    # -- responses --
    def _send(self, status: int, body: bytes, kind: str, headers: dict | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, data, status: int = 200) -> None:
        self._send(status, json.dumps(data).encode(), "application/json")

    def _allowed(self, need_key: bool) -> bool:
        address = self.client_address[0]
        if not is_private(address):
            self._send(403, b"VECTOR only answers devices on your own network.", "text/plain")
            return False
        if self.owner.locked_out(address):
            self._send(429, b"Too many wrong keys. Wait a few minutes, then scan the QR code again.",
                       "text/plain")
            return False
        if not need_key:
            return True
        query = parse_qs(urlparse(self.path).query)
        given = self.headers.get("X-Vector-Key") or (query.get("k") or [""])[0]
        if not self.owner.check_key(address, given):
            self._json({"error": "This link isn't paired. Type /phone on your computer and scan "
                                 "the new QR code."}, 401)
            return False
        return True

    def _body(self) -> dict:
        try:
            length = min(int(self.headers.get("Content-Length") or 0), 64_000)
            data = json.loads(self.rfile.read(length) or b"{}")
            return data if isinstance(data, dict) else {}
        except (ValueError, OSError):
            return {}

    # -- routes --
    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            if self._allowed(need_key=False):
                page = (ASSETS / "phone.html").read_bytes()
                self._send(200, page, "text/html; charset=utf-8",
                           {"Content-Security-Policy": "default-src 'self'; img-src 'self' blob: data:; "
                                                       "style-src 'self' 'unsafe-inline'; "
                                                       "script-src 'self' 'unsafe-inline'; "
                                                       "connect-src 'self'; frame-ancestors 'none'"})
            return
        if path == "/icon.png":
            if self._allowed(need_key=False):
                self._send(200, (ASSETS / "phone-icon.png").read_bytes(), "image/png",
                           {"Cache-Control": "max-age=86400"})
            return
        if path == "/manifest.json":
            if self._allowed(need_key=False):
                key = (parse_qs(urlparse(self.path).query).get("k") or [""])[0]
                start = f"/?k={key}" if hmac.compare_digest(key.encode(), self.owner.key.encode()) else "/"
                self._json({"name": "VECTOR Remote", "short_name": "VECTOR", "start_url": start,
                            "display": "standalone", "background_color": "#0B1016",
                            "theme_color": "#0B1016",
                            "icons": [{"src": "/icon.png", "sizes": "512x512", "type": "image/png"}]})
            return
        if not self._allowed(need_key=True):
            return
        if path == "/api/hello":
            w, h = self.owner.desktop.size()
            self._json({"name": platform.node() or "your computer", "version": __version__,
                        "screen": {"w": w, "h": h}, "system": platform.system()})
        elif path == "/api/state":
            self._json(self.owner.bridge.state.snapshot())
        elif path == "/api/screen":
            query = parse_qs(urlparse(self.path).query)
            try:
                width = max(320, min(int((query.get("w") or ["1280"])[0]), MAX_SCREEN_WIDTH))
                quality = max(30, min(int((query.get("q") or ["60"])[0]), 85))
            except ValueError:
                width, quality = 1280, 60
            try:
                jpeg, info = self.owner.desktop.screenshot(width, quality)
            except Exception as exc:
                log.exception("screenshot failed")
                self._json({"error": f"Couldn't capture the screen: {exc}"}, 500)
                return
            self._send(200, jpeg, "image/jpeg", {"X-Mouse": f"{info['mouse_x']},{info['mouse_y']}"})
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path
        if not self._allowed(need_key=True):
            return
        data = self._body()
        try:
            self._json(self._act(path, data))
        except _BadRequest as exc:
            self._json({"error": str(exc)}, 400)
        except Exception as exc:
            log.exception("phone action failed")
            self._json({"error": str(exc)}, 500)

    def _act(self, path: str, data: dict) -> dict:
        owner, bridge = self.owner, self.owner.bridge
        if path == "/api/ask":
            text = str(data.get("text", "")).strip()[:2000]
            if not text:
                raise _BadRequest("Type something to ask VECTOR.")
            if bridge.state.busy:
                raise _BadRequest("VECTOR is still busy. Stop it first, or wait.")
            bridge.ask(text)
            return {"ok": True}
        if path == "/api/answer":
            return {"ok": bridge.state.answer(bool(data.get("allow")))}
        if path == "/api/stop":
            bridge.stop()
            return {"ok": True}
        desktop = owner.desktop
        if path in ("/api/click", "/api/move"):
            x, y = _point(data, desktop.size())
            if path == "/api/move":
                desktop.move(x, y)
            else:
                button = data.get("button", "left")
                if button not in ("left", "right", "middle"):
                    raise _BadRequest("button must be left, right or middle")
                desktop.click(x, y, button, 2 if data.get("double") else 1)
            return {"ok": True}
        if path == "/api/scroll":
            steps = int(data.get("steps", 0))
            desktop.scroll(max(-30, min(steps, 30)))
            return {"ok": True}
        if path == "/api/type":
            text = str(data.get("text", ""))[:2000]
            if text:
                desktop.type(text)
            return {"ok": True}
        if path == "/api/keys":
            combo = [str(k).lower() for k in data.get("keys", [])][:4]
            if not combo or any(k not in ALLOWED_KEYS for k in combo):
                raise _BadRequest(f"Unknown key in {combo}")
            desktop.keys(combo)
            return {"ok": True}
        raise _BadRequest("unknown action")


class _BadRequest(Exception):
    pass


def _point(data: dict, size: tuple[int, int]) -> tuple[int, int]:
    """The phone sends where it tapped as 0..1 of the picture; turn that into a screen point."""
    try:
        fx, fy = float(data["x"]), float(data["y"])
    except (KeyError, TypeError, ValueError) as exc:
        raise _BadRequest("x and y (0 to 1) are needed") from exc
    w, h = size
    fx, fy = max(0.0, min(fx, 1.0)), max(0.0, min(fy, 1.0))
    return min(round(fx * w), w - 1), min(round(fy * h), h - 1)


class RemoteBridge:
    """Connects the phone to a running VectorApp (all calls come from server threads)."""

    def __init__(self, app):
        self.app = app
        self.state = RemoteState()

    def ask(self, text: str) -> None:
        self.app.submit_remote(text)

    def stop(self) -> None:
        self.app.ui(self.app.stop_all)
