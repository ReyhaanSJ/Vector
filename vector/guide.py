"""The illustrated VECTOR guide: shown the first time VECTOR starts, and again with /guide,
`vector --guide` or the tray menu.

Each page has a drawing (keys, the summon bar, the mic, the tray...) made from VECTOR's own
design, plus a line or two of text.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Callable

from vector import __version__
from vector.config import HOME_DIR
from vector.ui import (
    ACCENT,
    ACCENT_BG,
    AMBER,
    AMBER_BG,
    AMBER_EDGE,
    AMBER_TEXT,
    BG,
    BORDER,
    CHIP,
    DIM,
    LINE,
    MONO_FONTS,
    MUTED,
    PANEL,
    TEXT,
    UI_FONTS,
    draw_mark,
    fsize,
    pick_font,
    round_rect,
)

STATE_FILE = HOME_DIR / "state.json"
W, H = 760, 560          # window
CW, CH = 680, 270        # illustration area


# -- remembering whether the guide was seen ---------------------------------------------------
def _state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def should_show() -> bool:
    return not _state().get("guide_seen")


def mark_seen() -> None:
    data = _state()
    data["guide_seen"] = __version__
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        pass


# -- drawing helpers -----------------------------------------------------------------------------
class Pen:
    def __init__(self, canvas, fonts):
        self.c = canvas
        self.f = fonts

    def key(self, x, y, label, w=None, glow=False):
        """A keyboard key."""
        w = w or max(54, 18 + 10 * len(label))
        round_rect(self.c, x, y + 4, x + w, y + 54, 10, fill="#05080C", outline="#05080C")
        round_rect(self.c, x, y, x + w, y + 50, 10, fill=ACCENT_BG if glow else PANEL,
                   outline=ACCENT if glow else BORDER, width=2 if glow else 1)
        self.c.create_text(x + w / 2, y + 25, text=label, fill=ACCENT if glow else TEXT,
                           font=self.f["key"])
        return x + w

    def plus(self, x, y):
        self.c.create_text(x + 14, y + 25, text="+", fill=MUTED, font=self.f["big"])
        return x + 28

    def mini_bar(self, x, y, w, text, placeholder=False, aloud=False):
        """A small copy of the summon bar."""
        round_rect(self.c, x, y, x + w, y + 64, 14, fill=BG, outline=BORDER, width=1)
        draw_mark(self.c, x + 18, y + 20, 24)
        self.c.create_text(x + 58, y + 32, text=text, anchor="w", font=self.f["body"],
                           fill=DIM if placeholder else TEXT)
        self.mic(x + w - 52, y + 12, on=True, size=40)
        if aloud:
            self.speaker(x + w - 52, y + 56, on=True)

    def mic(self, x, y, on=True, size=44):
        s = size / 44
        round_rect(self.c, x, y, x + size, y + size, 11 * s, fill=ACCENT_BG if on else CHIP,
                   outline=ACCENT if on else CHIP, width=2)
        stroke = ACCENT if on else MUTED
        round_rect(self.c, x + 16 * s, y + 9 * s, x + 28 * s, y + 27 * s, 6 * s, fill="",
                   outline=stroke, width=2)
        self.c.create_arc(x + 12 * s, y + 12 * s, x + 32 * s, y + 32 * s, start=200, extent=140,
                          style="arc", outline=stroke, width=2)
        self.c.create_line(x + 22 * s, y + 32 * s, x + 22 * s, y + 37 * s, fill=stroke, width=2)

    def speaker(self, x, y, on=True, scale=1.0):
        s = scale
        round_rect(self.c, x, y, x + 44 * s, y + 22 * s, 7 * s, fill=ACCENT_BG if on else CHIP,
                   outline=ACCENT if on else CHIP)
        stroke = ACCENT if on else MUTED
        self.c.create_polygon(x + 13 * s, y + 9 * s, x + 16 * s, y + 9 * s, x + 20 * s, y + 5 * s,
                              x + 20 * s, y + 17 * s, x + 16 * s, y + 13 * s, x + 13 * s, y + 13 * s,
                              fill=stroke, outline=stroke)
        if on:
            for r in (0, 1):
                self.c.create_arc(x + (17 + r) * s, y + (6 - 3 * r) * s, x + (25 + 5 * r) * s,
                                  y + (16 + 3 * r) * s, start=-50, extent=100, style="arc",
                                  outline=stroke, width=1.6)

    def bubble(self, x, y, text, color=TEXT, edge=BORDER, fill=PANEL, tail="left"):
        from tkinter import font as tkfont

        w = tkfont.Font(font=self.f["body"]).measure(text) + 36
        round_rect(self.c, x, y, x + w, y + 46, 16, fill=fill, outline=edge)
        tx = x + 26 if tail == "left" else x + w - 26
        self.c.create_polygon(tx - 8, y + 45, tx + 8, y + 45, tx - (12 if tail == "left" else -12),
                              y + 60, fill=fill, outline=edge)
        self.c.create_line(tx - 7, y + 45, tx + 7, y + 45, fill=fill, width=2)
        self.c.create_text(x + 18, y + 23, text=text, anchor="w", font=self.f["body"], fill=color)
        return x + w

    def waves(self, x, y, n=3, color=ACCENT):
        for i in range(n):
            r = 10 + i * 9
            self.c.create_arc(x - r, y - r, x + r, y + r, start=-45, extent=90, style="arc",
                              outline=color, width=2)


# -- the pages -----------------------------------------------------------------------------------
def page_welcome(p: Pen, hotkey: str):
    c = p.c
    draw_mark(c, CW / 2 - 55, 30, 110, width=6)
    c.create_text(CW / 2, 182, text="V E C T O R", font=p.f["title"], fill=TEXT)
    c.create_text(CW / 2, 220, text="your laptop, on command", font=p.f["body"], fill=MUTED)


MAC_KEY_NAMES = {"ctrl": "control", "control": "control", "shift": "shift", "alt": "option",
                 "option": "option", "cmd": "command", "win": "command", "space": "space"}


def key_labels(hotkey: str) -> list[str]:
    """How the keys are printed on this computer's keyboard."""
    if sys.platform == "darwin":
        return [MAC_KEY_NAMES.get(k, k.upper() if len(k) == 1 else k) for k in hotkey.split("+")]
    return [k.capitalize() if len(k) > 1 else k.upper() for k in hotkey.split("+")]


