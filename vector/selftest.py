"""`vector --selftest`: check that the basics work on this computer.

Every check is safe: nothing is deleted, and anything changed (clipboard, volume,
memory, files) is put back afterwards. Checks that pop something up on screen
(an app, a notification, a spoken sentence) ask first.
"""

from __future__ import annotations

import platform
import sys
import tempfile
import time
import traceback
from collections.abc import Callable
from pathlib import Path

GREEN, RED, YELLOW, DIM, RESET = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[0m"
if not sys.stdout.isatty():
    GREEN = RED = YELLOW = DIM = RESET = ""


class Skip(Exception):
    pass


def _ask(question: str, interactive: bool) -> bool:
    if not interactive:
        return False
    try:
        return input(f"    {question} [y/N] ").strip().lower() in {"y", "yes"}
    except EOFError:
        return False


# ---- individual checks: return a short detail string, raise Skip or any error ----

def check_python() -> str:
    return f"Python {platform.python_version()} on {platform.system()} {platform.release()}"


def check_skills() -> str:
    from vector.registry import REGISTRY, load_builtin_skills

    load_builtin_skills()
    return f"{len(REGISTRY)} skills loaded"


def check_system_status() -> str:
    from vector.skills.system import system_status

    out = system_status()
    battery = next((line for line in out.splitlines() if line.startswith("Battery")), "no battery info")
    return battery


def check_folders() -> str:
    from vector.osutil import personal_folders

    folders = personal_folders()
    missing = [name for name in ("desktop", "documents", "downloads") if not folders[name].exists()]
    if missing:
        raise RuntimeError(f"can't find: {', '.join(missing)} (looked in {folders[missing[0]]})")
    return f"Downloads = {folders['downloads']}"


def check_files() -> str:
    from vector.skills import files

    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "vector-selftest.txt"
        files.write_text_file(str(target), "hello")
        assert files.read_text_file(str(target)) == "hello", "read back wrong text"
        assert "vector-selftest.txt" in files.find_files("selftest", tmp), "find_files missed it"
        assert "Would move" in files.organize_folder(tmp, dry_run=True)
    return "write, read, find, organize (dry run)"


def check_memory() -> str:
    from vector.skills import productivity

    marker = f"selftest marker {time.time()}"
    productivity.remember(marker)
    try:
        assert marker in productivity.recall("selftest marker"), "recall failed"
    finally:
        productivity.forget(marker)
    return f"saved in {productivity.MEMORY_FILE}"


def check_clipboard() -> str:
    import pyperclip

    try:
        original = pyperclip.paste()
    except pyperclip.PyperclipException as exc:
        raise Skip(f"no clipboard access ({str(exc).splitlines()[0][:70]})") from exc
    try:
        pyperclip.copy("vector selftest")
        assert pyperclip.paste() == "vector selftest", "clipboard didn't round-trip"
    finally:
        pyperclip.copy(original)
    return "copy + paste work (your clipboard was restored)"


def check_shell() -> str:
    from vector.skills.system import run_shell_command

    out = run_shell_command("echo vector-ok")
    assert "vector-ok" in out, out
    return "PowerShell" if platform.system() == "Windows" else "shell"


def check_start_menu() -> str:
    if platform.system() == "Darwin":
        return check_mac_apps()
    if platform.system() != "Windows":
        raise Skip("Windows and macOS only")
    from vector.skills.apps import best_app_match, windows_start_apps

    apps = windows_start_apps()
    if not apps:
        raise RuntimeError("Get-StartApps returned nothing")
    found = [q for q in ("calculator", "notepad", "edge") if best_app_match(q, apps)]
    return f"{len(apps)} apps found; recognises {', '.join(found) or 'none of calculator/notepad/edge'}"


def check_mac_apps() -> str:
    if platform.system() != "Darwin":
        raise Skip("macOS only")
    from vector.skills.apps import best_app_match, mac_apps

    apps = mac_apps()
    if not apps:
        raise RuntimeError("found no apps in /Applications")
    found = [q for q in ("calculator", "safari", "textedit") if best_app_match(q, apps)]
    return f"{len(apps)} apps found; recognises {', '.join(found) or 'none of calculator/safari/textedit'}"


def check_mac_shortcut() -> str:
    if platform.system() != "Darwin":
        raise Skip("macOS only")
    from vector.macos import CarbonHotkey

    hotkey = CarbonHotkey("ctrl+alt+shift+f12", lambda: None)
    error = hotkey.register()
    if error:
        raise RuntimeError(error)
    hotkey.unregister()
    return "global shortcuts can be registered (no extra permission needed)"


def check_mac_volume() -> str:
    if platform.system() != "Darwin":
        raise Skip("macOS only")
    from vector.osutil import run

    out = run(["osascript", "-e", "output volume of (get volume settings)"]).stdout.strip()
    if not out.isdigit():
        raise Skip(f"no speakers to control ({out or 'no answer'})")
    original = int(out)
    target = original - 1 if original > 5 else 5
    try:
        run(["osascript", "-e", f"set volume output volume {target}"])
        now = run(["osascript", "-e", "output volume of (get volume settings)"]).stdout.strip()
        assert now.isdigit() and abs(int(now) - target) <= 1, f"volume didn't change ({now})"
    finally:
        run(["osascript", "-e", f"set volume output volume {original}"])
    return f"exact control works (left at {original}%)"


def check_volume() -> str:
    if platform.system() == "Darwin":
        return check_mac_volume()
    if platform.system() != "Windows":
        raise Skip("Windows and macOS only")
    from vector.skills.system import windows_endpoint_volume

    endpoint = windows_endpoint_volume()
    original = endpoint.GetMasterVolumeLevelScalar()
    from vector.skills.system import set_volume

    try:
        set_volume(int(original * 100) - 1 if original > 0.05 else 5)
        changed = endpoint.GetMasterVolumeLevelScalar()
        assert abs(changed - original) > 0.001, "volume didn't change"
    finally:
        endpoint.SetMasterVolumeLevelScalar(original, None)
    return f"exact control works (left at {original * 100:.0f}%)"


def check_keyboard_control() -> str:
    try:
        import pyautogui  # noqa: F401
    except ImportError as exc:
        raise Skip("pyautogui not installed (pip install -e \".[control]\")") from exc
    except Exception as exc:
        raise Skip(f"no display: {exc}") from exc
    return "pyautogui ready (typing / shortcuts / media keys)"


def check_open_app(interactive: bool) -> str:
    if not _ask("Open Calculator to test app launching?", interactive):
        raise Skip("skipped")
    from vector.skills.apps import open_app

    out = open_app("calculator")
    if "Couldn't" in out:
        raise RuntimeError(out)
    return out + " (close it yourself)"


def check_notification(interactive: bool) -> str:
    if not _ask("Show a test notification?", interactive):
        raise Skip("skipped")
    from vector.osutil import notify

    if not notify("VECTOR", "Self-test notification. If you can see this, notifications work!"):
        raise RuntimeError("no notification method worked")
    return "sent - check it appeared"


def check_voice(interactive: bool) -> str:
    try:
        import faster_whisper  # noqa: F401
        import sounddevice as sd
        import vosk  # noqa: F401
    except (ImportError, OSError) as exc:
        raise Skip('voice packages not installed (pip install -e ".[voice]")') from exc
    inputs = [d for d in sd.query_devices() if d.get("max_input_channels", 0) > 0]
    if not inputs:
        raise RuntimeError("no microphone found")
    detail = f"{len(inputs)} microphone(s)"
    if _ask('Test hands-free voice? (say "Vector, what time is it" when asked)', interactive):
        from vector.config import load_config
        from vector.voice import VoiceEngine

        config = load_config()
        print("    Loading speech models (first time downloads ~200 MB)...")
        with VoiceEngine(config.wake_word, config.whisper_model) as engine:
            engine.say("Say: Vector, what time is it.")
            print("    Listening for 15 seconds...")
            stop = __import__("threading").Event()
            timer = __import__("threading").Timer(15, stop.set)
            timer.start()
            heard = engine.listen_for_command(stop=stop)
            timer.cancel()
        if heard is None:
            raise RuntimeError("didn't hear \"Vector\" - check mic permissions "
                               f"({'docs/macos.md' if platform.system() == 'Darwin' else 'docs/windows.md'})")
        detail += f'; wake word OK, heard: "{heard}"'
    return detail


_brain_ok = False


def check_brain(config) -> str:
    global _brain_ok
    from vector.brain import create_brain
    from vector.registry import Registry

    brain = create_brain(config)
    reply = brain.respond(
        "This is a connection test. Reply with exactly: VECTOR ONLINE",
        "You are a connection test. Follow the instruction exactly.",
        Registry().all(),
        lambda name, args: ("no tools in the self-test", True),
    )
    if "ONLINE" not in reply.upper():
        raise RuntimeError(f"unexpected reply: {reply[:80]}")
    _brain_ok = True
    return f"{config.resolved_provider} / {config.resolved_model} answered"


def check_agent_uses_tools(config) -> str:
    if not _brain_ok:
        raise Skip("needs a working AI brain (see above)")
    from vector.agent import Vector
    from vector.brain import create_brain

    used = []
    agent = Vector(config, create_brain(config), confirm=lambda n, a: False,
                   on_action=lambda name, args: used.append(name))
    agent.ask("What time is it right now? Use your tool to check.")
    if "current_time" not in used:
        raise RuntimeError(f"AI didn't call the clock skill (called: {used or 'nothing'})")
    return "AI picked and ran a skill by itself"


def run_selftest(config, interactive: bool = True) -> int:
    from vector.brain import BrainError
    from vector.skills.system import NoAudioDevice

    checks: list[tuple[str, Callable[[], str]]] = [
        ("Python version", check_python),
        ("Skills load", check_skills),
        ("System status", check_system_status),
        ("Personal folders", check_folders),
        ("Files", check_files),
        ("Long-term memory", check_memory),
        ("Clipboard", check_clipboard),
        ("Shell commands", check_shell),
        ("Applications" if platform.system() == "Darwin" else "Start menu apps", check_start_menu),
        ("Global shortcut", check_mac_shortcut),
        ("Volume control", check_volume),
        ("Keyboard control", check_keyboard_control),
        ("AI brain connection", lambda: check_brain(config)),
        ("AI uses skills", lambda: check_agent_uses_tools(config)),
        ("Open an app", lambda: check_open_app(interactive)),
        ("Notifications", lambda: check_notification(interactive)),
        ("Voice", lambda: check_voice(interactive)),
    ]
    print("\nVECTOR self-test\n")
    passed = failed = skipped = 0
    failures = []
    for name, fn in checks:
        print(f"  {name:<22}", end="", flush=True)
        try:
            detail = fn()
            print(f"{GREEN}PASS{RESET}  {DIM}{detail}{RESET}")
            passed += 1
        except Skip as exc:
            print(f"{YELLOW}SKIP{RESET}  {DIM}{exc}{RESET}")
            skipped += 1
        except Exception as exc:
            msg = str(exc) or exc.__class__.__name__
            print(f"{RED}FAIL{RESET}  {msg}")
            # Our own friendly errors already say what to do; only keep tracebacks for surprises.
            if not isinstance(exc, (BrainError, NoAudioDevice)):
                failures.append((name, traceback.format_exc()))
            failed += 1
    print(f"\n  {passed} passed, {failed} failed, {skipped} skipped")
    if failures:
        print(f"\n{DIM}Details (paste these when reporting a problem):{RESET}")
        for name, tb in failures:
            print(f"\n--- {name} ---\n{tb.strip()}")
    return 1 if failed else 0
