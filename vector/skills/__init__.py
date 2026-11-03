"""Built-in skills. Importing this package registers every tool with VECTOR."""

from vector.osutil import IS_MAC, IS_WINDOWS
from vector.skills import apps, control, files, productivity, screen, system, web  # noqa: F401

if IS_WINDOWS:
    from vector.skills import windows  # noqa: F401
elif IS_MAC:
    from vector.skills import mac  # noqa: F401
