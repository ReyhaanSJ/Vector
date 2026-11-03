"""The VECTOR agent: glues together the brain, the skills and the safety checks."""

from __future__ import annotations

import datetime as dt
import json
import platform
import sys
import threading
import traceback
from collections.abc import Callable
from pathlib import Path

from vector.brain import Brain
from vector.config import Config
from vector.registry import REGISTRY, Registry, ToolOutput, load_builtin_skills, load_skill_dir

# Name used when asking for the once-per-request screen OK (the UIs show a friendly message for it).
SCREEN_PERMISSION = "use_your_screen"

# confirm(tool_name, arguments) -> True to allow
Confirmer = Callable[[str, dict], bool]
# on_action(tool_name, arguments) - lets the UI show what VECTOR is doing
ActionHook = Callable[[str, dict], None]

SYSTEM_PROMPT = """\
You are VECTOR, a personal AI assistant that runs on {user}'s computer and can control it \
through the tools provided - in the spirit of a capable, loyal, slightly witty AI butler.

Computer: {os} | Home folder: {home} | Shell: {shell}
Each request starts with a [Context: ...] line giving the current date and time; it comes \
from VECTOR, not from the user.

How to behave:
- Act, don't just describe: when asked to do something on the computer, use the tools to do it.
- Chain tools when needed (e.g. find a file, then open it). Check results before claiming success.
- Keep replies short and spoken-friendly (1-3 sentences, no markdown tables), since they may \
be read aloud. Address the user as {user} occasionally, not every message.
- If a tool fails, say what went wrong plainly and suggest a fix.
- Some tools need the user's approval; if they decline, accept it and don't retry the same thing.
- Use `remember` when the user tells you a lasting preference or fact about themselves.
- Never delete, overwrite or close things the user didn't ask about.
- You can see the screen (look_at_screen) and control it (click, scroll, type_text, press_keys).
  For on-screen tasks: look first, act, then look again to check it worked. Click coordinates
  are pixels in the latest screenshot. Prefer direct skills (open_app, open_website) when they fit.
- You have the internet: search_web finds pages and fetch_webpage reads them. Use them for
  facts, news, prices or anything you don't know, and say where the information came from.

Things you remember about {user}:
{memory}
"""


def _os_name() -> str:
    if platform.system() == "Windows":
        # Windows 11 still reports release "10"; build 22000+ is Windows 11.
        build = sys.getwindowsversion().build  # type: ignore[attr-defined]
        return f"Windows {'11' if build >= 22000 else '10'} (build {build})"
    if platform.system() == "Darwin":
        version = platform.mac_ver()[0] or platform.release()
        return (f"macOS {version} ({platform.machine()}). Keyboard shortcuts use the command key: "
                "press_keys('command+c'), not ctrl")
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
        self._cancel = threading.Event()
        self._screen_ok = False
        self._system: str | None = None
        self._memory_seen: str | None = None
        if registry is None:
            load_builtin_skills()
            user_dirs = [config.home / "skills", *map(Path, config.skill_dirs)]
            for directory in user_dirs:
                load_skill_dir(directory)

    def system_prompt(self) -> str:
        """The instructions for the AI. They stay exactly the same for a whole conversation:
        Claude's saved reasoning is tied to them, and changing them mid-chat makes Claude reject
        the request. (It also keeps the prompt cache warm.) Things that change - the time, what
        VECTOR remembers - travel with each request instead (see request_context)."""
        if self._system is None:
            from vector.skills.productivity import memory_summary

            self._memory_seen = memory_summary() or "(nothing yet)"
            self._system = SYSTEM_PROMPT.format(
                user=self.config.user_name,
                os=_os_name(),
                shell="PowerShell" if platform.system() == "Windows" else "sh/bash",
                home=Path.home(),
                memory=self._memory_seen,
            )
        return self._system

    def request_context(self) -> str:
        """A short line sent with each request: the time now, and memory if it changed."""
        from vector.skills.productivity import memory_summary

        now = dt.datetime.now().strftime("%A %d %B %Y, %I:%M %p").replace(" 0", " ")
        parts = [f"it is {now}"]
        memory = memory_summary() or "(nothing yet)"
        if self._memory_seen is not None and memory != self._memory_seen:
            parts.append(f"what you remember about {self.config.user_name} is now: {memory}")
            self._memory_seen = memory
        return "[Context: " + "; ".join(parts) + "]"

    def cancel(self) -> None:
        """Stop the current request: no further skills run and its reply is dropped."""
        self._cancel.set()

    @property
    def cancelled(self) -> bool:
        return self._cancel.is_set()

    def execute(self, name: str, args: dict) -> tuple[str, bool]:
        from vector.brain import Cancelled

        if self._cancel.is_set():
            raise Cancelled()
        t = self.registry.get(name)
        if t is None:
            return f"Unknown tool '{name}'.", True
        if self.on_action:
            self.on_action(name, args)
        if t.screen and not self._screen_ok:
            mode = self.config.screen_access.lower()
            if mode == "never":
                return ("Screen access is turned off. The user can allow it with: "
                        "vector --set screen_access=ask"), True
            if mode != "always" and not self.confirm(SCREEN_PERMISSION, {"for": "this request"}):
                if self._cancel.is_set():
                    raise Cancelled()
                return "The user didn't allow screen access for this request.", True
            self._screen_ok = True
        if t.dangerous and self.config.confirm_dangerous and not self.confirm(name, args):
            if self._cancel.is_set():
                raise Cancelled()
            return "The user declined this action.", True
        try:
            result = t(**args)
        except TypeError as exc:
            return f"Bad arguments for {name}: {exc}", True
        except Exception as exc:
            return f"{name} failed: {exc}\n{traceback.format_exc(limit=2)}", True
        if isinstance(result, ToolOutput):
            return result, False
        if not isinstance(result, str):
            result = json.dumps(result, default=str)
        return result, False

    def ask(self, text: str) -> str:
        from vector.brain import Cancelled

        self._cancel.clear()
        self._screen_ok = False  # the screen OK lasts for one request
        system = self.system_prompt()
        request = f"{self.request_context()}\n{text}"
        reply = self.brain.respond(request, system, self.registry.all(), self.execute)
        if self._cancel.is_set():  # stopped while the AI was still answering
            raise Cancelled()
        return reply

    def reset(self) -> None:
        self.brain.reset()
        self._system = None  # a fresh conversation picks up new settings and memory
