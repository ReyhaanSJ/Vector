"""VECTOR desktop app.

Runs quietly in the background with a tray icon:
  * press Ctrl+Shift+Space anywhere (configurable) to pop up the summon bar and type,
  * or just say "Vector, ..." - no button needed - and it listens, acts and answers out loud.

Start it with the VECTOR shortcut, `vector-app`, or `vector --app`.
"""

from __future__ import annotations

import logging
import queue
import sys
import threading
import traceback
from collections.abc import Callable

from vector import __version__
from vector.config import Config, load_config

log = logging.getLogger("vector.app")

# Colours from the VECTOR design.
BG = "#0B1016"
PANEL = "#13202A"
BORDER = "#2A3846"
TEXT = "#E6EDF3"
MUTED = "#8B98A5"
ACCENT = "#5CD6EA"
AMBER = "#F2B84B"
AMBER_BG = "#1A1408"
FONT = "Segoe UI" if sys.platform == "win32" else "Helvetica"
MONO = "Consolas" if sys.platform == "win32" else "Courier"


def describe_step(name: str, args: dict) -> str:
    """Friendly one-line description of a skill call for the bar."""
    first = next((str(v) for v in args.values() if isinstance(v, (str, int, float))), "")
    label = name.replace("_", " ").capitalize()
    if first:
        first = first if len(first) < 48 else first[:45] + "..."
        return f"{label}: {first}"
    return label