def page_summon(p: Pen, hotkey: str):
    keys = key_labels(hotkey)
    widths = [max(54, 18 + 10 * len(k)) for k in keys]
    total = sum(widths) + 28 * (len(keys) - 1)
    x = (CW - total) / 2
    for i, k in enumerate(keys):
        x = p.key(x, 16, k, glow=True)
        if i < len(keys) - 1:
            x = p.plus(x, 16)
    p.c.create_line(CW / 2, 84, CW / 2, 120, fill=MUTED, width=2, arrow="last", arrowshape=(10, 12, 5))
    p.mini_bar(60, 134, CW - 120, "open spotify and play my liked songs")
    p.c.create_text(CW - 60, 222, text="Enter", anchor="e", font=p.f["small"], fill=MUTED)


def page_voice(p: Pen, hotkey: str):
    p.mic(110, 90, on=True, size=88)
    p.waves(210, 134, 3)
    p.bubble(260, 70, "Vector, what's the weather today?", tail="left")
    p.bubble(330, 150, "Sunny and 31 degrees in Mumbai.", color=ACCENT, edge=ACCENT, fill=ACCENT_BG,
             tail="right")
    p.c.create_text(154, 196, text="mic on = listening", font=p.f["small"], fill=MUTED)


def page_aloud(p: Pen, hotkey: str):
    p.mini_bar(60, 30, CW - 120, "what's the latest news in India?", aloud=True)
    p.c.create_line(CW - 82, 112, CW - 82, 140, fill=ACCENT, width=2, arrow="first",
                    arrowshape=(9, 11, 4))
    p.c.create_text(CW - 82, 152, text="read aloud", font=p.f["small"], fill=ACCENT)
    p.bubble(80, 180, "Here are today's top stories...", tail="left")
    p.waves(392, 203, 3)


