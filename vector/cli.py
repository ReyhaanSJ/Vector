"""Command-line interface.

    vector                      chat by typing
    vector --voice              hands-free: say "Vector, ..." to give a command
    vector "open spotify"       run a single command and exit
    vector --setup              create ~/.vector/config.toml
    vector --list-skills        show everything VECTOR can do
    vector --selftest           check that everything works on this computer
    vector --app                background app: summon bar + say "Vector, ..." anywhere
    vector --startup on         start the VECTOR app when you log in (Windows)
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

CYAN, DIM, YELLOW, RED, RESET = "\033[96m", "\033[2m", "\033[93m", "\033[91m", "\033[0m"
if not sys.stdout.isatty():
    CYAN = DIM = YELLOW = RED = RESET = ""

BANNER = rf"""{CYAN}
 __     _______ ____ _____ ___  ____
 \ \   / / ____/ ___|_   _/ _ \|  _ \
  \ \ / /|  _|| |     | || | | | |_) |
   \ V / | |__| |___  | || |_| |  _ <
    \_/  |_____\____| |_| \___/|_| \_\   v{__version__}
{RESET}{DIM}  your laptop, on command.  /help for commands{RESET}
"""

HELP = """Commands:
  /help     show this help
  /skills   list skills
  /reset    forget this conversation (long-term memory is kept)
  /exit     quit
Anything else is a request, e.g. "open vscode and my downloads folder"."""


def _fmt_args(args: dict) -> str:
    parts = []
    for k, v in args.items():
        s = repr(v)
        parts.append(f"{k}={s if len(s) < 80 else s[:77] + '...'}")
    return ", ".join(parts)


def terminal_confirm(name: str, args: dict) -> bool:
    print(f"{YELLOW}  ! VECTOR wants to run {name}({_fmt_args(args)}){RESET}")
    try:
        answer = input(f"{YELLOW}    Allow? [y/N] {RESET}").strip().lower()
    except EOFError:
        return False
    return answer in {"y", "yes"}


def show_action(name: str, args: dict) -> None:
    print(f"{DIM}  -> {name}({_fmt_args(args)}){RESET}")


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
    p.add_argument("--set", metavar="KEY=VALUE", action="append",
                   help="save a setting, e.g. --set model=qwen2.5:7b or --set user_name=Ray")
    p.add_argument("--model", help="model name (overrides config)")
    p.add_argument("--yes", action="store_true", help="don't ask before risky actions (careful!)")
    p.add_argument("--setup", action="store_true", help="write a default config file")
    p.add_argument("--list-skills", action="store_true", help="list available skills")
    p.add_argument("--selftest", action="store_true", help="check that everything works on this computer")
    p.add_argument("--startup", choices=["on", "off", "terminal"],
                   help="Windows: start VECTOR at login (on = background app, terminal, off = remove)")
    p.add_argument("--version", action="version", version=f"VECTOR {__version__}")
    return p


def list_skills(vector) -> None:
    for t in vector.registry.all():
        flag = f" {YELLOW}[asks first]{RESET}" if t.dangerous else ""
        print(f"  {CYAN}{t.name}{RESET}{flag}\n    {DIM}{t.description}{RESET}")


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
            print(vector.ask(" ".join(args.request)))
        except BrainError as exc:
            print(f"{RED}{exc}{RESET}")
            return 1
        return 0

    if args.voice:
        return voice_loop(vector)
    return text_loop(vector)


def set_startup(mode: str) -> int:
    from vector import startup

    if not startup.supported():
        print("Start-at-login is only set up for Windows so far. PRs welcome!")
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

    print(BANNER)
    if not config_path().exists():
        print(f"{DIM}  tip: run `vector --setup` to personalise VECTOR{RESET}\n")
    while True:
        try:
            text = input(f"{CYAN}you > {RESET}").strip()
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
        if cmd == "/reset":
            vector.reset()
            print(f"{DIM}  conversation cleared{RESET}")
            continue
        try:
            reply = vector.ask(text)
        except BrainError as exc:
            print(f"{RED}  {exc}{RESET}")
            continue
        except KeyboardInterrupt:
            print(f"{DIM}  (interrupted){RESET}")
            continue
        print(f"{CYAN}VECTOR >{RESET} {reply}\n")


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
    print(BANNER)
    print(f"{DIM}  starting voice (the first time downloads ~200 MB of speech models)...{RESET}")
    try:
        engine = VoiceEngine(wake, vector.config.whisper_model, speak=vector.config.speak_replies)
        engine.start()
    except VoiceUnavailable as exc:
        print(f"{RED}{exc}{RESET}")
        return 1

    vector.confirm = lambda name, args: _voice_confirm(engine, name, args)
    print(f"{DIM}  listening... just say \"{wake.title()}, <your request>\". Ctrl+C to quit.{RESET}")
    engine.say("Vector online.")
    try:
        while True:
            command = engine.listen_for_command(on_wake=lambda: print(f"{DIM}  (listening){RESET}"))
            if command is None:
                continue
            if not command:
                engine.say("Yes?")
                command = engine.listen_once()
                if not command:
                    continue
            print(f"{CYAN}you > {RESET}{command}")
            if command.lower().strip(" .!") in {"goodbye", "shut down", "exit", "quit", "stop listening"}:
                engine.say("Goodbye.")
                return 0
            try:
                reply = vector.ask(command)
            except BrainError as exc:
                reply = str(exc)
            print(f"{CYAN}VECTOR >{RESET} {reply}\n")
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
    print(f"{YELLOW}  ! VECTOR wants to run {name}({_fmt_args(args)}) - say yes or no{RESET}")
    engine.say(f"Can I run {name.replace('_', ' ')}? Say yes or no.")
    answer = engine.ask_yes_no(timeout=10)
    print(f"{DIM}    {'allowed' if answer else 'denied'}{RESET}")
    return bool(answer)


if __name__ == "__main__":
    sys.exit(main())