class SummonBar:
    """The pop-up bar. Every method must run on the Tk thread."""

    def __init__(self, root, on_submit: Callable[[str], None], on_toggle_voice: Callable[[], None],
                 hotkey_label: str):
        import tkinter as tk

        self.tk = tk
        self.root = root
        self.on_submit = on_submit
        self.on_toggle_voice = on_toggle_voice
        self.busy = False
        self._confirm_cb: Callable[[bool], None] | None = None
        self._hide_job = None

        win = self.win = tk.Toplevel(root)
        win.withdraw()
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg=BORDER)

        body = tk.Frame(win, bg=BG, padx=18, pady=14)
        body.pack(fill="both", expand=True, padx=1, pady=1)

        top = tk.Frame(body, bg=BG)
        top.pack(fill="x")
        logo = tk.Canvas(top, width=24, height=24, bg=BG, highlightthickness=0)
        logo.create_polygon(12, 2, 22, 21, 2, 21, outline=ACCENT, fill="", width=2)
        logo.create_line(12, 9, 12, 21, fill=ACCENT, width=2)
        logo.pack(side="left", padx=(0, 12))
        self.entry = tk.Entry(top, bg=BG, fg=TEXT, insertbackground=TEXT, relief="flat",
                              font=(FONT, 16), width=40, disabledbackground=BG,
                              disabledforeground=MUTED)
        self.entry.pack(side="left", fill="x", expand=True, ipady=6)
        self.voice_btn = tk.Button(top, text="Voice on", command=self.on_toggle_voice, bg=PANEL,
                                   fg=TEXT, activebackground=BORDER, activeforeground=TEXT,
                                   relief="flat", font=(FONT, 10), padx=10, pady=6, cursor="hand2")
        self.voice_btn.pack(side="left", padx=(12, 0))

        self.status = tk.Label(body, text="", bg=BG, fg=ACCENT, font=(FONT, 10), anchor="w")
        self.status.pack(fill="x", pady=(10, 0))

        self.steps_title = tk.Label(body, text="VECTOR WILL", bg=BG, fg=MUTED, font=(FONT, 8, "bold"),
                                    anchor="w")
        self.steps = tk.Frame(body, bg=BG)

        self.reply = tk.Label(body, text="", bg=BG, fg=TEXT, font=(FONT, 12), anchor="w",
                              justify="left", wraplength=640)

        self.confirm = tk.Frame(body, bg=AMBER_BG, padx=12, pady=10, highlightthickness=1,
                                highlightbackground="#5C4416")
        self.confirm_text = tk.Label(self.confirm, text="", bg=AMBER_BG, fg="#F4DDB0",
                                     font=(FONT, 11), anchor="w", justify="left", wraplength=600)
        self.confirm_text.pack(fill="x")
        buttons = tk.Frame(self.confirm, bg=AMBER_BG)
        buttons.pack(fill="x", pady=(8, 0))
        tk.Button(buttons, text="Allow (Y)", command=lambda: self._answer(True), bg=AMBER, fg=AMBER_BG,
                  activebackground="#FFD27A", relief="flat", font=(FONT, 10, "bold"), padx=16, pady=6,
                  cursor="hand2").pack(side="left")
        tk.Button(buttons, text="Deny (N)", command=lambda: self._answer(False), bg=AMBER_BG,
                  fg="#F4DDB0", activebackground="#2A2110", relief="flat", font=(FONT, 10), padx=16,
                  pady=6, cursor="hand2").pack(side="left", padx=(8, 0))

        footer = tk.Label(body, text=f"Enter run  ·  Esc close  ·  {hotkey_label} anywhere  ·  "
                                     "or just say “Vector”",
                          bg=BG, fg=MUTED, font=(FONT, 9), anchor="w")
        footer.pack(fill="x", side="bottom", pady=(12, 0))

        self.entry.bind("<Return>", self._submit)
        win.bind("<Escape>", lambda e: self.hide())
        win.bind("<Key>", self._key)
        win.bind("<Enter>", lambda e: self._cancel_auto_hide())
        win.bind("<FocusOut>", lambda e: self.root.after(200, self._maybe_hide))

    # -- showing and hiding ----------------------------------------------------------------
    def show(self, focus: bool = True) -> None:
        self._cancel_auto_hide()
        win = self.win
        win.update_idletasks()
        width = 720
        x = (win.winfo_screenwidth() - width) // 2
        y = int(win.winfo_screenheight() * 0.22)
        win.geometry(f"{width}x{max(win.winfo_reqheight(), 140)}+{x}+{y}")
        win.deiconify()
        win.lift()
        if focus:
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
            self._answer(False)
        self._cancel_auto_hide()
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
        if self.busy or self._confirm_cb is not None:
            return
        if self.win.focus_get() is None and self.visible():
            self.hide()

    def _refit(self) -> None:
        self.win.update_idletasks()
        if self.visible():
            self.win.geometry(f"720x{max(self.win.winfo_reqheight(), 140)}")

    # -- content ----------------------------------------------------------------------------
    def set_status(self, text: str, color: str = ACCENT) -> None:
        self.status.configure(text=text, fg=color)
        self._refit()

    def set_voice(self, on: bool, available: bool = True) -> None:
        if not available:
            self.voice_btn.configure(text="Voice unavailable", state="disabled")
        else:
            self.voice_btn.configure(text="Voice on" if on else "Voice off",
                                     fg=ACCENT if on else MUTED, state="normal")

    def start_request(self, text: str, typed: bool) -> None:
        self.busy = True
        if not typed:
            self.entry.configure(state="normal")
            self.entry.delete(0, "end")
            self.entry.insert(0, text)
        self.entry.configure(state="disabled")
        for child in self.steps.winfo_children():
            child.destroy()
        self.steps_title.pack_forget()
        self.steps.pack_forget()
        self.reply.pack_forget()
        self.set_status("Thinking...")

    def add_step(self, name: str, args: dict) -> None:
        tk = self.tk
        if not self.steps.winfo_ismapped():
            self.steps_title.pack(fill="x", pady=(10, 2))
            self.steps.pack(fill="x")
        n = len(self.steps.winfo_children()) + 1
        row = tk.Frame(self.steps, bg=PANEL if n == 1 else BG, padx=10, pady=6)
        row.pack(fill="x", pady=1)
        tk.Label(row, text=str(n), bg=BORDER, fg=ACCENT, font=(MONO, 9), width=2).pack(side="left")
        tk.Label(row, text=describe_step(name, args), bg=row["bg"], fg=TEXT, font=(FONT, 11),
                 anchor="w").pack(side="left", fill="x", expand=True, padx=(10, 0))
        tk.Label(row, text=name, bg=row["bg"], fg=MUTED, font=(MONO, 9)).pack(side="right")
        self._refit()

    def finish_request(self, reply: str, error: bool = False) -> None:
        self.busy = False
        self.entry.configure(state="normal")
        self.entry.delete(0, "end")
        self.steps_title.configure(text="DONE")
        self.reply.configure(text=reply, fg=AMBER if error else TEXT)
        self.reply.pack(fill="x", pady=(10, 0))
        self.set_status("")
        if self.visible():
            self.entry.focus_set()

    def ask_confirm(self, name: str, args: dict, callback: Callable[[bool], None]) -> None:
        self._confirm_cb = callback
        details = ", ".join(f"{k}={v!r}" for k, v in args.items())
        self.confirm_text.configure(
            text=f"VECTOR wants to run {name}({details[:200]}).\nAllow it?  (you can also say yes or no)")
        self.confirm.pack(fill="x", pady=(10, 0))
        self.show(focus=True)
        self._refit()

    def cancel_confirm(self) -> None:
        if self._confirm_cb is not None:
            self._confirm_cb = None
            self.confirm.pack_forget()
            self._refit()

    def _answer(self, allowed: bool) -> None:
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


