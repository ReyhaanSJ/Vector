# Contributing to VECTOR

Thanks for helping build VECTOR!

## Setup

```bash
git clone https://github.com/reyhaansj/vector.git && cd vector
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest
ruff check .
```

## Ways to help

- **New skills.** The easiest place to start. Add a function to the right file in `vector/skills/`
  (or a new module, imported in `vector/skills/__init__.py`). See [docs/skills.md](docs/skills.md).
- **Cross-platform fixes.** Many skills have per-OS code. If something doesn't work on your OS, open an issue or PR.
- **New AI providers.** Subclass `vector.brain.base.Brain` and register it in `vector/brain/__init__.py`.
- **Docs, bug reports, ideas.** All welcome.

## Guidelines

- Mark any skill that modifies, deletes, sends or types something with `@tool(dangerous=True)`.
- Skills should return a short, human-readable string and fail gracefully, with no uncaught exceptions for common problems.
- Optional heavy dependencies should be imported inside the function and give a helpful install hint if missing.
- Add a test for logic that can run without a real desktop (see `tests/`).
- Keep PRs focused; describe what you tested and on which OS.
