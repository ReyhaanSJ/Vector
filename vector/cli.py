"""Command-line interface.

    vector                      chat by typing
    vector --voice              hands-free: say "Vector, ..." to give a command
    vector "open spotify"       run a single command and exit
    vector --setup              create ~/.vector/config.toml
    vector --list-skills        show everything VECTOR can do
    vector --selftest           check that everything works on this computer
    vector --app                background app: summon bar + say "Vector, ..." anywhere
    vector --startup on         start the VECTOR app when you log in (Windows and macOS)
    vector --phone              use VECTOR and see this screen from your phone (VECTOR Remote)
"""

from __future__ import annotations

import argparse
import os
import sys

from vector import __version__
from vector.config import config_path, load_config, write_default_config

if sys.platform == "win32":
    os.system("")  # turn on colour codes in older Windows consoles
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

# Colours from the VECTOR design (24-bit; Windows Terminal and modern consoles support them).
CYAN = "\033[38;2;92;214;234m"
DIM = "\033[38;2;139;152;165m"
YELLOW = "\033[38;2;242;184;75m"
RED = "\033[38;2;242;139;130m"
BOLD = "\033[1m"
RESET = "\033[0m"
if not sys.stdout.isatty() or os.environ.get("NO_COLOR"):
    CYAN = DIM = YELLOW = RED = BOLD = RESET = ""

MARK = "\u25b3"   # the VECTOR triangle
PROMPT = "\u203a"  # ›


def banner(model: str = "") -> str:
    details = " \u00b7 ".join(x for x in (model, "/help", "/exit") if x)
    return (f"\n  {CYAN}{MARK}{RESET}  {BOLD}V E C T O R{RESET}  {DIM}{__version__}{RESET}\n"
            f"     {DIM}{details}{RESET}\n")


HELP = f"""
  {BOLD}Commands{RESET}
  {CYAN}/help{RESET}     this help
  {CYAN}/skills{RESET}   everything VECTOR can do
  {CYAN}/model{RESET}    which AI is answering
  {CYAN}/aloud{RESET}    read replies out loud on/off (Ctrl+C stops reading)
  {CYAN}/guide{RESET}    the illustrated guide
  {CYAN}/uninstall{RESET} remove VECTOR (you can keep your data)
  {CYAN}/reset{RESET}    start a fresh conversation (long-term memory is kept)
  {CYAN}/exit{RESET}     quit

  {DIM}Anything else is a request, e.g. "open vscode and my downloads folder".{RESET}
"""


def say(text: str) -> None:
    """Print VECTOR's reply, wrapped neatly under the triangle mark."""
    import shutil
    import textwrap

    width = max(40, min(shutil.get_terminal_size((100, 20)).columns, 110) - 4)
    lines = []
    for para in text.splitlines() or [""]:
        lines.extend(textwrap.wrap(para, width) or [""])
    print(f"\n{CYAN}{MARK}{RESET} " + "\n  ".join(lines) + "\n")


def error(text: str) -> None:
    print(f"  {RED}\u2715 {text}{RESET}")


def _fmt_args(args: dict) -> str:
    parts = []
    for k, v in args.items():
        s = repr(v)
        parts.append(f"{k}={s if len(s) < 80 else s[:77] + '...'}")
    return ", ".join(parts)


def _describe_ask(name: str, args: dict) -> str:
    if name == "use_your_screen":
        return "see and control your screen for this request"
    return f"{name}({_fmt_args(args)})"


def terminal_confirm(name: str, args: dict) -> bool:
    print(f"  {YELLOW}! Needs your OK{RESET}  {_describe_ask(name, args)}")
    try:
        answer = input(f"    {YELLOW}Allow?{RESET} {DIM}y = yes, Enter = no{RESET} {CYAN}{PROMPT}{RESET} ")
    except EOFError:
        return False
    allowed = answer.strip().lower() in {"y", "yes"}
    print(f"    {DIM}{'allowed' if allowed else 'skipped'}{RESET}")
    return allowed