class VectorApp:
    def __init__(self, config: Config, agent=None, enable_voice: bool = True,
                 enable_tray: bool = True, enable_hotkey: bool = True):
        import tkinter as tk

        self.config = config
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title("VECTOR")
        self._ui_queue: queue.Queue = queue.Queue()
        self._requests: queue.Queue = queue.Queue()
        self._quit = threading.Event()
        self._voice_pause = threading.Event()
        self.voice_on = False
        self.voice_available = enable_voice
        self.engine = None
        self.tray = None
        self.hotkey = None
        self._current_source = "typed"
        self.update = None

        hotkey_label = "+".join(p.capitalize() for p in config.hotkey.split("+"))
        self.bar = SummonBar(self.root, self.submit_typed, self.toggle_voice, hotkey_label)

        if agent is None:
            from vector.agent import Vector
            from vector.brain import create_brain

            agent = Vector(config, create_brain(config))
        self.agent = agent
        self.agent.confirm = self._confirm
        self.agent.on_action = lambda name, args: self.ui(self.bar.add_step, name, args)

        threading.Thread(target=self._worker, name="vector-brain", daemon=True).start()
        self.root.after(40, self._drain_ui)

        if enable_hotkey:
            from vector.hotkey import GlobalHotkey

            self.hotkey = GlobalHotkey(config.hotkey, lambda: self.ui(self.summon))
            if not self.hotkey.start():
                self.notify(f"Shortcut unavailable: {self.hotkey.error}")
        if enable_tray:
            self._start_tray()
        if enable_tray and config.check_updates:
            self.root.after(15000, self.check_updates)  # once things have settled
        if enable_voice and config.listen_on_start:
            self.toggle_voice()
        else:
            self.bar.set_voice(False, available=enable_voice)

    # -- plumbing ---------------------------------------------------------------------------
    def ui(self, fn: Callable, *args) -> None:
        """Run fn on the Tk thread (safe to call from any thread)."""
        self._ui_queue.put((fn, args))

    def _drain_ui(self) -> None:
        try:
            while True:
                fn, args = self._ui_queue.get_nowait()
                try:
                    fn(*args)
                except Exception:
                    log.exception("UI callback failed")
        except queue.Empty:
            pass
        if not self._quit.is_set():
            self.root.after(40, self._drain_ui)

    def notify(self, message: str) -> None:
        log.info(message)
        if self.tray is not None:
            try:
                self.tray.notify(message, "VECTOR")
                return
            except Exception:
                pass
        self.ui(self._show_notice, message)

    def _show_notice(self, message: str) -> None:
        self.bar.set_status(message, AMBER)
        self.bar.show(focus=False)
        self.bar.hide_later(10000)

    # -- requests -----------------------------------------------------------------------------
    def summon(self) -> None:
        if self.bar.visible() and not self.bar.busy:
            self.bar.hide()
        else:
            self.bar.show()

    def submit_typed(self, text: str) -> None:
        self.bar.start_request(text, typed=True)
        self._requests.put((text, "typed", None))

    def ask(self, text: str, source: str = "typed") -> str:
        """Run a request on the brain thread and wait for the reply (used by voice)."""
        done = threading.Event()
        box: list[str] = []
        self.ui(self.bar.start_request, text, source == "typed")
        self._requests.put((text, source, (done, box)))
        done.wait()
        return box[0] if box else ""

    def _worker(self) -> None:
        from vector.brain import BrainError

        while not self._quit.is_set():
            try:
                text, source, waiter = self._requests.get(timeout=0.5)
            except queue.Empty:
                continue
            self._current_source = source
            error = False
            try:
                reply = self.agent.ask(text)
            except BrainError as exc:
                reply, error = str(exc), True
            except Exception as exc:  # never let one bad request kill the app
                log.exception("request failed")
                reply, error = f"Something went wrong: {exc}", True
            self.ui(self.bar.finish_request, reply, error)
            if source == "voice":
                self.ui(self.bar.hide_later, 9000)
            if waiter:
                done, box = waiter
                box.append(reply)
                done.set()

    def _confirm(self, name: str, args: dict) -> bool:
        """Called on the brain thread before a risky skill runs."""
        decided = threading.Event()
        result = [False]

        def answer(allowed: bool) -> None:
            if not decided.is_set():
                result[0] = allowed
                decided.set()

        self.ui(self.bar.ask_confirm, name, args, answer)
        if self._current_source == "voice" and self.engine is not None:
            def by_voice():
                self.engine.say(f"Can I run {name.replace('_', ' ')}? Say yes or no.")
                heard = self.engine.ask_yes_no(timeout=10, cancel=decided)
                if heard is not None:
                    answer(heard)
            threading.Thread(target=by_voice, daemon=True).start()
        if not decided.wait(timeout=120):
            answer(False)
        self.ui(self.bar.cancel_confirm)
        return result[0]

    # -- voice --------------------------------------------------------------------------------
    def toggle_voice(self) -> None:
        if not self.voice_available:
            return
        if self.voice_on:
            self.voice_on = False
            self._voice_pause.set()
            self.bar.set_voice(False)
            return
        self.voice_on = True
        self._voice_pause.clear()
        self.bar.set_voice(True)
        if self.engine is None:
            threading.Thread(target=self._voice_loop, name="vector-voice", daemon=True).start()

    def _voice_loop(self) -> None:
        from vector.voice import VoiceEngine, VoiceUnavailable

        try:
            self.ui(self.bar.set_status, "Starting voice (first time downloads ~200 MB)...")
            engine = VoiceEngine(self.config.wake_word, self.config.whisper_model,
                                 speak=self.config.speak_replies)
            engine.start()
            self.engine = engine
            self.ui(self.bar.set_status, "")
            self.notify(f"VECTOR is listening. Say “{self.config.wake_word.title()}” any time.")
        except VoiceUnavailable as exc:
            self.voice_available = False
            self.voice_on = False
            self.ui(self.bar.set_voice, False, False)
            self.notify(str(exc))
            return
        except Exception as exc:
            log.exception("voice failed to start")
            self.voice_on = False
            self.ui(self.bar.set_voice, False, False)
            self.notify(f"Voice couldn't start: {exc}")
            return

        import time

        while not self._quit.is_set():
            if not self.voice_on:
                time.sleep(0.3)
                continue
            try:
                command = engine.listen_for_command(
                    stop=self._voice_pause,
                    on_wake=lambda: self.ui(self._on_wake))
                if command is None:
                    continue
                if not command:
                    self.ui(self.bar.set_status, "Yes?")
                    engine.say("Yes?")
                    command = engine.listen_once()
                    if not command:
                        self.ui(self.bar.set_status, "")
                        self.ui(self.bar.hide_later, 1500)
                        continue
                reply = self.ask(command, source="voice")
                engine.say(reply)
            except VoiceUnavailable as exc:
                self.voice_on = False
                self.ui(self.bar.set_voice, False, False)
                self.notify(str(exc))
                return
            except Exception:
                log.exception("voice loop error")

    def _on_wake(self) -> None:
        self.bar.show(focus=False)
        self.bar.set_status("Listening...")

    # -- tray ---------------------------------------------------------------------------------
    def _start_tray(self) -> None:
        try:
            import pystray
            from PIL import Image, ImageDraw
        except ImportError:
            log.info("pystray/Pillow not installed: no tray icon")
            return
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.ellipse((2, 2, 62, 62), fill=(11, 16, 22, 255))
        draw.polygon([(32, 12), (52, 50), (12, 50)], outline=(92, 214, 234, 255), width=4)
        draw.line([(32, 26), (32, 50)], fill=(92, 214, 234, 255), width=4)
        menu = pystray.Menu(
            pystray.MenuItem(f"Open VECTOR ({self.config.hotkey})", lambda: self.ui(self.bar.show),
                             default=True),
            pystray.MenuItem("Listen for “Vector”", lambda: self.ui(self.toggle_voice),
                             checked=lambda item: self.voice_on, enabled=lambda item: self.voice_available),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(lambda item: f"Update to {self.update.version}" if self.update else "",
                             lambda: self.start_update(), visible=lambda item: self.update is not None),
            pystray.MenuItem("Check for updates", lambda: self.check_updates(force=True)),
            pystray.MenuItem(f"About VECTOR {__version__}", lambda: None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit VECTOR", lambda: self.ui(self.quit)),
        )
        self.tray = pystray.Icon("VECTOR", img, "VECTOR", menu)
        try:
            self.tray.run_detached()
        except Exception:
            log.exception("tray icon failed")
            self.tray = None

    # -- updates ------------------------------------------------------------------------------
    def check_updates(self, force: bool = False) -> None:
        """Look for a newer VECTOR in the background; tell the user if there is one."""
        def work():
            from vector.updater import UpdateError, check_for_update

            try:
                release = check_for_update(force=force)
            except UpdateError as exc:
                if force:
                    self.notify(str(exc))
                return
            except Exception:
                log.exception("update check failed")
                return
            self.update = release
            if self.tray is not None:
                try:
                    self.tray.update_menu()
                except Exception:
                    pass
            if release:
                self.notify(f"VECTOR {release.version} is available. "
                            "Right-click the VECTOR tray icon > Update.")
            elif force:
                self.notify(f"You have the newest VECTOR ({__version__}).")

        threading.Thread(target=work, name="vector-update-check", daemon=True).start()

    def start_update(self) -> None:
        release = self.update
        if release is None:
            return

        def work():
            from vector.updater import UpdateError, install_release

            self.notify(f"Downloading VECTOR {release.version}...")
            try:
                install_release(release)
            except UpdateError as exc:
                self.notify(str(exc))
                return
            self.ui(self.quit)  # the installer reopens VECTOR when it's done

        threading.Thread(target=work, name="vector-update", daemon=True).start()

    # -- lifecycle ----------------------------------------------------------------------------
    def quit(self) -> None:
        self._quit.set()
        self._voice_pause.set()
        if self.hotkey:
            self.hotkey.stop()
        if self.engine:
            try:
                self.engine.stop()
            except Exception:
                pass
        if self.tray:
            try:
                self.tray.stop()
            except Exception:
                pass
        self.root.after(50, self.root.destroy)

    def run(self) -> None:
        self.root.mainloop()


def _setup_logging(config: Config) -> None:
    config.home.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=config.home / "app.log", level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    def excepthook(exc_type, exc, tb):
        log.error("crash: %s", "".join(traceback.format_exception(exc_type, exc, tb)))

    sys.excepthook = excepthook


def main(argv: list[str] | None = None) -> int:
    """Start the app. `--background` (used at login) starts without popping up the bar."""
    from vector.instance import InstanceServer, signal_running

    argv = sys.argv[1:] if argv is None else argv
    background = "--background" in argv
    config = load_config()
    if signal_running("voice" if background else "show"):
        return 0  # already running: it just popped up its bar
    _setup_logging(config)
    try:
        app = VectorApp(config)
    except Exception as exc:
        log.exception("VECTOR failed to start")
        try:
            from tkinter import messagebox

            messagebox.showerror("VECTOR", f"VECTOR couldn't start:\n\n{exc}")
        except Exception:
            pass
        return 1
    server = InstanceServer(lambda msg: app.ui(
        app.quit if msg == "quit" else (lambda: None) if msg == "voice" else app.bar.show))
    server.start()
    if not background:
        app.ui(app.bar.show)
    app.run()
    server.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
