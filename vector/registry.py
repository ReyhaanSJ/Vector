"""The skill registry: turns plain Python functions into tools the AI can call.

Writing a new skill is as simple as:

    from vector import tool

    @tool
    def say_hello(name: str) -> str:
        \"\"\"Greet someone by name.

        name: Who to greet.
        \"\"\"
        return f"Hello {name}!"

The function's docstring becomes the tool description (first paragraph) and the
`param: description` lines document each argument. Type hints become the JSON
schema. Mark anything that changes the system with `@tool(dangerous=True)` so
VECTOR asks the user before running it.
"""

from __future__ import annotations

import importlib.util
import inspect
import re
import sys
import types
import typing
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_JSON_TYPES = {str: "string", int: "integer", float: "number", bool: "boolean"}


@dataclass
class Tool:
    name: str
    description: str
    func: Callable[..., Any]
    parameters: dict
    dangerous: bool = False

    def schema(self) -> dict:
        """Tool definition in the shape the Claude Messages API expects."""
        return {"name": self.name, "description": self.description, "input_schema": self.parameters}

    def __call__(self, **kwargs):
        return self.func(**kwargs)


def _json_type(annotation) -> dict:
    origin = typing.get_origin(annotation)
    args = typing.get_args(annotation)
    if origin in (typing.Union, types.UnionType):
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1:
            return _json_type(non_none[0])
    if origin is typing.Literal:
        return {"type": _JSON_TYPES.get(type(args[0]), "string"), "enum": list(args)}
    if origin in (list, tuple, set) or annotation in (list, tuple, set):
        item = _json_type(args[0]) if args else {"type": "string"}
        return {"type": "array", "items": item}
    if annotation in _JSON_TYPES:
        return {"type": _JSON_TYPES[annotation]}
    return {"type": "string"}


def _parse_docstring(doc: str, param_names: set[str]) -> tuple[str, dict[str, str]]:
    doc = inspect.cleandoc(doc or "")
    summary_lines, params = [], {}
    in_summary = True
    for line in doc.splitlines():
        match = re.match(r"^\s*(\w+)\s*(?:\([^)]*\))?\s*:\s*(.+)$", line)
        if match and match.group(1) in param_names:
            params[match.group(1)] = match.group(2).strip()
            in_summary = False
        elif in_summary:
            if not line.strip() and summary_lines:
                in_summary = False
            elif line.strip():
                summary_lines.append(line.strip())
    return " ".join(summary_lines), params


def build_tool(func: Callable, name: str | None = None, dangerous: bool = False) -> Tool:
    signature = inspect.signature(func)
    description, param_docs = _parse_docstring(func.__doc__ or "", set(signature.parameters))
    hints = typing.get_type_hints(func)
    properties, required = {}, []
    for pname, param in signature.parameters.items():
        if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
            continue
        prop = _json_type(hints.get(pname, str))
        if pname in param_docs:
            prop["description"] = param_docs[pname]
        if param.default is inspect.Parameter.empty:
            required.append(pname)
        elif param.default is not None:
            prop["default"] = param.default
        properties[pname] = prop
    schema = {"type": "object", "properties": properties, "required": required}
    return Tool(
        name=name or func.__name__,
        description=description or func.__name__.replace("_", " "),
        func=func,
        parameters=schema,
        dangerous=dangerous,
    )


class Registry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, t: Tool) -> Tool:
        self._tools[t.name] = t
        return t

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def all(self) -> list[Tool]:
        return sorted(self._tools.values(), key=lambda t: t.name)

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def __len__(self) -> int:
        return len(self._tools)


REGISTRY = Registry()


def tool(func: Callable | None = None, *, name: str | None = None, dangerous: bool = False):
    """Decorator that registers a function as a VECTOR skill."""

    def wrap(f: Callable) -> Callable:
        REGISTRY.register(build_tool(f, name=name, dangerous=dangerous))
        return f

    return wrap(func) if func is not None else wrap


def load_builtin_skills() -> None:
    from vector import skills  # noqa: F401  (importing registers the tools)


def load_skill_dir(directory: str | Path) -> list[str]:
    """Import every *.py file in a folder so its @tool functions register."""
    loaded = []
    directory = Path(directory).expanduser()
    if not directory.is_dir():
        return loaded
    for path in sorted(directory.glob("*.py")):
        if path.name.startswith("_"):
            continue
        mod_name = f"vector_user_skill_{path.stem}"
        spec = importlib.util.spec_from_file_location(mod_name, path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            sys.modules[mod_name] = module
            try:
                spec.loader.exec_module(module)
                loaded.append(path.name)
            except Exception as exc:  # a broken user skill must not crash VECTOR
                print(f"[vector] could not load skill {path.name}: {exc}", file=sys.stderr)
    return loaded