def page_asks(p: Pen, hotkey: str):
    c = p.c
    x, y, w = 90, 24, CW - 180
    round_rect(c, x, y, x + w, y + 170, 16, fill=AMBER_BG, outline=AMBER_EDGE)
    c.create_polygon(x + 30, y + 22, x + 44, y + 46, x + 16, y + 46, outline=AMBER, fill="", width=2)
    c.create_text(x + 56, y + 34, text="Needs your OK", anchor="w", font=p.f["head"], fill=AMBER)
    c.create_text(x + 20, y + 74, text="See and control your screen for this request", anchor="w",
                  font=p.f["mono"], fill=AMBER_TEXT)
    for i, (label, fill, fg) in enumerate((("Allow", AMBER, AMBER_BG), ("Deny", AMBER_BG, AMBER_TEXT))):
        bx = x + 20 + i * 136
        round_rect(c, bx, y + 108, bx + 124, y + 146, 10, fill=fill, outline=AMBER_EDGE)
        c.create_text(bx + 62, y + 127, text=label, font=p.f["button"], fill=fg)
    c.create_text(CW / 2, 228, text="press Y or N   ·   or just say yes / no", font=p.f["small"],
                  fill=MUTED)


def page_stop(p: Pen, hotkey: str):
    p.key(CW / 2 - 70, 40, "Esc", w=140, glow=True)
    items = ["stops talking", "cancels the task", "answers Deny", "closes the bar"]
    x = 60
    for item in items:
        from tkinter import font as tkfont

        w = tkfont.Font(font=p.f["small"]).measure(item) + 28
        round_rect(p.c, x, 150, x + w, 182, 16, fill=PANEL, outline=BORDER)
        p.c.create_text(x + w / 2, 166, text=item, font=p.f["small"], fill=TEXT)
        x += w + 14
    p.c.create_text(CW / 2, 222, text="works from any app while VECTOR is busy or talking",
                    font=p.f["small"], fill=MUTED)


def page_tray(p: Pen, hotkey: str):
    c = p.c
    round_rect(c, 40, 200, CW - 40, 250, 10, fill="#202830", outline="#202830")
    for i in range(4):
        round_rect(c, 60 + i * 44, 211, 88 + i * 44, 239, 6, fill="#39434E", outline="#39434E")
    c.create_text(CW - 70, 225, text="9:41 AM", font=p.f["small"], fill=TEXT)
    tx = CW - 170
    c.create_oval(tx, 212, tx + 26, 238, fill=BG, outline=ACCENT, width=2)
    draw_mark(c, tx + 6, 217, 14, width=2)
    menu = ["Open VECTOR", "Listen for “Vector”", "Update to 0.4.0", "Guide", "Quit VECTOR"]
    mx, my = tx - 140, 18
    round_rect(c, mx, my, mx + 190, my + 30 * len(menu) + 14, 10, fill=PANEL, outline=BORDER)
    for i, item in enumerate(menu):
        c.create_text(mx + 16, my + 22 + i * 30, text=item, anchor="w", font=p.f["small"],
                      fill=ACCENT if item.startswith("Update") else TEXT)
    c.create_line(tx + 13, my + 30 * len(menu) + 16, tx + 13, 208, fill=MUTED, width=2,
                  arrow="first", arrowshape=(9, 11, 4))
    c.create_text(40, 40, text="right-click the\nVECTOR icon", anchor="nw", font=p.f["body"], fill=MUTED)


