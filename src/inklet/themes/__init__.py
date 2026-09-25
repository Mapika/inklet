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
    CVD_KINDS, CVD_METHODS, RGB, ColorError, contrast_ratio, darken, delta_e,
    delta_e_2000, delta_e_ok, from_lab, from_oklab, from_oklch, in_gamut_oklab,
    interpolate, interpolate_lab, interpolate_oklab, lighten, mix, mix_lab,
    mix_oklab, parse_color, readable, relative_luminance, simulate_cvd, to_hex,
    to_lab, to_oklab, to_oklch,
)
from .palettes import (
    CIVIDIS, INFERNO, INKLET, INKLET_DUO, INKLET_MUTED, INKLET_PAIRS, KINDS,
    MAGMA, OKABE_ITO, PALETTES, PLASMA, TOL_BRIGHT, TOL_BURD, TOL_DARK,
    TOL_HIGH_CONTRAST, TOL_INCANDESCENT, TOL_IRIDESCENT, TOL_LIGHT,
    TOL_MEDIUM_CONTRAST, TOL_MUTED, TOL_NIGHTFALL, TOL_PALE, TOL_PRGN,
    TOL_RAINBOW, TOL_SUNSET, TOL_VIBRANT, TOL_WHORBR, TOL_YLORBR, VIRIDIS,
    Palette, PaletteReport, palette, palette_names,
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
    "Palette", "PaletteReport", "PALETTES", "KINDS", "palette", "palette_names",
    "OKABE_ITO", "TOL_BRIGHT", "TOL_MUTED", "TOL_VIBRANT", "TOL_HIGH_CONTRAST",
    "TOL_MEDIUM_CONTRAST", "TOL_LIGHT", "TOL_PALE", "TOL_DARK",
    "TOL_YLORBR", "TOL_WHORBR", "TOL_IRIDESCENT", "TOL_INCANDESCENT",
    "TOL_RAINBOW", "TOL_SUNSET", "TOL_NIGHTFALL", "TOL_BURD", "TOL_PRGN",
    "VIRIDIS", "CIVIDIS", "INFERNO", "PLASMA", "MAGMA",
    "INKLET", "INKLET_MUTED", "INKLET_PAIRS", "INKLET_DUO",
    # colour utilities
    "RGB", "ColorError", "CVD_KINDS", "CVD_METHODS", "parse_color", "to_hex",
    "relative_luminance", "contrast_ratio", "mix", "lighten", "darken",
    "readable",
    "interpolate", "simulate_cvd", "to_lab", "from_lab", "delta_e",
    "mix_lab", "interpolate_lab",
    "to_oklab", "from_oklab", "to_oklch", "from_oklch", "in_gamut_oklab",
    "mix_oklab", "interpolate_oklab", "delta_e_2000", "delta_e_ok",
]
