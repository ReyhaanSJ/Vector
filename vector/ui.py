"""The summon bar: VECTOR's pop-up window, drawn to match the VECTOR design
(rounded panel, triangle mark, mic button, numbered steps, Allow / Deny card)."""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

# Colours from the VECTOR design.
BG = "#0B1016"
PANEL = "#13202A"
CHIP = "#15202A"
LINE = "#18212B"
BORDER = "#2A3846"
TEXT = "#E6EDF3"
MUTED = "#8B98A5"
DIM = "#5B6773"
ACCENT = "#5CD6EA"
ACCENT_BG = "#0F2A31"
AMBER = "#F2B84B"
AMBER_TEXT = "#F4DDB0"
AMBER_BG = "#1A1408"
AMBER_EDGE = "#5C4416"
RED = "#F28B82"

WIDTH = 720
PAD = 20
ASSETS = Path(__file__).parent / "assets"


def describe_step(name: str, args: dict) -> str:
    """Friendly one-line description of a skill call for the bar."""
    first = next((str(v) for v in args.values() if isinstance(v, (str, int, float))), "")
    label = name.replace("_", " ").capitalize()
    if first:
        first = first if len(first) < 48 else first[:45] + "..."
        return f"{label}: {first}"
    return label


# Tk on macOS draws fonts at 72 dpi (Windows: 96), so the same size looks smaller on a Mac.
FONT_SCALE = 1.3 if sys.platform == "darwin" else 1.0
UI_FONTS = ["Segoe UI Variable Text", "Segoe UI", "SF Pro Text", ".AppleSystemUIFont",
            "Helvetica Neue", "Inter"]
MONO_FONTS = ["Cascadia Mono", "Consolas", "SF Mono", "Menlo", "JetBrains Mono", "DejaVu Sans Mono"]


MAC_TITLE = "VECTOR summon bar"


def fsize(points: int) -> int:
    """A font size that looks the same on Windows and macOS."""
    return round(points * FONT_SCALE)


def pick_font(root, candidates: list[str], fallback: str) -> str:
    from tkinter import font

    available = {f.lower() for f in font.families(root)}
    return next((c for c in candidates if c.lower() in available), fallback)


def round_rect(canvas, x0, y0, x1, y1, r, **kw):
    """A rounded rectangle on a Tk canvas (smoothed polygon)."""
    r = min(r, (x1 - x0) / 2, (y1 - y0) / 2)
    pts = [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1,
           x1 - r, y1, x0 + r, y1, x0, y1, x0, y1 - r, x0, y0 + r, x0, y0]
    return canvas.create_polygon(pts, smooth=True, splinesteps=24, **kw)


def draw_mark(canvas, x, y, size, color=ACCENT, width=2):
    """VECTOR's triangle mark with its x,y top-left corner."""
    top, left, right = (x + size / 2, y + 1), (x + 1, y + size - 1), (x + size - 1, y + size - 1)
    canvas.create_line(*left, *top, *right, *left, *top, fill=color, width=width,
                       joinstyle="round", capstyle="round")
    canvas.create_line(top[0], y + size * 0.42, top[0], y + size - 1, fill=color, width=width,
                       capstyle="round")


class Pill:
    """A rounded button drawn on a canvas, with hover colours and keyboard focus."""

    def __init__(self, parent, text: str, command: Callable[[], None], font, *, fill: str,
                 fg: str, hover: str, outline: str = "", width: int | None = None,
                 height: int = 38, radius: int = 10, bg: str = BG):
        import tkinter as tk
        from tkinter import font as tkfont

        self.command = command
        w = width or tkfont.Font(font=font).measure(text) + 36
        self.canvas = tk.Canvas(parent, width=w, height=height, bg=bg, highlightthickness=0,
                                cursor="hand2", takefocus=1)
        self.fill, self.hover = fill, hover
        self.shape = round_rect(self.canvas, 1, 1, w - 1, height - 1, radius, fill=fill,
                                outline=outline or fill)
        self.canvas.create_text(w / 2, height / 2, text=text, fill=fg, font=font)
        for seq, handler in (("<Button-1>", lambda e: self.command()),
                             ("<Return>", lambda e: self.command()),
                             ("<space>", lambda e: self.command()),
                             ("<Enter>", lambda e: self._paint(self.hover)),
                             ("<Leave>", lambda e: self._paint(self.fill))):
            self.canvas.bind(seq, handler)

    def _paint(self, colour: str) -> None:
        self.canvas.itemconfigure(self.shape, fill=colour)

    def pack(self, **kw):
        self.canvas.pack(**kw)
        return self