def page_mac_menu(p: Pen, hotkey: str):
    """macOS: the VECTOR menu in the menu bar, and the Dock icon."""
    c = p.c
    round_rect(c, 30, 8, CW - 30, 38, 8, fill="#202830", outline="#202830")
    c.create_text(52, 23, text="\uf8ff", font=p.f["body"], fill=TEXT)  # Apple logo (Mac fonts)
    from tkinter import font as tkfont

    c.create_text(76, 23, text="VECTOR", anchor="w", font=p.f["head"], fill=TEXT)
    x = 76 + tkfont.Font(font=p.f["head"]).measure("VECTOR") + 22
    for word in ("Edit", "Window"):
        c.create_text(x, 23, text=word, anchor="w", font=p.f["small"], fill=MUTED)
        x += tkfont.Font(font=p.f["small"]).measure(word) + 22
    c.create_text(CW - 50, 23, text="9:41", anchor="e", font=p.f["small"], fill=TEXT)
    menu = ["Open VECTOR", "Listen for \u201cVector\u201d", "Update to 0.4.1", "Guide", "Quit VECTOR  \u2318Q"]
    mx, my = 62, 44
    round_rect(c, mx, my, mx + 210, my + 26 * len(menu) + 12, 10, fill=PANEL, outline=BORDER)
    for i, item in enumerate(menu):
        c.create_text(mx + 16, my + 19 + i * 26, text=item, anchor="w", font=p.f["small"],
                      fill=ACCENT if item.startswith("Update") else TEXT)
    # the Dock
    dx = CW - 300
    round_rect(c, dx, 196, dx + 250, 258, 16, fill="#202830", outline="#2A3846")
    for i in range(4):
        round_rect(c, dx + 14 + i * 58, 206, dx + 56 + i * 58, 248, 10,
                   fill="#39434E" if i != 2 else BG, outline=ACCENT if i == 2 else "#39434E")
    draw_mark(c, dx + 14 + 2 * 58 + 9, 213, 24, width=2)
    c.create_oval(dx + 14 + 2 * 58 + 19, 251, dx + 14 + 2 * 58 + 23, 255, fill=TEXT, outline=TEXT)
    c.create_text(dx - 16, 227, text="click it in the Dock\nto open the bar", anchor="e",
                  font=p.f["small"], fill=MUTED, justify="right")


def page_mac_allow(p: Pen, hotkey: str):
    """macOS: the three permissions VECTOR may ask for."""
    c = p.c
    rows = [("Microphone", "to hear \u201cVector, ...\u201d"),
            ("Screen Recording", "to see your screen when you ask"),
            ("Accessibility", "to click and type for you")]
    x0, x1 = 90, CW - 90
    round_rect(c, x0, 4, x1, 62 + 66 * len(rows), 14, fill=PANEL, outline=BORDER)
    c.create_text(x0 + 20, 26, text="System Settings \u203a Privacy & Security", anchor="w",
                  font=p.f["small"], fill=MUTED)
    for i, (name, why) in enumerate(rows):
        y = 56 + i * 66
        c.create_line(x0 + 16, y - 8, x1 - 16, y - 8, fill=LINE)
        draw_mark(c, x0 + 22, y + 6, 22, width=2)
        c.create_text(x0 + 60, y + 8, text=f"VECTOR \u00b7 {name}", anchor="w", font=p.f["head"],
                      fill=TEXT)
        c.create_text(x0 + 60, y + 32, text=why, anchor="w", font=p.f["small"], fill=MUTED)
        tx = x1 - 76  # a switch, turned on
        round_rect(c, tx, y + 6, tx + 52, y + 34, 14, fill=ACCENT, outline=ACCENT)
        c.create_oval(tx + 27, y + 9, tx + 49, y + 31, fill=TEXT, outline=TEXT)


def page_try(p: Pen, hotkey: str):
    from tkinter import font as tkfont

    ideas = ["What's on my screen?", "Search the web for today's top news",
             "Tidy my Downloads folder", "Remind me to stretch in 20 minutes",
             "Open VS Code and my project folder", "Set volume to 30 and dark mode on",
             "Read this page aloud: <link>", "What's my battery like?"]
    x, y = 20, 14
    for idea in ideas:
        w = tkfont.Font(font=p.f["body"]).measure(idea) + 36
        if x + w > CW - 20:
            x, y = 20, y + 58
        round_rect(p.c, x, y, x + w, y + 42, 21, fill=PANEL, outline=BORDER)
        p.c.create_text(x + 18, y + 21, text=idea, anchor="w", font=p.f["body"], fill=TEXT)
        x += w + 12


PAGES: list[tuple[str, str, Callable]] = [
    ("Welcome to VECTOR", "An assistant that runs your laptop: apps, files, the web, your screen. "
     "This quick tour takes a minute. VECTOR works in English for now.", page_welcome),
    ("Summon it from anywhere", "Press {hotkey} in any app, type what you want, press Enter. "
     "VECTOR shows each step as it works.", page_summon),
    ("Or just say “Vector”", "No button needed: say “Vector”, then your request. "
     "The mic button turns listening on or off.", page_voice),
    ("Hear the answers", "The small speaker under the mic reads replies out loud. Clicked too "
     "late? Click it and it reads the reply on screen.", page_aloud),
    ("It asks before risky things", "Deleting, running commands and using your screen need your OK. "
     "Screenshots go to your AI provider, so close private things first.", page_asks),
    ("Esc stops everything", "Talking, a task, a question: Esc ends it. While the bar is open, "
     "the rest of the screen dims until you press Esc.", page_stop),
    ("Find it in the tray", "VECTOR lives by the clock. Right-click it to listen, update, open "
     "this guide again, or quit.", page_tray),
    ("Things to try", "Ask in your own words. Type /guide in the bar to see this again, or "
     "/uninstall to remove VECTOR (you can keep your data).", page_try),
]

