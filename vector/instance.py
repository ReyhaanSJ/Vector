"""Keeps one VECTOR app running. Launching it again just pops up the summon bar."""

from __future__ import annotations

import socket
import threading
from collections.abc import Callable

HOST = "127.0.0.1"
PORT = 47615


def signal_running(message: str = "show", port: int = PORT) -> bool:
    """Tell an already-running VECTOR app something. True if one answered."""
    try:
        with socket.create_connection((HOST, port), timeout=0.5) as conn:
            conn.sendall(message.encode() + b"\n")
            return conn.recv(16).startswith(b"ok")
    except OSError:
        return False


class InstanceServer:
    """Listens for messages from later launches. Only this computer can connect."""

    def __init__(self, on_message: Callable[[str], None], port: int = PORT):
        self.on_message = on_message
        self.port = port
        self._sock: socket.socket | None = None

    def start(self) -> bool:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind((HOST, self.port))
        except OSError:
            sock.close()
            return False
        sock.listen(4)
        self._sock = sock
        threading.Thread(target=self._serve, name="vector-instance", daemon=True).start()
        return True

    def _serve(self) -> None:
        while self._sock is not None:
            try:
                conn, _ = self._sock.accept()
            except OSError:
                return
            with conn:
                try:
                    conn.settimeout(1.0)
                    message = conn.recv(64).decode(errors="ignore").strip()
                    conn.sendall(b"ok\n")
                except OSError:
                    continue
            if message in {"show", "quit", "voice"}:
                self.on_message(message)

    def stop(self) -> None:
        if self._sock is not None:
            sock, self._sock = self._sock, None
            try:
                sock.shutdown(socket.SHUT_RDWR)  # wakes the thread blocked in accept()
            except OSError:
                pass
            sock.close()
