"""Give VECTOR's own programs (vector.exe, vector-app.exe) the VECTOR icon.

Python's installer creates those launchers without an icon, so Windows shows its generic
"blank program" picture for them (Task Manager, Startup apps, pinned taskbar buttons).
Setup runs this to write the icon into them:

    python -m vector.winicon
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

RT_ICON = 3
RT_GROUP_ICON = 14
ICON = Path(__file__).parent / "assets" / "icon.ico"


def parse_ico(data: bytes) -> list[tuple[bytes, bytes]]:
    """Split an .ico file into (14-byte group entry without id, image bytes) per size."""
    reserved, kind, count = struct.unpack_from("<HHH", data, 0)
    if reserved != 0 or kind != 1 or count == 0:
        raise ValueError("not an .ico file")
    images = []
    for i in range(count):
        w, h, colors, res, planes, bits, size, offset = struct.unpack_from("<BBBBHHII", data, 6 + 16 * i)
        entry = struct.pack("<BBBBHHI", w, h, colors, res, planes, bits, size)
        images.append((entry, data[offset:offset + size]))
    return images


def group_icon(images: list[tuple[bytes, bytes]]) -> bytes:
    """The RT_GROUP_ICON resource that lists every size (ids 1..n)."""
    out = struct.pack("<HHH", 0, 1, len(images))
    for i, (entry, _) in enumerate(images, 1):
        out += entry + struct.pack("<H", i)
    return out


def set_exe_icon(exe: Path, ico: Path = ICON) -> None:
    """Write the icon into an .exe's resources (Windows only)."""
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.BeginUpdateResourceW.restype = wintypes.HANDLE
    kernel32.BeginUpdateResourceW.argtypes = [wintypes.LPCWSTR, wintypes.BOOL]
    kernel32.UpdateResourceW.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.LPVOID,
                                         wintypes.WORD, wintypes.LPVOID, wintypes.DWORD]
    kernel32.EndUpdateResourceW.argtypes = [wintypes.HANDLE, wintypes.BOOL]

    images = parse_ico(ico.read_bytes())
    handle = kernel32.BeginUpdateResourceW(str(exe), False)
    if not handle:
        raise OSError(ctypes.get_last_error(), f"can't open {exe} (is VECTOR running?)")
    ok = True
    try:
        for i, (_, image) in enumerate(images, 1):
            buf = ctypes.create_string_buffer(image, len(image))
            ok &= bool(kernel32.UpdateResourceW(handle, RT_ICON, i, 0, buf, len(image)))
        group = group_icon(images)
        buf = ctypes.create_string_buffer(group, len(group))
        ok &= bool(kernel32.UpdateResourceW(handle, RT_GROUP_ICON, 1, 0, buf, len(group)))
    finally:
        if not kernel32.EndUpdateResourceW(handle, not ok):
            ok = False
    if not ok:
        raise OSError(ctypes.get_last_error(), f"couldn't write the icon into {exe}")


def refresh_icon_cache() -> None:
    """Ask Explorer to redraw icons so the new one shows without a restart."""
    import ctypes

    SHCNE_ASSOCCHANGED, SHCNF_IDLIST = 0x08000000, 0
    ctypes.windll.shell32.SHChangeNotify(SHCNE_ASSOCCHANGED, SHCNF_IDLIST, None, None)


def main() -> int:
    if sys.platform != "win32":
        print("Only needed on Windows.")
        return 0
    scripts = Path(sys.executable).parent
    done = []
    for name in ("vector-app.exe", "vector.exe"):
        exe = scripts / name
        if exe.exists():
            try:
                set_exe_icon(exe)
                done.append(name)
            except OSError as exc:
                print(f"Couldn't set the icon on {name}: {exc}")
    refresh_icon_cache()
    print("VECTOR icon set on: " + (", ".join(done) or "nothing"))
    return 0 if done else 1


if __name__ == "__main__":
    sys.exit(main())
