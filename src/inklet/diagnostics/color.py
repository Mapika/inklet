"""Colour arithmetic for the contrast rule, with a self-contained fallback.

`inklet.themes` owns colour parsing for the library. It may not exist yet when this
module is imported (modules are built in parallel), so every entry point here
tries the theme first and falls back to a small local sRGB parser. The fallback
is deliberately narrow -- hex and a handful of CSS names -- because a wrong
colour guess would produce a false LOW_CONTRAST, and `None` (skip the check) is
always the better answer than a confident wrong number.
"""

from __future__ import annotations

import math
import re

RGB = tuple[float, float, float]

try:  # pragma: no cover - depends on sibling module build order
    from ..themes import contrast_ratio as _theme_contrast_ratio  # type: ignore
except Exception:  # ImportError, or a half-built theme module
    _theme_contrast_ratio = None

_HEX = re.compile(r"^#([0-9a-fA-F]{3,8})$")
_FUNC = re.compile(r"^rgba?\(([^)]*)\)$")

# Only colours whose value is unambiguous. Anything else returns None and the
# rule skips that pair rather than inventing a luminance.
_NAMED: dict[str, RGB | None] = {
    "none": None,
    "transparent": None,
    "currentcolor": None,
    "inherit": None,
    "black": (0.0, 0.0, 0.0),
    "white": (1.0, 1.0, 1.0),
    "red": (1.0, 0.0, 0.0),
    "lime": (0.0, 1.0, 0.0),
    "blue": (0.0, 0.0, 1.0),
    "yellow": (1.0, 1.0, 0.0),
    "cyan": (0.0, 1.0, 1.0),
    "aqua": (0.0, 1.0, 1.0),
    "magenta": (1.0, 0.0, 1.0),
    "fuchsia": (1.0, 0.0, 1.0),
    "green": (0.0, 128 / 255, 0.0),
    "navy": (0.0, 0.0, 128 / 255),
    "teal": (0.0, 128 / 255, 128 / 255),
    "maroon": (128 / 255, 0.0, 0.0),
    "purple": (128 / 255, 0.0, 128 / 255),
    "olive": (128 / 255, 128 / 255, 0.0),
    "orange": (1.0, 165 / 255, 0.0),
    "gray": (128 / 255, 128 / 255, 128 / 255),
    "grey": (128 / 255, 128 / 255, 128 / 255),
    "silver": (192 / 255, 192 / 255, 192 / 255),
    "lightgray": (211 / 255, 211 / 255, 211 / 255),
    "lightgrey": (211 / 255, 211 / 255, 211 / 255),
    "darkgray": (169 / 255, 169 / 255, 169 / 255),
    "darkgrey": (169 / 255, 169 / 255, 169 / 255),
    "dimgray": (105 / 255, 105 / 255, 105 / 255),
    "dimgrey": (105 / 255, 105 / 255, 105 / 255),
    "whitesmoke": (245 / 255, 245 / 255, 245 / 255),
}


def parse_color(value: str | None) -> RGB | None:
    """sRGB components in 0..1, or None when the colour is unknown or not opaque.

    Translucent colours return None on purpose: their effective luminance
    depends on what is behind them, which pure geometry cannot know.
    """
    if not isinstance(value, str):
        return None
    text = value.strip().lower()
    if not text:
        return None
    if text in _NAMED:
        return _NAMED[text]

    match = _HEX.match(text)
    if match is not None:
        digits = match.group(1)
        if len(digits) in (3, 4):
            digits = "".join(ch * 2 for ch in digits)
        if len(digits) == 8:
            if int(digits[6:8], 16) != 255:
                return None  # translucent
            digits = digits[:6]
        if len(digits) != 6:
            return None
        return tuple(int(digits[i:i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]

    match = _FUNC.match(text)
    if match is not None:
        parts = [p.strip() for p in match.group(1).replace("/", ",").split(",") if p.strip()]
        if len(parts) == 4:
            try:
                alpha = float(parts[3].rstrip("%"))
            except ValueError:
                return None
            if alpha < (100.0 if parts[3].endswith("%") else 1.0):
                return None
            parts = parts[:3]
        if len(parts) != 3:
            return None
        channels: list[float] = []
        for part in parts:
            try:
                raw = float(part.rstrip("%"))
            except ValueError:
                return None
            channels.append(raw / 100 if part.endswith("%") else raw / 255)
        return (_clamp01(channels[0]), _clamp01(channels[1]), _clamp01(channels[2]))

    return None


def _clamp01(v: float) -> float:
    return 0.0 if v < 0.0 else 1.0 if v > 1.0 else v


def relative_luminance(rgb: RGB) -> float:
    """WCAG 2.x relative luminance of an sRGB triple."""
    r, g, b = (_linearize(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _linearize(channel: float) -> float:
    return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4


def contrast_ratio(foreground: str | None, background: str | None) -> float | None:
    """WCAG contrast ratio in 1.0..21.0, or None if either colour is unknown.

    Delegates to `inklet.themes.contrast_ratio` when that module is available, but
    only trusts a finite result in the legal range; anything else falls through
    to the local computation so a theme in flux cannot poison the linter.
    """
    if _theme_contrast_ratio is not None:
        try:
            value = float(_theme_contrast_ratio(foreground, background))
        except Exception:
            value = math.nan
        if math.isfinite(value) and 0.99 <= value <= 21.01:
            return value

    fg = parse_color(foreground)
    bg = parse_color(background)
    if fg is None or bg is None:
        return None
    lighter, darker = sorted((relative_luminance(fg), relative_luminance(bg)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)
