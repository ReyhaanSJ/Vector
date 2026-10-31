"""The VECTOR agent: glues together the brain, the skills and the safety checks."""

from __future__ import annotations

import datetime as dt
import json
import platform
import sys
import traceback
from collections.abc import Callable
from pathlib import Path

from vector.brain import Brain
from vector.config import Config
from vector.registry import REGISTRY, Registry, load_builtin_skills, load_skill_dir

# confirm(tool_name, arguments) -> True to allow
Confirmer = Callable[[str, dict], bool]
# on_action(tool_name, arguments) - lets the UI show what VECTOR is doing
ActionHook = Callable[[str, dict], None]

SYSTEM_PROMPT = """\
You are VECTOR, a personal AI assistant that runs on {user}'s computer and can control it \
through the tools provided - in the spirit of a capable, loyal, slightly witty AI butler.

Computer: {os} | Home folder: {home} | Shell: {shell} | Now: {now}

How to behave:
- Act, don't just describe: when asked to do something on the computer, use the tools to do it.
- Chain tools when needed (e.g. find a file, then open it). Check results before claiming success.
- Keep replies short and spoken-friendly (1-3 sentences, no markdown tables), since they may \
be read aloud. Address the user as {user} occasionally, not every message.
- If a tool fails, say what went wrong plainly and suggest a fix.
- Some tools need the user's approval; if they decline, accept it and don't retry the same thing.
- Use `remember` when the user tells you a lasting preference or fact about themselves.
- Never delete, overwrite or close things the user didn't ask about.

Things you remember about {user}:
{memory}
"""


def _os_name() -> str:
    if platform.system() == "Windows":
        # Windows 11 still reports release "10"; build 22000+ is Windows 11.
        build = sys.getwindowsversion().build  # type: ignore[attr-defined]
        return f"Windows {'11' if build >= 22000 else '10'} (build {build})"
    return f"{platform.system()} {platform.release()}"


class Vector:
    def __init__(
        self,
        config: Config,
        brain: Brain,
        confirm: Confirmer | None = None,
        on_action: ActionHook | None = None,
        registry: Registry | None = None,
    ):
        self.config = config
        self.brain = brain
        self.confirm = confirm or (lambda name, args: False)
        self.on_action = on_action
        self.registry = registry or REGISTRY
        if registry is None:
            load_builtin_skills()
            user_dirs = [config.home / "skills", *map(Path, config.skill_dirs)]
            for directory in user_dirs:
                load_skill_dir(directory)

    def system_prompt(self) -> str:
        from vector.skills.productivity import memory_summary

        return SYSTEM_PROMPT.format(
            user=self.config.user_name,
            os=_os_name(),
            shell="PowerShell" if platform.system() == "Windows" else "sh/bash",
            home=Path.home(),
            # Date + hour only, so the prompt stays stable (cacheable) within the hour.
            now=dt.datetime.now().strftime("%A %d %B %Y, around %I %p"),
            memory=memory_summary() or "(nothing yet)",
        )

    def execute(self, name: str, args: dict) -> tuple[str, bool]:
        t = self.registry.get(name)
        if t is None:
            return f"Unknown tool '{name}'.", True
        if self.on_action:
            self.on_action(name, args)
        if t.dangerous and self.config.confirm_dangerous and not self.confirm(name, args):
            return "The user declined this action.", True
        try:
            result = t(**args)
        except TypeError as exc:
            return f"Bad arguments for {name}: {exc}", True
        except Exception as exc:
            return f"{name} failed: {exc}\n{traceback.format_exc(limit=2)}", True
        if not isinstance(result, str):
            result = json.dumps(result, default=str)
        return result, False

    def ask(self, text: str) -> str:
        return self.brain.respond(text, self.system_prompt(), self.registry.all(), self.execute)

    def reset(self) -> None:
        self.brain.reset()
