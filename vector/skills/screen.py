"""Seeing and controlling the screen: screenshots for the AI, mouse clicks, scrolling, dragging.

These need the user's OK once per request (setting: screen_access). Moving the mouse into a
corner of the screen, or pressing Esc, stops VECTOR mid-task.
"""

from __future__ import annotations

import io
from collections.abc import Callable
from typing import Literal

from vector.registry import ToolOutput, tool

MAX_W, MAX_H = 1366, 900  # screenshots are shrunk to this; keeps them quick and cheap for the AI
_state = {"scale": 1.0}

# Set by the app: called with True before VECTOR looks or clicks (hide the summon bar so it
# isn't in the way), and False when the request is over.
hide_overlay: Callable[[bool], None] | None = None

_MISSING = "Seeing and controlling the screen needs pyautogui: pip install \"vector-assistant[control]\""


def _gui():
    try:
        import pyautogui
    except Exception:  # not installed, or no display
        return None
    pyautogui.FAILSAFE = True  # mouse in a screen corner = emergency stop
    pyautogui.PAUSE = 0.05
    return pyautogui


def _prepare() -> None:
    if hide_overlay is not None:
        hide_overlay(True)


def shrink(width: int, height: int) -> float:
    """Scale factor that fits a screen into MAX_W x MAX_H (never enlarges)."""
    return min(1.0, MAX_W / width, MAX_H / height)


def click_scale(image_w: int, shot_w: int, mouse_w: int) -> float:
    """Screenshot pixels per mouse unit. Same as the shrink factor unless the screenshot has
    more pixels than the mouse has positions (Retina screens: 2x)."""
    if mouse_w <= 0 or shot_w <= 0:
        return image_w / shot_w if shot_w else 1.0
    return image_w / mouse_w


def to_screen(x: float, y: float, scale: float | None = None) -> tuple[int, int]:
    """Screenshot pixel -> real screen pixel."""
    s = scale if scale is not None else _state["scale"]
    return round(x / s), round(y / s)


def to_image(x: float, y: float, scale: float | None = None) -> tuple[int, int]:
    s = scale if scale is not None else _state["scale"]
    return round(x * s), round(y * s)


@tool(screen=True)
def look_at_screen() -> ToolOutput | str:
    """Take a screenshot so you can see what's on the screen right now: read text, find buttons,
    check that an action worked. Coordinates for click/scroll/drag are pixels in this image."""
    gui = _gui()
    if gui is None:
        return _MISSING
    _prepare()
    try:
        from PIL import ImageGrab

        img = ImageGrab.grab()  # physical pixels, the same space pyautogui clicks in
    except Exception:
        img = gui.screenshot()
    full_w, full_h = img.size
    scale = shrink(full_w, full_h)
    if scale < 1:
        from PIL import Image

        img = img.resize((round(full_w * scale), round(full_h * scale)), Image.LANCZOS)
    # Clicks use the mouse's own units. On a Mac Retina screen a screenshot has twice as many
    # pixels as those units, so the image -> mouse factor comes from the two real sizes.
    _state["scale"] = click_scale(img.width, full_w, gui.size()[0])
    scale = _state["scale"]
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "JPEG", quality=72)
    mx, my = to_image(*gui.position(), scale)
    return ToolOutput(
        f"Screenshot: {img.width}x{img.height} pixels (the screen is {full_w}x{full_h}). "
        f"Mouse pointer at ({mx}, {my}). Use this image's pixel coordinates for click, scroll and drag.",
        [("image/jpeg", buf.getvalue())],
    )


@tool(screen=True)
def click(x: int, y: int, button: Literal["left", "right", "middle"] = "left",
          double: bool = False) -> str:
    """Click on the screen at a point from the latest screenshot (look_at_screen first).

    x: Horizontal pixel in the screenshot.
    y: Vertical pixel in the screenshot.
    button: Which mouse button.
    double: Double-click instead of a single click.
    """
    gui = _gui()
    if gui is None:
        return _MISSING
    _prepare()
    sx, sy = to_screen(x, y)
    gui.click(sx, sy, clicks=2 if double else 1, button=button)
    return f"{'Double-clicked' if double else 'Clicked'} {button} at ({x}, {y})."


@tool(screen=True)
def move_mouse(x: int, y: int) -> str:
    """Move the mouse pointer to a point from the latest screenshot (e.g. to hover a menu).

    x: Horizontal pixel in the screenshot.
    y: Vertical pixel in the screenshot.
    """
    gui = _gui()
    if gui is None:
        return _MISSING
    _prepare()
    gui.moveTo(*to_screen(x, y), duration=0.15)
    return f"Mouse moved to ({x}, {y})."


@tool(screen=True)
def scroll(amount: int, x: int | None = None, y: int | None = None) -> str:
    """Scroll the mouse wheel. Positive scrolls up, negative scrolls down.

    amount: Wheel steps, e.g. -5 to scroll down a page-ish.
    x: Optional point (screenshot pixels) to scroll over.
    y: Optional point (screenshot pixels) to scroll over.
    """
    gui = _gui()
    if gui is None:
        return _MISSING
    _prepare()
    if x is not None and y is not None:
        gui.moveTo(*to_screen(x, y))
    # Windows counts wheel movement in 1/120ths of a notch.
    gui.scroll(int(amount) * (120 if _is_windows() else 1))
    return f"Scrolled {'up' if amount > 0 else 'down'} {abs(int(amount))}."


@tool(screen=True)
def drag(from_x: int, from_y: int, to_x: int, to_y: int) -> str:
    """Drag with the left mouse button held, e.g. to move a window or select text.

    from_x: Start pixel (screenshot), horizontal.
    from_y: Start pixel (screenshot), vertical.
    to_x: End pixel (screenshot), horizontal.
    to_y: End pixel (screenshot), vertical.
    """
    gui = _gui()
    if gui is None:
        return _MISSING
    _prepare()
    gui.moveTo(*to_screen(from_x, from_y))
    gui.dragTo(*to_screen(to_x, to_y), duration=0.4, button="left")
    return f"Dragged from ({from_x}, {from_y}) to ({to_x}, {to_y})."


def _is_windows() -> bool:
    import sys

    return sys.platform == "win32"
