"""Built-in skills. Importing this package registers every tool with VECTOR."""

from vector.osutil import IS_WINDOWS
from vector.skills import apps, control, files, productivity, system  # noqa: F401

if IS_WINDOWS:
    from vector.skills import windows  # noqa: F401
