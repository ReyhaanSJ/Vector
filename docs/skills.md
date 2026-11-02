# Writing skills

A skill is a normal Python function decorated with `@tool`:

```python
from typing import Literal
from vector import tool

@tool
def convert_temperature(value: float, to: Literal["celsius", "fahrenheit"] = "celsius") -> str:
    """Convert a temperature between Celsius and Fahrenheit.

    value: The temperature to convert.
    to: Which unit to convert into.
    """
    result = (value - 32) * 5 / 9 if to == "celsius" else value * 9 / 5 + 32
    return f"{result:.1f} degrees {to}"
```

How it's turned into a tool for the AI:

| Source | Becomes |
|---|---|
| function name | tool name |
| first paragraph of the docstring | tool description (the AI reads this to decide when to use it) |
| `param: text` lines in the docstring | parameter descriptions |
| type hints (`str`, `int`, `float`, `bool`, `list[str]`, `Literal[...]`) | JSON schema types |
| parameters without defaults | required inputs |

## Tips

- **Write the docstring for the AI.** Say what it does and when to use it.
- **Return text.** Whatever you return is shown to the AI, which then answers the user. Keep it short.
- **`dangerous=True`** for anything irreversible or outward-facing; VECTOR will ask the user first.
- **Don't raise for expected failures.** Return a helpful message like `"No file called X"`.

## Where to put skills

- Personal skills: `~/.vector/skills/*.py` (loaded automatically)
- Extra folders: list them in `skill_dirs` in `~/.vector/config.toml`
- Built in (for a PR): `vector/skills/`