def show_action(name: str, args: dict) -> None:
    from vector.ui import describe_step

    print(f"  {DIM}\u00b7 {describe_step(name, args)}{RESET}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="vector", description="VECTOR - an AI assistant for your laptop.")
    p.add_argument("request", nargs="*", help="a one-off request, e.g. vector open spotify")
    p.add_argument("--app", action="store_true",
                   help="start the background app: summon bar (Ctrl+Shift+Space) and hands-free voice")
    p.add_argument("--voice", action="store_true", help="hands-free voice mode in this terminal")
    p.add_argument("--prepare-voice", action="store_true",
                   help="download the offline speech models now (~200 MB, once)")
    p.add_argument("--provider", help="ollama, openrouter, anthropic or auto (overrides config)")
    p.add_argument("--update", nargs="?", const="latest", metavar="VERSION",
                   help="install the newest VECTOR (or a specific version, e.g. --update 0.2.0)")
    p.add_argument("--versions", action="store_true", help="list every VECTOR version")
    p.add_argument("--models", action="store_true", help="list the AI models you can use right now")
    p.add_argument("--guide", action="store_true", help="show the illustrated guide")
    p.add_argument("--phone", action="store_true",
                   help="use VECTOR from your phone: shows the QR code to scan (VECTOR Remote)")
    p.add_argument("--uninstall", action="store_true", help="remove VECTOR (you can keep your data)")
    p.add_argument("--set", metavar="KEY=VALUE", action="append",
                   help="save a setting, e.g. --set model=qwen2.5:7b or --set user_name=Ray")
    p.add_argument("--model", help="model name (overrides config)")
    p.add_argument("--yes", action="store_true", help="don't ask before risky actions (careful!)")
    p.add_argument("--setup", action="store_true", help="write a default config file")
    p.add_argument("--list-skills", action="store_true", help="list available skills")
    p.add_argument("--selftest", action="store_true", help="check that everything works on this computer")
    p.add_argument("--startup", choices=["on", "off", "terminal"],
                   help="start VECTOR at login (on = background app, terminal, off = remove)")
    p.add_argument("--version", action="version", version=f"VECTOR {__version__}")
    return p


def list_skills(vector) -> None:
    skills = vector.registry.all()
    width = max(len(t.name) for t in skills) + 2
    print(f"\n  {BOLD}{len(skills)} skills{RESET}  {DIM}{YELLOW}!{RESET}{DIM} = asks before running{RESET}\n")
    for t in skills:
        flag = f"{YELLOW}!{RESET}" if t.dangerous else " "
        desc = t.description if len(t.description) < 80 else t.description[:77] + "..."
        print(f"  {flag} {CYAN}{t.name:<{width}}{RESET}{DIM}{desc}{RESET}")
    print()


def model_name(vector) -> str:
    from vector.config import describe_model

    model = getattr(vector.brain, "model", None) or vector.config.resolved_model
    return describe_model(vector.config.resolved_provider, model)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.set:
        from vector.config import set_config_value

        for item in args.set:
            key, sep, value = item.partition("=")
            if not sep:
                print(f"{RED}Use KEY=VALUE, e.g. --set model=qwen2.5:7b{RESET}")
                return 1
            try:
                path = set_config_value(key.strip(), value.strip())
            except KeyError as exc:
                print(f"{RED}{exc.args[0]}{RESET}")
                return 1
            print(f"Saved {key.strip()} = {value.strip()}  ({path})")
        return 0

    if args.setup:
        path = write_default_config()
        print(f"Config file: {path}\nEdit it to set your name, AI provider and more.")
        return 0

    if args.startup:
        return set_startup(args.startup)

    if args.versions:
        return show_versions()

    if args.models:
        return show_models()

    if args.guide:
        from vector.guide import main as guide_main

        return guide_main()

    if args.phone:
        return pair_phone()

    if args.uninstall:
        return uninstall_from_terminal()

    if args.update:
        return run_update(args.update)

    if args.app:
        from vector.app import main as app_main

        return app_main([])

    if args.prepare_voice:
        return prepare_voice()

    config = load_config()
    if args.provider:
        config.provider = args.provider
    if args.model:
        config.model = args.model
    if args.yes:
        config.confirm_dangerous = False

    if args.selftest:
        from vector.selftest import run_selftest

        return run_selftest(config, interactive=sys.stdin.isatty())

    from vector.agent import Vector
    from vector.brain import BrainError, create_brain

    try:
        brain = create_brain(config)
    except BrainError as exc:
        print(f"{RED}{exc}{RESET}")
        return 1
    vector = Vector(config, brain, confirm=terminal_confirm, on_action=show_action)

    if args.list_skills:
        list_skills(vector)
        return 0

    if args.request:
        try:
            say(vector.ask(" ".join(args.request)))
        except BrainError as exc:
            error(str(exc))
            return 1
        return 0

    if args.voice:
        return voice_loop(vector)
    return text_loop(vector)


def pair_phone() -> int:
    """Ask the running VECTOR app to show its pairing QR code (the app serves the phone)."""
    from vector.instance import signal_running

    if signal_running("phone"):
        say("VECTOR is showing the QR code on your screen. Scan it with your phone's Camera.")
        return 0
    from vector.config import set_config_value
    from vector.remote import load_key, phone_url, qr_text

    set_config_value("phone_remote", "true")
    url = phone_url(load_key())
    print(qr_text(url))
    say("Open the VECTOR app (it serves your phone), then scan this with your phone's Camera:")
    print(f"  {url}\n")
    say("Your phone must be on the same Wi-Fi. iPhone: Share > Add to Home Screen to keep it.")
    return 0


def set_startup(mode: str) -> int:
    from vector import startup

    if not startup.supported():
        print("Start-at-login is set up for Windows and macOS so far. PRs welcome!")
        return 1
    if mode == "off":
        removed = startup.disable()
        print("VECTOR will no longer start at login." if removed else "VECTOR wasn't set to start at login.")
    else:
        path = startup.enable(app=(mode == "on"))
        print(f"VECTOR will start when you log in ({path}).\nUndo with: vector --startup off")
    return 0


def text_loop(vector) -> int:
    from vector.brain import BrainError
    from vector.voice import Speaker

    print(banner(model_name(vector)))
    if not config_path().exists():
        print(f"  {DIM}tip: run `vector --setup` to personalise VECTOR{RESET}\n")
    reader = Speaker()
    aloud = vector.config.read_aloud
    last_reply = ""
    while True:
        try:
            text = input(f"{CYAN}{PROMPT}{RESET} ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not text:
            continue
        cmd = text.lower()
        if cmd in {"/exit", "/quit", "exit", "quit"}:
            return 0
        if cmd == "/help":
            print(HELP)
            continue
        if cmd == "/skills":
            list_skills(vector)
            continue
        if cmd == "/guide":
            from vector.guide import open_guide, text_guide

            if not open_guide(vector.config.hotkey):
                print(text_guide(vector.config.hotkey))
            continue
        if cmd == "/uninstall":
            if uninstall_from_terminal() == 0:
                return 0
            continue
        if cmd == "/aloud":
            aloud = not aloud
            from vector.config import set_config_value

            set_config_value("read_aloud", "true" if aloud else "false")
            print(f"  {DIM}reading replies aloud: {'on' if aloud else 'off'}{RESET}\n")
            if aloud and last_reply:
                _read(reader, last_reply)
            continue
        if cmd == "/model":
            print(f"  {DIM}{model_name(vector)}  (change it: vector --models){RESET}\n")
            continue
        if cmd == "/reset":
            vector.reset()
            print(f"  {DIM}fresh conversation{RESET}\n")
            continue
        try:
            reply = vector.ask(text)
        except BrainError as exc:
            error(str(exc))
            print()
            continue
        except KeyboardInterrupt:
            print(f"  {DIM}(stopped){RESET}\n")
            continue
        say(reply)
        last_reply = reply
        if aloud:
            _read(reader, reply)


def uninstall_from_terminal() -> int:
    from vector import uninstall

    try:
        sure = input(f"  {YELLOW}Uninstall VECTOR?{RESET} {DIM}y = yes, Enter = cancel{RESET} {CYAN}{PROMPT}{RESET} ")
        if sure.strip().lower() not in {"y", "yes"}:
            print(f"  {DIM}cancelled{RESET}\n")
            return 1
        print(f"  {DIM}{uninstall.DATA_HELP}{RESET}")
        keep = input(f"  {YELLOW}Keep your data for next time?{RESET} {DIM}Enter = keep, d = delete{RESET} "
                     f"{CYAN}{PROMPT}{RESET} ")
    except (EOFError, KeyboardInterrupt):
        print(f"\n  {DIM}cancelled{RESET}\n")
        return 1
    try:
        uninstall.start(keep_data=keep.strip().lower() not in {"d", "delete"})
    except RuntimeError as exc:
        error(str(exc))
        return 1
    print(f"  {DIM}The uninstaller opened in a new window. Goodbye!{RESET}")
    return 0


def _read(reader, text: str) -> None:
    try:
        reader.say(text)
    except KeyboardInterrupt:
        print(f"  {DIM}(stopped reading){RESET}\n")


def show_models() -> int:
    from vector.brain import BrainError
    from vector.config import load_config

    config = load_config()
    provider = config.resolved_provider
    current = config.model or config.resolved_model
    try:
        if provider == "openrouter":
            from vector.brain.openai_compat import list_free_tool_models, pick_free_model

            models = list_free_tool_models()
            best = pick_free_model(models)
            print("Free OpenRouter models that can use VECTOR's skills (right now):")
            for m in models:
                tags = []
                if m == best:
                    tags.append("VECTOR's pick")
                if m == current:
                    tags.append("in use")
                print(f"  {m}" + (f"  {CYAN}<- {', '.join(tags)}{RESET}" if tags else ""))
            if current == "auto:free":
                print(f"{DIM}You're on auto:free, so VECTOR uses its pick automatically.{RESET}")
        elif provider == "ollama":
            import json
            import urllib.request

            with urllib.request.urlopen(f"{config.ollama_url}/api/tags", timeout=10) as resp:
                models = [m["name"] for m in json.loads(resp.read()).get("models", [])]
            print("AI models downloaded in Ollama:")
            for m in models:
                mark = f"  {CYAN}<- in use{RESET}" if m.split(":latest")[0] == current.split(":latest")[0] else ""
                print(f"  {m}{mark}")
            print(f"{DIM}Get more with: ollama pull <name>  (see https://ollama.com/library){RESET}")
        else:
            print(f"Using Claude ({current}). Models: claude-opus-5-5, claude-sonnet-5-5, claude-haiku-5-5")
    except BrainError as exc:
        print(f"{RED}{exc}{RESET}")
        return 1
    except OSError:
        print(f"{RED}Couldn't reach Ollama. Is it running?{RESET}")
        return 1
    print(f"{DIM}Switch with: vector --set model=<name>, then restart VECTOR.{RESET}")
    return 0


def show_versions() -> int:
    from vector import __version__
    from vector.updater import UpdateError, list_releases, same_version

    try:
        releases = list_releases(include_prereleases=True)
    except UpdateError as exc:
        print(f"{RED}{exc}{RESET}")
        return 1
    if not releases:
        print("No versions have been released yet.")
        return 0
    for r in releases:
        here = same_version(r.tag, __version__)
        mark = f"{CYAN}* installed{RESET}" if here else ""
        tag = " (preview)" if r.prerelease else ""
        headline = next((ln.replace("*", "").strip("# ").strip()
                         for ln in r.notes.splitlines() if ln.strip()), "")
        print(f"  {r.version:<10} {r.published}  {mark}{tag}")
        if headline:
            print(f"    {DIM}{headline[:90]}{RESET}")
    print(f"\n{DIM}Install one with: vector --update <version>{RESET}")
    return 0


def run_update(target: str) -> int:
    from vector import __version__
    from vector.updater import UpdateError, check_for_update, find_release, install_release

    try:
        if target == "latest":
            release = check_for_update(force=True)
            if release is None:
                print(f"You have the newest VECTOR ({__version__}).")
                return 0
        else:
            release = find_release(target)
        print(f"Installing VECTOR {release.version} (you have {__version__})...")
        install_release(release)
    except UpdateError as exc:
        print(f"{RED}{exc}{RESET}")
        return 1
    print("The installer opened in a new window. VECTOR restarts when it's done.")
    return 0


def prepare_voice() -> int:
    from vector.config import load_config
    from vector.voice import VoiceEngine, VoiceUnavailable, speech_models_present

    config = load_config()
    if speech_models_present(config.whisper_model):
        print("Already downloaded: speech models")
    else:
        print("Downloading the offline speech models (~200 MB, only needed once)...")
    try:
        VoiceEngine.prepare(config.whisper_model)
    except VoiceUnavailable as exc:
        print(f"{RED}{exc}{RESET}")
        return 1
    print("Voice is ready.")
    return 0


def voice_loop(vector) -> int:
    from vector.brain import BrainError
    from vector.voice import VoiceEngine, VoiceUnavailable

    wake = vector.config.wake_word
    print(banner(model_name(vector)))
    print(f"  {DIM}starting voice (the first time downloads ~200 MB of speech models)...{RESET}")
    try:
        engine = VoiceEngine(wake, vector.config.whisper_model, speak=vector.config.speak_replies)
        engine.start()
    except VoiceUnavailable as exc:
        print(f"{RED}{exc}{RESET}")
        return 1

    vector.confirm = lambda name, args: _voice_confirm(engine, name, args)
    print(f"  {DIM}just say \u201c{wake.title()}, ...\u201d  \u00b7  Ctrl+C to quit{RESET}\n")
    engine.say("Vector online.")
    try:
        while True:
            command = engine.listen_for_command(on_wake=lambda: print(f"  {CYAN}\u25cf{RESET} {DIM}listening{RESET}"))
            if command is None:
                continue
            if not command:
                engine.say("Yes?")
                command = engine.listen_once()
                if not command:
                    continue
            print(f"{CYAN}{PROMPT}{RESET} {command}")
            if command.lower().strip(" .!") in {"goodbye", "shut down", "exit", "quit", "stop listening"}:
                engine.say("Goodbye.")
                return 0
            try:
                reply = vector.ask(command)
            except BrainError as exc:
                reply = str(exc)
            say(reply)
            engine.say(reply)
    except VoiceUnavailable as exc:
        print(f"{RED}{exc}{RESET}")
        return 1
    except KeyboardInterrupt:
        print()
        return 0
    finally:
        engine.stop()


def _voice_confirm(engine, name: str, args: dict) -> bool:
    print(f"  {YELLOW}! Needs your OK{RESET}  {_describe_ask(name, args)}  {DIM}say yes or no{RESET}")
    engine.say(f"Can I run {name.replace('_', ' ')}? Say yes or no.")
    answer = engine.ask_yes_no(timeout=10)
    print(f"    {DIM}{'allowed' if answer else 'skipped'}{RESET}")
    return bool(answer)


if __name__ == "__main__":
    sys.exit(main())
