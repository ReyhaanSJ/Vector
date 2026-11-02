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
from vector.ui import ACCENT, AMBER, SummonBar, describe_step  # noqa: F401  (describe_step re-exported)

log = logging.getLogger("vector.app")


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
        self.bar = SummonBar(self.root, self.submit_typed, self.toggle_voice, hotkey_label,
                             on_escape=self.stop_all, on_toggle_aloud=self.toggle_aloud,
                             focus_mode=config.focus_mode)
        from vector.voice import Speaker

        self._reader = Speaker()  # reads typed replies aloud when voice mode is off
        self.read_aloud = config.read_aloud
        self.bar.set_aloud(self.read_aloud)
        self._busy = False
        self._speaking = False
        self._confirm_answer: Callable[[bool], None] | None = None
        self._esc = None
        self._tucked = False  # bar hidden so VECTOR can see/click the screen
        from vector.skills import screen as screen_skill

        screen_skill.hide_overlay = self._hide_for_screen

        if agent is None:
            from vector.agent import Vector
            from vector.brain import create_brain

            agent = Vector(config, create_brain(config))
        self.agent = agent
        self._show_model()
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

    # -- stopping -------------------------------------------------------------------------------
    def stop_all(self) -> None:
        """Esc: stop talking, cancel what VECTOR is doing, deny any pending Allow, hide the bar."""
        was_active = self._busy or self._speaking
        self.agent.cancel()
        if self._confirm_answer is not None:
            self._confirm_answer(False)
        self.stop_speaking()
        if self.bar.busy:
            self.bar.finish_request("Stopped.")
        self.bar.hide()
        if was_active:
            log.info("stopped by Esc")

    def _set_active(self) -> None:
        """While VECTOR is busy or talking, Esc stops it from anywhere; otherwise Esc is left alone."""
        active = self._busy or self._speaking
        if active and self._esc is None:
            from vector.hotkey import GlobalHotkey

            self._esc = GlobalHotkey("esc", lambda: self.ui(self.stop_all), allow_bare=True)
            if not self._esc.start():
                self._esc = None
        elif not active and self._esc is not None:
            self._esc.stop()
            self._esc = None

    def _hide_for_screen(self, hidden: bool) -> None:
        """Called (on the brain thread) right before VECTOR looks at or clicks the screen:
        get the bar out of the way first, so it isn't in the screenshot or under the mouse."""
        if not hidden or self._tucked:
            return
        done = threading.Event()

        def tuck():
            if self.bar.visible():
                self.bar.tuck()  # also lifts focus mode's dimming so VECTOR can see the desktop
                self._tucked = True
            done.set()

        self.ui(tuck)
        done.wait(1.5)
        if self._tucked:
            import time

            time.sleep(0.2)  # let Windows finish redrawing what was behind it

    def speak(self, text: str) -> None:
        """Say something out loud (blocks; call from a background thread). Esc cuts it off."""
        if not text:
            return
        self._speaking = True
        self.ui(self._set_active)
        try:
            if self.engine is not None:
                self.engine.say(text)     # mutes the mic while talking
            else:
                self._reader.say(text)
        except Exception:
            log.exception("speaking failed")
        finally:
            self._speaking = False
            self.ui(self._set_active)

    def speak_in_background(self, text: str) -> None:
        threading.Thread(target=self.speak, args=(text,), name="vector-read-aloud", daemon=True).start()

    def stop_speaking(self) -> None:
        self._reader.stop()
        if self.engine is not None:
            self.engine.stop_speaking()

    def toggle_aloud(self) -> None:
        """The small speaker button: read replies aloud on/off. Turning it on also reads the
        reply already on screen, for when you clicked too late."""
        self.read_aloud = not self.read_aloud
        self.bar.set_aloud(self.read_aloud)
        try:
            from vector.config import set_config_value

            set_config_value("read_aloud", "true" if self.read_aloud else "false")
        except OSError:
            log.exception("couldn't save read_aloud")
        if self.read_aloud:
            reply = self.bar.showing_reply()
            if reply and not self._speaking:
                self.speak_in_background(reply)
        else:
            self.stop_speaking()

    def submit_typed(self, text: str) -> None:
        self.bar.start_request(text, typed=True)
        self._requests.put((text, "typed", None))

    def ask(self, text: str, source: str = "typed") -> str | None:
        """Run a request on the brain thread and wait for the reply (used by voice).
        None if it was stopped with Esc."""
        done = threading.Event()
        box: list[str | None] = []
        self.ui(self.bar.start_request, text, source == "typed")
        self._requests.put((text, source, (done, box)))
        done.wait()
        return box[0] if box else None

    def _show_model(self) -> None:
        from vector.config import describe_model

        model = getattr(getattr(self.agent, "brain", None), "model", None) or self.config.resolved_model
        self.bar.set_model(describe_model(self.config.resolved_provider, model))

    def _worker(self) -> None:
        from vector.brain import BrainError, Cancelled

        while not self._quit.is_set():
            try:
                text, source, waiter = self._requests.get(timeout=0.5)
            except queue.Empty:
                continue
            self._current_source = source
            self._busy = True
            self.ui(self._set_active)
            error = False
            reply: str | None
            try:
                reply = self.agent.ask(text)
            except Cancelled:
                reply = None  # Esc: the bar already says "Stopped."
            except BrainError as exc:
                reply, error = str(exc), True
            except Exception as exc:  # never let one bad request kill the app
                log.exception("request failed")
                reply, error = f"Something went wrong: {exc}", True
            self._busy = False
            self.ui(self._set_active)
            if self._tucked:  # bring the bar back to show the answer
                self._tucked = False
                if reply is not None:
                    self.ui(self.bar.show, False)
            if reply is not None:
                self.ui(self.bar.finish_request, reply, error)
                if source == "voice":
                    self.ui(self.bar.hide_later, 9000)
                elif self.read_aloud:  # typed request with read-aloud on
                    self.speak_in_background(reply)
            self.ui(self._show_model)  # auto:free may have picked a different model
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

        self._confirm_answer = answer
        self.ui(self.bar.ask_confirm, name, args, answer)
        if self._current_source == "voice" and self.engine is not None:
            def by_voice():
                ask = ("Can I look at and control your screen?" if name == "use_your_screen"
                       else f"Can I run {name.replace('_', ' ')}?")
                self.speak(f"{ask} Say yes or no.")
                if decided.is_set():
                    return
                heard = self.engine.ask_yes_no(timeout=10, cancel=decided)
                if heard is not None:
                    answer(heard)
            threading.Thread(target=by_voice, daemon=True).start()
        if not decided.wait(timeout=120):
            answer(False)
        self._confirm_answer = None
        if self.engine is not None and not decided.is_set():
            self.engine.stop_speaking()
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
                    self.speak("Yes?")
                    command = engine.listen_once()
                    if not command:
                        self.ui(self.bar.set_status, "")
                        self.ui(self.bar.hide_later, 1500)
                        continue
                reply = self.ask(command, source="voice")
                if reply:  # None when stopped with Esc
                    self.speak(reply)
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
        from vector.ui import ASSETS

        try:
            img = Image.open(ASSETS / "tray.png")
        except OSError:
            img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
            ImageDraw.Draw(img).polygon([(32, 10), (54, 52), (10, 52)], outline=(92, 214, 234, 255),
                                        width=5)
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


def _windows_identity() -> None:
    """Tell Windows this is "VECTOR" (not Python), so it gets its own taskbar/notification identity."""
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("VECTOR.Assistant")
        except Exception:
            pass


def main(argv: list[str] | None = None) -> int:
    """Start the app. `--background` (used at login) starts without popping up the bar."""
    from vector.instance import InstanceServer, signal_running

    argv = sys.argv[1:] if argv is None else argv
    background = "--background" in argv
    config = load_config()
    if signal_running("voice" if background else "show"):
        return 0  # already running: it just popped up its bar
    _setup_logging(config)
    _windows_identity()
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
