"""Design tokens, and the only place allowed to name a colour.

`Theme` holds the tokens; `Theme.style_for(role)` is the bridge to
`core.style.Style`. Everything else in the library asks the theme rather than
writing a hex value, which is what makes a figure rethemable and what lets the
linter check contrast instead of guessing at it.

    from inklet.themes import theme
    t = theme("nature")
    t.style_for("box")        # -> Style(fill='#ffffff', stroke='#1a1a1a', ...)
    t.color(0)                # -> categorical series colour
    t.gap("m")                # -> 3.0 mm
    t.scaled(2)               # -> the same design at twice the size
"""

from __future__ import annotations

from .color import (
    CVD_KINDS, RGB, ColorError, contrast_ratio, darken, delta_e, from_lab,
    interpolate, interpolate_lab, lighten, mix, mix_lab, parse_color,
    readable, relative_luminance, simulate_cvd, to_hex, to_lab,
)
from .palettes import (
    OKABE_ITO, PALETTES, TOL_BRIGHT, TOL_HIGH_CONTRAST, TOL_MUTED, TOL_SUNSET,
    TOL_VIBRANT, TOL_YLORBR, Palette, palette, palette_names,
)
from .theme import (
    GAP_NAMES, HAIRLINE_FLOOR, NATURE, NOTEBOOK, ROLES, SLIDES, THEMES, Theme,
    ThemeError, theme, theme_names,
)

__all__ = [
    # themes
    "Theme", "ThemeError", "THEMES", "ROLES", "GAP_NAMES", "HAIRLINE_FLOOR",
    "theme", "theme_names", "NATURE", "SLIDES", "NOTEBOOK",
    # palettes
    "Palette", "PALETTES", "palette", "palette_names",
    "OKABE_ITO", "TOL_BRIGHT", "TOL_MUTED", "TOL_VIBRANT", "TOL_HIGH_CONTRAST",
    "TOL_YLORBR", "TOL_SUNSET",
    # colour utilities
    "RGB", "ColorError", "CVD_KINDS", "parse_color", "to_hex",
    "relative_luminance", "contrast_ratio", "mix", "lighten", "darken",
    "readable",
    "interpolate", "simulate_cvd", "to_lab", "from_lab", "delta_e",
    "mix_lab", "interpolate_lab",
]
