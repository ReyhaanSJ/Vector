"""The window that pairs a phone with VECTOR: a QR code to scan, and three short steps."""

from __future__ import annotations

import base64
import sys
from collections.abc import Callable

from vector.ui import (
    ACCENT,
    ASSETS,
    BG,
    BORDER,
    MUTED,
    PANEL,
    TEXT,
    Pill,
    draw_mark,
    fsize,
    pick_font,
)

STEPS = [
    ("Scan it", "Open your phone's Camera, point it at this code and tap the link. "
                "The phone must be on the same Wi-Fi as this computer."
                + (" If Windows asks about the firewall, click Allow." if sys.platform == "win32" else
                   " If macOS asks to accept incoming connections, click Allow."
                   if sys.platform == "darwin" else "")),
    ("Keep it", "iPhone: tap Share, then Add to Home Screen. Android: menu, then Add to "
                "Home screen. VECTOR Remote now opens like an app."),
    ("Use it", "See this screen live. Tap to click, drag to scroll, type, or ask VECTOR. "
               "Stop ends anything at once."),
]


class PairingWindow:
    def __init__(self, master, url: str, reset: bool = False, on_off: Callable[[], None] | None = None,
                 on_close: Callable[[], None] | None = None):
        import tkinter as tk

        from vector.remote import qr_png

        self.on_off = on_off
        self.on_close = on_close
        win = self.win = tk.Toplevel(master)
        win.title("VECTOR Remote")
        win.configure(bg=BG)
        win.resizable(False, False)
        win.attributes("-topmost", True)
        win.protocol("WM_DELETE_WINDOW", self.close)
        win.bind("<Escape>", lambda e: self.close())
        try:
            if sys.platform == "win32" and (ASSETS / "icon.ico").exists():
                win.iconbitmap(str(ASSETS / "icon.ico"))
        except Exception:
            pass

        ui = pick_font(win, ["Segoe UI Variable Text", "Segoe UI", "SF Pro Text", ".AppleSystemUIFont",
                             "Helvetica Neue", "Inter"], "Helvetica")
        mono = pick_font(win, ["Cascadia Mono", "Consolas", "SF Mono", "Menlo"], "Courier")
        body = tk.Frame(win, bg=BG, padx=28, pady=24)
        body.pack(fill="both", expand=True)

        head = tk.Frame(body, bg=BG)
        head.pack(fill="x")
        mark = tk.Canvas(head, width=28, height=28, bg=BG, highlightthickness=0)
        draw_mark(mark, 2, 2, 24)
        mark.pack(side="left", padx=(0, 12))
        tk.Label(head, text="Use VECTOR from your phone", bg=BG, fg=TEXT,
                 font=(ui, fsize(17), "bold")).pack(side="left")
        if reset:
            tk.Label(body, text="New code made: phones paired before can't connect any more.",
                     bg=BG, fg=ACCENT, font=(ui, fsize(10))).pack(anchor="w", pady=(10, 0))

        row = tk.Frame(body, bg=BG)
        row.pack(fill="x", pady=(18, 8))
        card = tk.Frame(row, bg="#FFFFFF", padx=10, pady=10)
        card.pack(side="left", anchor="n")
        self._qr = tk.PhotoImage(data=base64.b64encode(qr_png(url, scale=6)).decode())
        tk.Label(card, image=self._qr, bg="#FFFFFF", bd=0).pack()

        steps = tk.Frame(row, bg=BG, padx=22)
        steps.pack(side="left", fill="both", expand=True)
        for n, (title, text) in enumerate(STEPS, 1):
            item = tk.Frame(steps, bg=BG)
            item.pack(fill="x", pady=(0, 14))
            dot = tk.Canvas(item, width=26, height=26, bg=BG, highlightthickness=0)
            dot.create_oval(1, 1, 25, 25, fill=PANEL, outline=ACCENT)
            dot.create_text(13, 13, text=str(n), fill=ACCENT, font=(ui, fsize(10), "bold"))
            dot.pack(side="left", anchor="n", padx=(0, 12))
            words = tk.Frame(item, bg=BG)
            words.pack(side="left", fill="x", expand=True)
            tk.Label(words, text=title, bg=BG, fg=TEXT, font=(ui, fsize(12), "bold"),
                     anchor="w").pack(fill="x")
            tk.Label(words, text=text, bg=BG, fg=MUTED, font=(ui, fsize(10)), anchor="w",
                     justify="left", wraplength=300).pack(fill="x")

        link = tk.Frame(body, bg=PANEL, highlightthickness=1, highlightbackground=BORDER, padx=12, pady=8)
        link.pack(fill="x", pady=(6, 4))
        tk.Label(link, text="Or type this into your phone's browser:", bg=PANEL, fg=MUTED,
                 font=(ui, fsize(9))).pack(anchor="w")
        self.link = tk.Entry(link, bg=PANEL, fg=TEXT, relief="flat", font=(mono, fsize(9)),
                             readonlybackground=PANEL, highlightthickness=0)
        self.link.insert(0, url)
        self.link.configure(state="readonly")
        self.link.pack(fill="x")
        from urllib.parse import urlparse

        from vector.remote import tailscale_address

        away = tailscale_address()
        if away:
            parsed = urlparse(url)
            tk.Label(link, text="Away from home, with Tailscale on both:", bg=PANEL, fg=MUTED,
                     font=(ui, fsize(9))).pack(anchor="w", pady=(6, 0))
            far = tk.Entry(link, bg=PANEL, fg=TEXT, relief="flat", font=(mono, fsize(9)),
                           readonlybackground=PANEL, highlightthickness=0)
            far.insert(0, parsed._replace(netloc=f"{away}:{parsed.port}").geturl())
            far.configure(state="readonly")
            far.pack(fill="x")
        tk.Label(body, text="Anyone with this code can see and use this computer. Only scan it "
                            "with your own phone; /phone reset makes a new one.",
                 bg=BG, fg=MUTED, font=(ui, fsize(9)), wraplength=560, justify="left").pack(
                     anchor="w", pady=(8, 14))

        buttons = tk.Frame(body, bg=BG)
        buttons.pack(fill="x")
        Pill(buttons, "Done", self.close, (ui, fsize(11), "bold"), fill=ACCENT, fg=BG,
             hover="#7FE3F2").canvas.pack(side="right")
        Pill(buttons, "Turn phone remote off", self.turn_off, (ui, fsize(10)), fill=BG, fg=TEXT,
             hover=PANEL, outline=BORDER).canvas.pack(side="right", padx=(0, 10))

        win.update_idletasks()
        x = (win.winfo_screenwidth() - win.winfo_reqwidth()) // 2
        y = (win.winfo_screenheight() - win.winfo_reqheight()) // 3
        win.geometry(f"+{x}+{y}")
        win.lift()
        win.focus_force()

    def turn_off(self) -> None:
        if self.on_off:
            self.on_off()
        self.close()

    def close(self) -> None:
        try:
            self.win.destroy()
        except Exception:
            pass
        if self.on_close:
            callback, self.on_close = self.on_close, None
            callback()