if sys.platform == "darwin":  # a Mac has no tray; it has the menu bar, the Dock and permissions
    _tray = next(i for i, page in enumerate(PAGES) if page[2] is page_tray)
    PAGES[_tray] = ("Find it in the menu bar", "When VECTOR is the active app, its menu is at the top "
                    "left: listen, update, this guide, quit. Or click its icon in the Dock.",
                    page_mac_menu)
    PAGES.insert(_tray + 1, ("Allow VECTOR on your Mac", "macOS asks once for each of these. "
                             "If you said no, turn VECTOR on here and reopen it.", page_mac_allow))


# -- the window ----------------------------------------------------------------------------------
class GuideWindow:
    def __init__(self, master, hotkey: str = "ctrl+shift+space", on_close: Callable | None = None):
        import tkinter as tk

        self.tk = tk
        self.hotkey = hotkey
        self.on_close = on_close
        self.index = 0
        win = self.win = tk.Toplevel(master)
        win.title("VECTOR Guide")
        win.configure(bg=BG)
        win.resizable(False, False)
        win.attributes("-topmost", True)  # stay above focus mode's dimming
        x = (win.winfo_screenwidth() - W) // 2
        y = (win.winfo_screenheight() - H) // 3
        win.geometry(f"{W}x{H}+{x}+{y}")
        win.protocol("WM_DELETE_WINDOW", self.close)
        win.bind("<Escape>", lambda e: self.close())
        win.bind("<Right>", lambda e: self.next())
        win.bind("<Left>", lambda e: self.back())
        self._icon(win)

        ui = pick_font(win, UI_FONTS, "Helvetica")
        disp = pick_font(win, ["Segoe UI Variable Display", "Segoe UI Semibold", "SF Pro Display",
                               "Inter Display", "Inter"], ui)
        mono = pick_font(win, MONO_FONTS, "Courier")
        f = fsize
        self.fonts = {"title": (disp, f(26), "bold"), "head": (ui, f(13), "bold"), "body": (ui, f(12)),
                      "small": (ui, f(10)), "key": (ui, f(13), "bold"), "big": (ui, f(20)),
                      "mono": (mono, f(11)), "button": (ui, f(11), "bold"), "step": (ui, f(9), "bold")}

        self.step = tk.Label(win, text="", bg=BG, fg=ACCENT, font=self.fonts["step"], anchor="w")
        self.step.place(x=40, y=28)
        self.title = tk.Label(win, text="", bg=BG, fg=TEXT, font=(disp, fsize(20), "bold"), anchor="w")
        self.title.place(x=40, y=48)
        self.canvas = tk.Canvas(win, width=CW, height=CH, bg=BG, highlightthickness=0)
        self.canvas.place(x=(W - CW) // 2, y=104)
        self.text = tk.Label(win, text="", bg=BG, fg=MUTED, font=self.fonts["body"], justify="left",
                             anchor="nw", wraplength=W - 80)
        self.text.place(x=40, y=104 + CH + 20, width=W - 80)
        tk.Frame(win, bg=LINE, height=1).place(x=0, y=H - 72, width=W)
        self.dots = tk.Canvas(win, width=200, height=12, bg=BG, highlightthickness=0)
        self.dots.place(x=40, y=H - 42)
        self.back_btn = self._button("Back", self.back, primary=False)
        self.next_btn = self._button("Next", self.next, primary=True)
        self.back_btn.place(x=W - 40 - 110 - 10 - 110, y=H - 54)
        self.next_btn.place(x=W - 40 - 110, y=H - 54)
        self.render()
        win.lift()
        win.focus_force()

    def _icon(self, win):
        from vector.ui import ASSETS

        try:
            if sys.platform == "win32":
                win.iconbitmap(str(ASSETS / "icon.ico"))
            else:
                self._img = self.tk.PhotoImage(file=str(ASSETS / "icon.png"))
                win.iconphoto(False, self._img)
        except Exception:
            pass

    def _button(self, label, command, primary):
        c = self.tk.Canvas(self.win, width=110, height=38, bg=BG, highlightthickness=0, cursor="hand2",
                           takefocus=1)
        c.label = label
        c.primary = primary
        for seq in ("<Button-1>", "<Return>", "<space>"):
            c.bind(seq, lambda e: command())
        return c

    def _paint_button(self, c, label, primary, enabled=True):
        c.delete("all")
        fill = ACCENT if primary else BG
        fg = BG if primary else (TEXT if enabled else DIM)
        round_rect(c, 1, 1, 109, 37, 10, fill=fill, outline=ACCENT if primary else BORDER)
        c.create_text(55, 19, text=label, fill=fg, font=self.fonts["button"])

    def render(self):
        title, text, draw = PAGES[self.index]
        self.step.configure(text=f"STEP {self.index + 1} OF {len(PAGES)}")
        self.title.configure(text=title)
        label = "+".join(p.capitalize() for p in self.hotkey.split("+"))
        self.text.configure(text=text.format(hotkey=label))
        self.canvas.delete("all")
        draw(Pen(self.canvas, self.fonts), self.hotkey)
        self.dots.delete("all")
        for i in range(len(PAGES)):
            x = i * 18
            if i == self.index:
                round_rect(self.dots, x, 2, x + 22, 10, 4, fill=ACCENT, outline=ACCENT)
            else:
                self.dots.create_oval(x + 2, 2, x + 10, 10, fill=BORDER, outline="")
        last = self.index == len(PAGES) - 1
        self._paint_button(self.next_btn, "Done" if last else "Next", True)
        self._paint_button(self.back_btn, "Back" if self.index else "Skip", False)

    def next(self):
        if self.index == len(PAGES) - 1:
            self.close()
        else:
            self.index += 1
            self.render()

    def back(self):
        if self.index == 0:
            self.close()  # "Skip" on the first page
        else:
            self.index -= 1
            self.render()

    def close(self):
        mark_seen()
        self.win.destroy()
        if self.on_close:
            self.on_close()


def text_guide(hotkey: str = "ctrl+shift+space") -> str:
    """The guide for places without a screen (it's also handy as a cheat sheet)."""
    keys = " + ".join(f"[{k}]" for k in key_labels(hotkey))
    where = ("Menu bar       VECTOR menu (top left) or its Dock icon: listen, update, guide, quit"
             if sys.platform == "darwin" else "Tray icon      by the clock: listen, update, guide, quit")
    return f"""
   /\\     V E C T O R  guide
  /||\\    your laptop, on command
 /_||_\\

  1  Summon it      {keys}  then type and press Enter
  2  Say it         "Vector, open Spotify"  (mic button on = listening)
  3  Hear it        the small speaker button under the mic
  4  It asks first  risky actions and your screen need an OK:  Allow / Deny, or Y / N
  5  Stop           [Esc] stops talking, cancels a task, closes the bar
  6  {where}
     Commands       /guide  this guide      /uninstall  remove VECTOR (keep your data if you like)
  7  Try            "what's on my screen?"  "search the web for today's news"
                    "tidy my downloads"     "remind me in 20 minutes"
"""


def open_guide(hotkey: str = "ctrl+shift+space") -> bool:
    """From the terminal: open the illustrated guide in its own window (doesn't block)."""
    try:
        import tkinter  # noqa: F401
    except ImportError:
        return False
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    try:
        subprocess.Popen([sys.executable, "-m", "vector.guide", hotkey], creationflags=flags)
        return True
    except OSError:
        return False


def main() -> int:
    import tkinter as tk

    hotkey = sys.argv[1] if len(sys.argv) > 1 else "ctrl+shift+space"
    try:
        root = tk.Tk()
    except tk.TclError:
        print(text_guide(hotkey))
        return 0
    root.withdraw()
    GuideWindow(root, hotkey, on_close=root.destroy)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