class Tooltip:
    """A small hint that appears when the mouse rests on a widget."""

    def __init__(self, widget, text: Callable[[], str]):
        self.widget, self.text, self.tip, self.job = widget, text, None, None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _event=None):
        self._hide()
        self.job = self.widget.after(450, self._show)

    def _show(self):
        import tkinter as tk

        self.job = None
        w = self.widget
        self.tip = tk.Toplevel(w)
        self.tip.overrideredirect(True)
        self.tip.attributes("-topmost", True)
        tk.Label(self.tip, text=self.text(), bg=PANEL, fg=TEXT, padx=8, pady=4,
                 font=("Segoe UI", 9) if sys.platform == "win32" else ("Helvetica", fsize(9)),
                 highlightthickness=1, highlightbackground=BORDER).pack()
        self.tip.update_idletasks()
        x = w.winfo_rootx() + w.winfo_width() - self.tip.winfo_reqwidth()
        y = w.winfo_rooty() + w.winfo_height() + 6
        self.tip.geometry(f"+{x}+{y}")

    def _hide(self, _event=None):
        if self.job:
            self.widget.after_cancel(self.job)
            self.job = None
        if self.tip:
            self.tip.destroy()
            self.tip = None


class SummonBar:
    """The pop-up bar. Every method must run on the Tk thread."""

    def __init__(self, root, on_submit: Callable[[str], None], on_toggle_voice: Callable[[], None],
                 hotkey_label: str, on_escape: Callable[[], None] | None = None,
                 on_toggle_aloud: Callable[[], None] | None = None, focus_mode: bool = True):
        import tkinter as tk

        self.tk = tk
        self.focus_mode = focus_mode
        self.overlay = None
        self.on_escape = on_escape
        self.on_toggle_aloud = on_toggle_aloud or (lambda: None)
        self.aloud_on = False
        self.root = root
        self.on_submit = on_submit
        self.on_toggle_voice = on_toggle_voice
        self.busy = False
        self._confirm_cb: Callable[[bool], None] | None = None
        self._hide_job = None
        self._rounded = False
        self.voice_on = False
        self.voice_available = True

        ui = pick_font(root, UI_FONTS, "Helvetica")
        mono = pick_font(root, MONO_FONTS, "Courier")
        self.f_input = (ui, fsize(15))
        self.f_body = (ui, fsize(11))
        self.f_small = (ui, fsize(9))
        self.f_label = (ui, fsize(8), "bold")
        self.f_mono = (mono, fsize(9))
        self.f_button = (ui, fsize(10), "bold")

        win = self.win = tk.Toplevel(root)
        win.withdraw()
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg=BG)
        win.title(MAC_TITLE)  # never shown; lets macOS find this window to round its corners
        self._set_icon(win)

        # Off Windows 11 / macOS there are no rounded corners; a thin border frames the panel.
        outer = self._outer = tk.Frame(win, bg=BG, highlightthickness=0 if sys.platform == "win32"
                                       else 1, highlightbackground=BORDER)
        outer.pack(fill="both", expand=True)

        # -- header: mark, input, mic ----------------------------------------------------
        header = tk.Frame(outer, bg=BG, padx=PAD, pady=14)
        header.pack(fill="x")
        mark = tk.Canvas(header, width=26, height=26, bg=BG, highlightthickness=0)
        draw_mark(mark, 1, 2, 23)
        mark.pack(side="left", padx=(0, 14))
        entry_box = tk.Frame(header, bg=BG)
        entry_box.pack(side="left", fill="x", expand=True)
        self.entry = tk.Entry(entry_box, bg=BG, fg=TEXT, insertbackground=ACCENT, relief="flat",
                              font=self.f_input, highlightthickness=0, disabledbackground=BG,
                              disabledforeground=MUTED)
        self.entry.pack(fill="x", ipady=6)
        self.placeholder = tk.Label(entry_box, text="Ask VECTOR to do something...", bg=BG, fg=DIM,
                                    font=self.f_input, anchor="w")
        self.placeholder.place(x=1, rely=0.5, anchor="w")
        self.placeholder.bind("<Button-1>", lambda e: self.entry.focus_set())
        # Right-hand column: the mic (voice) button, with the small read-aloud button under it.
        controls = tk.Frame(header, bg=BG)
        controls.pack(side="left", padx=(12, 0))
        self.mic = tk.Canvas(controls, width=44, height=44, bg=BG, highlightthickness=0,
                             cursor="hand2", takefocus=1)
        self.mic.pack()
        for seq in ("<Button-1>", "<Return>", "<space>"):
            self.mic.bind(seq, lambda e: self.on_toggle_voice())
        self._draw_mic()
        self.aloud_btn = tk.Canvas(controls, width=44, height=22, bg=BG, highlightthickness=0,
                                   cursor="hand2", takefocus=1)
        self.aloud_btn.pack(pady=(5, 0))
        for seq in ("<Button-1>", "<Return>", "<space>"):
            self.aloud_btn.bind(seq, lambda e: self.on_toggle_aloud())
        Tooltip(self.aloud_btn, lambda: "Reading replies aloud. Click to stop." if self.aloud_on
                else "Read replies aloud (also reads the reply on screen now)")
        Tooltip(self.mic, lambda: "Listening for \u201cVector\u201d. Click to stop." if self.voice_on
                else "Turn on voice: just say \u201cVector, ...\u201d")
        self._draw_aloud()

        tk.Frame(outer, bg=LINE, height=1).pack(fill="x")

        # -- body ----------------------------------------------------------------------------
        self.body = tk.Frame(outer, bg=BG, padx=PAD - 8, pady=4)
        self.body.pack(fill="x")
        self.status_row = tk.Frame(self.body, bg=BG, padx=8)
        self.status_dot = tk.Canvas(self.status_row, width=10, height=10, bg=BG, highlightthickness=0)
        self.status_dot.create_oval(1, 1, 9, 9, fill=ACCENT, outline="")
        self.status_dot.pack(side="left", padx=(0, 8))
        self.status = tk.Label(self.status_row, text="", bg=BG, fg=ACCENT, font=self.f_body, anchor="w")
        self.status.pack(side="left", fill="x")

        self.steps_title = tk.Label(self.body, text="VECTOR WILL", bg=BG, fg=MUTED, font=self.f_label,
                                    anchor="w", padx=12)
        self.steps = tk.Frame(self.body, bg=BG)

        self.reply_box = tk.Frame(self.body, bg=BG, padx=12, pady=6)
        self.reply_label = tk.Label(self.reply_box, text="VECTOR", bg=BG, fg=ACCENT, font=self.f_label,
                                    anchor="w")
        self.reply_label.pack(fill="x")
        self.reply = tk.Label(self.reply_box, text="", bg=BG, fg=TEXT, font=self.f_body, anchor="w",
                              justify="left", wraplength=WIDTH - 2 * PAD - 8)
        self.reply.pack(fill="x", pady=(4, 0))

        self.confirm = tk.Canvas(self.body, bg=BG, highlightthickness=0, height=10)
        self.confirm_inner = tk.Frame(self.confirm, bg=AMBER_BG)
        title = tk.Frame(self.confirm_inner, bg=AMBER_BG)
        title.pack(fill="x")
        warn = tk.Canvas(title, width=18, height=18, bg=AMBER_BG, highlightthickness=0)
        warn.create_polygon(9, 2, 17, 16, 1, 16, outline=AMBER, fill="", width=2, joinstyle="round")
        warn.create_line(9, 7, 9, 11, fill=AMBER, width=2, capstyle="round")
        warn.create_oval(8, 13, 10, 15, fill=AMBER, outline="")
        warn.pack(side="left", padx=(0, 8))
        self.confirm_title = tk.Label(title, text="Needs your OK", bg=AMBER_BG, fg=AMBER,
                                      font=(ui, fsize(11), "bold"), anchor="w")
        self.confirm_title.pack(side="left")
        self.confirm_call = tk.Label(self.confirm_inner, text="", bg=AMBER_BG, fg=AMBER_TEXT,
                                     font=(mono, fsize(10)), anchor="w", justify="left",
                                     wraplength=WIDTH - 2 * PAD - 60)
        self.confirm_call.pack(fill="x", pady=(8, 2))
        self.confirm_hint = tk.Label(self.confirm_inner, text="", bg=AMBER_BG, fg="#C9B48A",
                                     font=self.f_small, anchor="w")
        self.confirm_hint.pack(fill="x")
        self.confirm_buttons = tk.Frame(self.confirm_inner, bg=AMBER_BG)
        self.confirm_buttons.pack(fill="x", pady=(10, 0))
        self._ui_font = ui
        self.last_dismissed = False  # True when the last question was closed with Esc

        # -- footer ----------------------------------------------------------------------------
        footer = tk.Frame(outer, bg=BG, padx=PAD, pady=10)
        footer.pack(fill="x", side="bottom")
        tk.Frame(outer, bg=LINE, height=1).pack(fill="x", side="bottom")
        hints = f"Enter  run     Esc  stop / close     {hotkey_label}  anywhere     or say “Vector”"
        tk.Label(footer, text=hints, bg=BG, fg=DIM, font=self.f_small, anchor="w").pack(side="left")
        self.model_label = tk.Label(footer, text="", bg=BG, fg=MUTED, font=self.f_small, anchor="e")
        self.model_label.pack(side="right")

        self.entry.bind("<Return>", self._submit)
        self.entry.bind("<KeyRelease>", lambda e: self._update_placeholder())
        win.bind("<Escape>", lambda e: (self.on_escape or self.hide)())
        win.bind("<Key>", self._key)
        win.bind("<Enter>", lambda e: self._cancel_auto_hide())
        win.bind("<FocusOut>", lambda e: self.root.after(200, self._maybe_hide))

    # -- drawing helpers ---------------------------------------------------------------------
    def _set_icon(self, win) -> None:
        try:
            if sys.platform == "win32" and (ASSETS / "icon.ico").exists():
                win.iconbitmap(default=str(ASSETS / "icon.ico"))
            elif (ASSETS / "icon.png").exists():
                self._icon_img = self.tk.PhotoImage(file=str(ASSETS / "icon.png"))
                win.iconphoto(True, self._icon_img)
        except Exception:
            pass

    def _draw_mic(self) -> None:
        c = self.mic
        c.delete("all")
        on, ok = self.voice_on, self.voice_available
        fill = ACCENT_BG if on else CHIP
        stroke = ACCENT if on else (MUTED if ok else DIM)
        round_rect(c, 1, 1, 43, 43, 11, fill=fill, outline=ACCENT if on else fill)
        round_rect(c, 17, 10, 27, 26, 5, fill="", outline=stroke, width=2)
        c.create_arc(13, 13, 31, 31, start=200, extent=140, style="arc", outline=stroke, width=2)
        c.create_line(22, 31, 22, 35, fill=stroke, width=2, capstyle="round")
        if not on:
            c.create_line(13, 33, 31, 11, fill=stroke, width=2, capstyle="round")

    def _draw_aloud(self) -> None:
        """The small read-aloud button: a speaker, with sound waves when on."""
        c = self.aloud_btn
        c.delete("all")
        on = self.aloud_on
        fill = ACCENT_BG if on else CHIP
        stroke = ACCENT if on else MUTED
        round_rect(c, 1, 1, 43, 21, 7, fill=fill, outline=ACCENT if on else fill)
        c.create_polygon(13, 9, 16, 9, 20, 5, 20, 17, 16, 13, 13, 13, fill=stroke, outline=stroke)
        if on:
            c.create_arc(17, 6, 25, 16, start=-50, extent=100, style="arc", outline=stroke, width=1.6)
            c.create_arc(18, 3, 30, 19, start=-50, extent=100, style="arc", outline=stroke, width=1.6)
        else:
            c.create_line(24, 8, 30, 14, fill=stroke, width=1.6, capstyle="round")
            c.create_line(30, 8, 24, 14, fill=stroke, width=1.6, capstyle="round")

    def set_aloud(self, on: bool) -> None:
        self.aloud_on = on
        self._draw_aloud()

    def showing_reply(self) -> str:
        """The reply on screen right now ("" if none)."""
        if self.visible() and not self.busy and self.reply_box.winfo_ismapped():
            return self.reply.cget("text")
        return ""

    def _round_corners(self) -> None:
        """Windows 11: native rounded corners, soft shadow and a thin border colour.
        macOS: rounded corners and a shadow through the window's own layer."""
        if self._rounded or sys.platform not in ("win32", "darwin"):
            return
        if sys.platform == "darwin":
            import os

            from vector.macos import round_window

            if os.environ.get("VECTOR_MAC_ROUND") == "0":
                return
            self.win.update_idletasks()
            self._rounded = round_window(MAC_TITLE, radius=14.0)
            if self._rounded:
                self._outer.configure(highlightthickness=0)  # the rounded edge replaces the border
            return
        self._rounded = True
        try:
            import ctypes

            hwnd = int(self.win.wm_frame(), 16)
            dwm = ctypes.windll.dwmapi
            corner = ctypes.c_int(2)                       # DWMWCP_ROUND
            dwm.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(corner), 4)
            border = ctypes.c_uint(0x0046382A)             # #2A3846 as 0x00BBGGRR
            dwm.DwmSetWindowAttribute(hwnd, 34, ctypes.byref(border), 4)
        except Exception:
            pass

    def _fit_confirm(self) -> None:
        inner = self.confirm_inner
        self.win.update_idletasks()
        w = self.confirm.winfo_width()
        if w < 100:  # not laid out yet
            w = WIDTH - 2 * (PAD - 8) - 16
        h = inner.winfo_reqheight() + 32
        c = self.confirm
        c.delete("all")
        c.configure(height=h)
        round_rect(c, 1, 1, w - 2, h - 2, 14, fill=AMBER_BG, outline=AMBER_EDGE)
        c.create_window(18, 16, window=inner, anchor="nw", width=w - 36)

    # -- showing and hiding ------------------------------------------------------------------
    # -- focus mode: dim and block the rest of the screen while the bar is open -------------
    def _virtual_screen(self) -> tuple[int, int, int, int]:
        """x, y, width, height covering every monitor."""
        if sys.platform == "win32":
            try:
                import ctypes

                m = ctypes.windll.user32.GetSystemMetrics
                return m(76), m(77), m(78), m(79)  # SM_X/Y/CX/CYVIRTUALSCREEN
            except Exception:
                pass
        return 0, 0, self.win.winfo_screenwidth(), self.win.winfo_screenheight()

    def _show_overlay(self) -> None:
        tk = self.tk
        if self.overlay is None:
            ov = self.overlay = tk.Toplevel(self.root)
            ov.withdraw()
            ov.overrideredirect(True)
            ov.attributes("-topmost", True)
            ov.configure(bg="#03060A", cursor="arrow")
            try:
                ov.attributes("-alpha", 0.45)
            except tk.TclError:
                pass
            for seq in ("<Button-1>", "<Button-2>", "<Button-3>", "<Double-Button-1>"):
                ov.bind(seq, lambda e: self._bring_back())
            ov.bind("<Escape>", lambda e: (self.on_escape or self.hide)())
        x, y, w, h = self._virtual_screen()
        self.overlay.geometry(f"{w}x{h}+{x}+{y}")
        self.overlay.deiconify()
        self.overlay.lift()

    def hide_overlay(self) -> None:
        if self.overlay is not None:
            self.overlay.withdraw()

    def overlay_visible(self) -> bool:
        return self.overlay is not None and bool(self.overlay.winfo_viewable())

    def _bring_back(self) -> None:
        """A click outside the bar: keep the bar in front and focused instead."""
        self.win.lift()
        self.win.focus_force()
        self.entry.focus_set()

    def show(self, focus: bool = True) -> None:
        self._cancel_auto_hide()
        if focus and self.focus_mode:
            self._show_overlay()
        win = self.win
        win.update_idletasks()
        x = (win.winfo_screenwidth() - WIDTH) // 2
        y = int(win.winfo_screenheight() * 0.22)
        win.geometry(f"{WIDTH}x{win.winfo_reqheight()}+{x}+{y}")
        win.deiconify()
        win.lift()
        self._round_corners()
        if focus:
            if sys.platform == "darwin":
                import os

                from vector.macos import activate

                if os.environ.get("VECTOR_MAC_ACTIVATE") != "0":
                    activate()  # VECTOR becomes the active app, so typing goes to the bar
            win.focus_force()
            self.entry.focus_set()
            if sys.platform == "win32":
                try:
                    import ctypes

                    ctypes.windll.user32.SetForegroundWindow(int(win.wm_frame(), 16))
                except Exception:
                    pass

    def hide(self) -> None:
        if self._confirm_cb is not None:
            self._answer(False, dismissed=True)
        self._cancel_auto_hide()
        self.hide_overlay()
        self.win.withdraw()

    def tuck(self) -> None:
        """Get out of the way while VECTOR looks at or clicks the screen."""
        self.hide_overlay()
        self.win.withdraw()

    def visible(self) -> bool:
        return bool(self.win.winfo_viewable())

    def hide_later(self, ms: int = 8000) -> None:
        self._cancel_auto_hide()
        self._hide_job = self.root.after(ms, self.hide)

    def _cancel_auto_hide(self) -> None:
        if self._hide_job is not None:
            self.root.after_cancel(self._hide_job)
            self._hide_job = None

    def _maybe_hide(self) -> None:
        if self.overlay_visible():  # focus mode: stay until Esc
            if self.win.focus_get() is None:
                self._bring_back()
            return
        if self.busy or self._confirm_cb is not None:
            return
        if self.win.focus_get() is None and self.visible():
            self.hide()

    def _refit(self) -> None:
        self.win.update_idletasks()
        if self.visible():
            self.win.geometry(f"{WIDTH}x{self.win.winfo_reqheight()}")

    def _update_placeholder(self) -> None:
        if self.entry.get():
            self.placeholder.place_forget()
        else:
            self.placeholder.place(x=1, rely=0.5, anchor="w")

    # -- content ------------------------------------------------------------------------------
    def set_status(self, text: str, color: str = ACCENT) -> None:
        if text:
            self.status.configure(text=text, fg=color)
            self.status_dot.itemconfigure(1, fill=color)
            if not self.status_row.winfo_ismapped():
                self.status_row.pack(fill="x", pady=(10, 4), before=self._first_section())
        else:
            self.status_row.pack_forget()
        self._refit()

    def _first_section(self):
        for w in (self.steps_title, self.steps, self.reply_box, self.confirm):
            if w.winfo_ismapped():
                return w
        return None

    def set_model(self, text: str) -> None:
        self.model_label.configure(text=text)

    def set_voice(self, on: bool, available: bool = True) -> None:
        self.voice_on, self.voice_available = on, available
        self._draw_mic()

    def start_request(self, text: str, typed: bool) -> None:
        self.busy = True
        if not typed:
            self.entry.configure(state="normal")
            self.entry.delete(0, "end")
            self.entry.insert(0, text)
        self._update_placeholder()
        self.entry.configure(state="disabled")
        for child in self.steps.winfo_children():
            child.destroy()
        self.steps_title.configure(text="VECTOR WILL")
        for w in (self.steps_title, self.steps, self.reply_box):
            w.pack_forget()
        self.set_status("Thinking...")

    def add_step(self, name: str, args: dict) -> None:
        tk = self.tk
        if not self.steps.winfo_ismapped():
            self.steps_title.pack(fill="x", pady=(8, 4))
            self.steps.pack(fill="x")
        n = len(self.steps.winfo_children()) + 1
        w, h = WIDTH - 2 * (PAD - 8) - 16, 42
        row = tk.Canvas(self.steps, width=w, height=h, bg=BG, highlightthickness=0)
        if n == 1:
            round_rect(row, 0, 0, w, h, 10, fill=PANEL, outline=PANEL)
        round_rect(row, 12, 10, 34, 32, 6, fill=CHIP, outline=CHIP)
        row.create_text(23, 21, text=str(n), fill=ACCENT, font=self.f_mono)
        row.create_text(48, 21, text=describe_step(name, args), fill=TEXT, font=self.f_body, anchor="w")
        row.create_text(w - 14, 21, text=name, fill=MUTED, font=self.f_mono, anchor="e")
        row.pack(fill="x", pady=1, padx=8)
        self._refit()

    def finish_request(self, reply: str, error: bool = False) -> None:
        self.busy = False
        self.entry.configure(state="normal")
        self.entry.delete(0, "end")
        self._update_placeholder()
        self.steps_title.configure(text="DONE")
        self.reply_label.configure(text="SOMETHING WENT WRONG" if error else "VECTOR",
                                   fg=RED if error else ACCENT)
        self.reply.configure(text=reply, fg=AMBER_TEXT if error else TEXT)
        self.reply_box.pack(fill="x", pady=(6, 8))
        self.set_status("")
        if self.visible():
            self.entry.focus_set()

    def _make_buttons(self, yes: str, no: str) -> None:
        for child in self.confirm_buttons.winfo_children():
            child.destroy()
        from tkinter import font as tkfont

        width = max(120, max(tkfont.Font(font=self.f_button).measure(t) for t in (yes, no)) + 36)
        Pill(self.confirm_buttons, yes, lambda: self._answer(True), self.f_button, fill=AMBER,
             fg=AMBER_BG, hover="#FFD27A", width=width, bg=AMBER_BG).pack(side="left")
        Pill(self.confirm_buttons, no, lambda: self._answer(False), (self._ui_font, 10), fill=AMBER_BG,
             fg=AMBER_TEXT, hover="#2A2110", outline=AMBER_EDGE, width=width,
             bg=AMBER_BG).pack(side="left", padx=(8, 0))

    def ask_choice(self, title: str, text: str, yes: str, no: str,
                   callback: Callable[[bool], None], hint: str = "Press Y or N.") -> None:
        """A question with your own wording, e.g. for /uninstall."""
        self._confirm_cb = callback
        self.confirm_title.configure(text=title)
        self.confirm_call.configure(text=text)
        self.confirm_hint.configure(text=hint)
        self._make_buttons(yes, no)
        for w in (self.steps_title, self.steps, self.reply_box):
            w.pack_forget()
        self.confirm.pack(fill="x", pady=(8, 10), padx=8)
        self._fit_confirm()
        self.show(focus=True)
        self._refit()

    def ask_confirm(self, name: str, args: dict, callback: Callable[[bool], None]) -> None:
        self._confirm_cb = callback
        self.confirm_title.configure(text="Needs your OK")
        self.confirm_hint.configure(text="Press Y or N, or say yes or no.")
        self._make_buttons("Allow", "Deny")
        if name == "use_your_screen":
            text = "See and control your screen (mouse and keyboard) for this request"
        else:
            details = ", ".join(f"{k}={v!r}" for k, v in args.items())
            text = f"{name}({details[:240]})"
        self.confirm_call.configure(text=text)
        self.confirm.pack(fill="x", pady=(8, 10), padx=8)
        self._fit_confirm()
        self.show(focus=True)
        self._refit()

    def cancel_confirm(self) -> None:
        if self._confirm_cb is not None:
            self._confirm_cb = None
            self.confirm.pack_forget()
            self._refit()

    def _answer(self, allowed: bool, dismissed: bool = False) -> None:
        self.last_dismissed = dismissed
        cb, self._confirm_cb = self._confirm_cb, None
        self.confirm.pack_forget()
        self._refit()
        if cb:
            cb(allowed)

    def _key(self, event) -> None:
        if self._confirm_cb is not None and event.keysym.lower() in {"y", "n"}:
            self._answer(event.keysym.lower() == "y")

    def _submit(self, _event=None) -> None:
        text = self.entry.get().strip()
        if text and not self.busy:
            self.on_submit(text)
