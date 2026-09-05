"""Colour maths for the theme layer: parsing, WCAG contrast, mixing, and
dichromat simulation.

Everything here is pure, deterministic and stdlib-only. Colours travel as
``#rrggbb`` strings because that is what ends up in the SVG; the integer-triple
form exists only inside a calculation. Hex output is normalised to lowercase,
so ``mix(c, other, 0.0) == c`` holds for any colour written in this codebase.
"""

from __future__ import annotations

import math
import re
from typing import Sequence

RGB = tuple[int, int, int]

__all__ = [
    "RGB", "ColorError", "CVD_KINDS",
    "parse_color", "to_hex", "relative_luminance", "contrast_ratio",
    "mix", "lighten", "darken", "interpolate",
    "simulate_cvd", "to_lab", "from_lab", "delta_e",
    "mix_lab", "interpolate_lab",
]


class ColorError(ValueError):
    """A colour value that cannot be interpreted."""


# A deliberately small slice of CSS: the sixteen HTML 4 keywords plus the greys
# and orange that actually turn up in diagram source. Anything else should be
# written as hex so the value is visible at the call site.
_CSS_NAMES: dict[str, str] = {
    "aqua": "#00ffff", "black": "#000000", "blue": "#0000ff",
    "cyan": "#00ffff", "darkgray": "#a9a9a9", "darkgrey": "#a9a9a9",
    "dimgray": "#696969", "dimgrey": "#696969", "fuchsia": "#ff00ff",
    "gray": "#808080", "green": "#008000", "grey": "#808080",
    "lightgray": "#d3d3d3", "lightgrey": "#d3d3d3", "lime": "#00ff00",
    "magenta": "#ff00ff", "maroon": "#800000", "navy": "#000080",
    "olive": "#808000", "orange": "#ffa500", "purple": "#800080",
    "red": "#ff0000", "silver": "#c0c0c0", "teal": "#008080",
    "white": "#ffffff", "whitesmoke": "#f5f5f5", "yellow": "#ffff00",
}

_HEX = re.compile(r"^#([0-9a-f]{3}|[0-9a-f]{6})$")
_RGB_FUNC = re.compile(r"^rgb\((.*)\)$")
_SEPARATOR = re.compile(r"[,\s]+")


def _round_half_up(value: float) -> int:
    """Deterministic rounding. `round()` is banker's, which makes a 50% mix
    round differently depending on which side of the blend you came from."""
    return math.floor(value + 0.5)


def _channel(value: float) -> int:
    return max(0, min(255, _round_half_up(value)))


def parse_color(value: str | Sequence[float]) -> RGB:
    """Parse ``#rgb``, ``#rrggbb``, ``rgb(...)`` or a CSS keyword into 0-255.

    A 3-sequence passes through (clamped), so callers can hand either form to
    the contrast helpers without converting first.
    """
    if not isinstance(value, str):
        channels = tuple(value)
        if len(channels) != 3:
            raise ColorError(f"expected 3 channels, got {len(channels)}")
        return (_channel(channels[0]), _channel(channels[1]), _channel(channels[2]))

    text = value.strip().lower()
    if text in _CSS_NAMES:
        text = _CSS_NAMES[text]

    hex_match = _HEX.match(text)
    if hex_match:
        digits = hex_match.group(1)
        if len(digits) == 3:
            digits = "".join(d * 2 for d in digits)
        return (int(digits[0:2], 16), int(digits[2:4], 16), int(digits[4:6], 16))

    func_match = _RGB_FUNC.match(text)
    if func_match:
        return _parse_rgb_components(func_match.group(1), value)

    raise ColorError(f"cannot parse colour {value!r}")


def _parse_rgb_components(body: str, original: str) -> RGB:
    if "/" in body:
        raise ColorError(f"alpha is not supported: {original!r}")
    parts = [p for p in _SEPARATOR.split(body.strip()) if p]
    if len(parts) != 3:
        raise ColorError(f"rgb() needs 3 components: {original!r}")
    channels = []
    for part in parts:
        try:
            value = (float(part[:-1]) / 100.0 * 255.0 if part.endswith("%")
                     else float(part))
        except ValueError:
            raise ColorError(f"cannot parse colour {original!r}") from None
        channels.append(value)
    return (_channel(channels[0]), _channel(channels[1]), _channel(channels[2]))


def to_hex(rgb: Sequence[float]) -> str:
    r, g, b = (_channel(c) for c in rgb)
    return f"#{r:02x}{g:02x}{b:02x}"


# --- WCAG contrast -----------------------------------------------------------
#
# WCAG 2.x, "Relative luminance" and "Contrast ratio" definitions:
# https://www.w3.org/TR/WCAG22/#dfn-relative-luminance
# The coefficients here are WCAG's own (0.2126/0.7152/0.0722 with the 0.03928
# knee), which are a rounded form of the sRGB->XYZ Y row used in `to_lab`.
# They are kept separate on purpose: contrast thresholds are defined against
# these exact numbers, so rounding them differently changes pass/fail.

def _linearize(channel: int) -> float:
    c = channel / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(rgb: str | Sequence[float]) -> float:
    """WCAG relative luminance, 0.0 (black) to 1.0 (white)."""
    r, g, b = (_linearize(c) for c in parse_color(rgb))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a: str | Sequence[float], b: str | Sequence[float]) -> float:
    """WCAG contrast ratio, 1.0 (identical) to 21.0 (black on white)."""
    la, lb = relative_luminance(a), relative_luminance(b)
    lighter, darker = max(la, lb), min(la, lb)
    return (lighter + 0.05) / (darker + 0.05)


# --- mixing ------------------------------------------------------------------
#
# Blending happens in gamma-encoded sRGB rather than linear light. That is the
# wrong physics but the right result here: it matches CSS `color-mix(in srgb)`
# and every design tool, so a 20% tint looks like the 20% tint the author drew
# in Figma. Ramp stops in `palettes` are published as sRGB swatches and are
# meant to be interpolated the same way.

def mix(a: str | Sequence[float], b: str | Sequence[float], t: float) -> str:
    """Blend `a` towards `b`; t=0 returns `a`, t=1 returns `b`."""
    if not 0.0 <= t <= 1.0:
        raise ColorError(f"mix amount must be within 0..1, got {t}")
    ca, cb = parse_color(a), parse_color(b)
    return to_hex([x + (y - x) * t for x, y in zip(ca, cb)])


def lighten(color: str | Sequence[float], amount: float) -> str:
    """Move `amount` of the way towards white."""
    return mix(color, "#ffffff", amount)


def darken(color: str | Sequence[float], amount: float) -> str:
    """Move `amount` of the way towards black."""
    return mix(color, "#000000", amount)


def interpolate(stops: Sequence[str], t: float) -> str:
    """Sample a continuous ramp built from evenly spaced `stops`, t in 0..1.

    This is the helper behind the sequential and diverging palettes: the
    published swatches become a continuous ramp without anyone having to
    hand-pick an intermediate value.
    """
    if not stops:
        raise ColorError("cannot interpolate an empty ramp")
    t = min(1.0, max(0.0, t))
    if len(stops) == 1:
        return to_hex(parse_color(stops[0]))
    position = t * (len(stops) - 1)
    index = min(int(position), len(stops) - 2)
    return mix(stops[index], stops[index + 1], position - index)


# --- colour vision deficiency ------------------------------------------------
#
# Viénot, Brettel & Mollon (1999), "Digital video colourmaps for checking the
# legibility of displays by dichromats", Color Research and Application 24(4),
# 243-252. The transform projects LMS cone responses onto the plane a dichromat
# can still distinguish, leaving the surviving cones untouched.
#
# The paper notes the transform is often applied straight to gamma-encoded
# values as a shortcut; we decode to linear light first, which is what the
# derivation actually assumes, and re-encode afterwards.

_RGB_TO_LMS = (
    (17.8824, 43.5161, 4.11935),
    (3.45565, 27.1554, 3.86714),
    (0.0299566, 0.184309, 1.46709),
)

# Dichromat projections in LMS. Each replaces the missing cone's response with
# the best estimate from the two that remain.
_PROJECTIONS = {
    # L cones absent: L is reconstructed from M and S.
    "protanopia": ((0.0, 2.02344, -2.52581), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
    # M cones absent.
    "deuteranopia": ((1.0, 0.0, 0.0), (0.494207, 0.0, 1.24827), (0.0, 0.0, 1.0)),
    # S cones absent.
    "tritanopia": ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (-0.395913, 0.801109, 0.0)),
}

CVD_KINDS: tuple[str, ...] = ("deuteranopia", "protanopia", "tritanopia")

_ALIASES = {"deutan": "deuteranopia", "protan": "protanopia", "tritan": "tritanopia"}

Matrix = tuple[tuple[float, float, float], ...]


def _invert3(m: Matrix) -> Matrix:
    """Inverting at import beats transcribing the published inverse: the two
    matrices cannot drift apart, and a typo would show up as a failed round
    trip rather than as a subtly wrong simulation."""
    (a, b, c), (d, e, f), (g, h, i) = m
    cof = (
        (e * i - f * h, c * h - b * i, b * f - c * e),
        (f * g - d * i, a * i - c * g, c * d - a * f),
        (d * h - e * g, b * g - a * h, a * e - b * d),
    )
    det = a * cof[0][0] + b * cof[1][0] + c * cof[2][0]
    if abs(det) < 1e-12:
        raise ColorError("singular matrix")
    return tuple(tuple(v / det for v in row) for row in cof)


_LMS_TO_RGB = _invert3(_RGB_TO_LMS)


def _apply(m: Matrix, v: Sequence[float]) -> tuple[float, float, float]:
    return tuple(sum(coef * component for coef, component in zip(row, v)) for row in m)


def _encode(linear: float) -> float:
    c = min(1.0, max(0.0, linear))
    return c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def simulate_cvd(color: str | Sequence[float], kind: str = "deuteranopia") -> str:
    """Render `color` as a dichromat with `kind` would see it.

    Out-of-gamut results are clipped, which is what every practical
    implementation does; the alternative (desaturating towards the neutral
    axis) changes distances more than the clipping does.
    """
    key = _ALIASES.get(kind, kind)
    projection = _PROJECTIONS.get(key)
    if projection is None:
        raise ColorError(f"unknown CVD kind {kind!r}; expected one of {CVD_KINDS}")
    linear = [_linearize(c) for c in parse_color(color)]
    simulated = _apply(_LMS_TO_RGB, _apply(projection, _apply(_RGB_TO_LMS, linear)))
    return to_hex([_encode(c) * 255.0 for c in simulated])


# --- perceptual distance -----------------------------------------------------
#
# CIELAB with the D65 white point, per CIE 15:2004. Distances are CIE76 dE*ab,
# which is crude at large differences but monotone and cheap; we only need to
# answer "did these two collapse into each other", not to rank near-matches.

_D65 = (0.95047, 1.00000, 1.08883)

_RGB_TO_XYZ = (
    (0.4124564, 0.3575761, 0.1804375),
    (0.2126729, 0.7151522, 0.0721750),
    (0.0193339, 0.1191920, 0.9503041),
)

_LAB_EPSILON = (6 / 29) ** 3


def _lab_f(t: float) -> float:
    return t ** (1 / 3) if t > _LAB_EPSILON else t / (3 * (6 / 29) ** 2) + 4 / 29


def to_lab(color: str | Sequence[float]) -> tuple[float, float, float]:
    """CIELAB L*a*b* under D65."""
    linear = [_linearize(c) for c in parse_color(color)]
    x, y, z = (v / w for v, w in zip(_apply(_RGB_TO_XYZ, linear), _D65))
    fx, fy, fz = _lab_f(x), _lab_f(y), _lab_f(z)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def delta_e(a: str | Sequence[float], b: str | Sequence[float]) -> float:
    """CIE76 dE*ab between two colours."""
    return math.dist(to_lab(a), to_lab(b))


# The inverse of `to_lab`, sharing its matrices and its white point so the two
# cannot drift apart. It exists for ramps: blending two colours in sRGB runs
# the shortest line through the cube, which for anything but a pair of
# neighbours dips through a desaturated middle -- the muddy grey-brown every
# hand-rolled gradient has in it. In CIELAB the same blend keeps its chroma and
# moves at a steady perceived rate.

_XYZ_TO_RGB = _invert3(_RGB_TO_XYZ)


def _lab_f_inv(t: float) -> float:
    return t ** 3 if t > 6 / 29 else 3 * (6 / 29) ** 2 * (t - 4 / 29)


def from_lab(lab: Sequence[float]) -> str:
    """CIELAB L*a*b* under D65 back to a hex colour, clipped to sRGB."""
    lightness, a_star, b_star = lab
    fy = (lightness + 16) / 116
    fx, fz = fy + a_star / 500, fy - b_star / 200
    xyz = [_lab_f_inv(f) * w for f, w in zip((fx, fy, fz), _D65)]
    return to_hex([_encode(c) * 255.0 for c in _apply(_XYZ_TO_RGB, xyz)])


def mix_lab(a: str | Sequence[float], b: str | Sequence[float], t: float) -> str:
    """Blend `a` towards `b` through CIELAB; t=0 returns `a`, t=1 returns `b`."""
    if not 0.0 <= t <= 1.0:
        raise ColorError(f"mix amount must be within 0..1, got {t}")
    la, lb = to_lab(a), to_lab(b)
    return from_lab([x + (y - x) * t for x, y in zip(la, lb)])


#: Lightness step of the `readable` search, in L* units. Fixed rather than
#: bisected so the answer is the same number every run, and fine enough that
#: the result is within half a unit of the lightest colour that passes -- about
#: a 1/256 change in a channel, which is below what a press can hold anyway.
_L_STEP = 0.5


def readable(color: str | Sequence[float], on: str | Sequence[float],
             min_ratio: float = 4.5) -> str:
    """The nearest colour to `color`, along its own lightness, that can be read
    on `on`.

    A categorical palette is built for *area*. Okabe-Ito's yellow on white is
    1.07:1 and its sky blue 1.9:1 -- fine as a bar, unreadable as the word that
    names the bar, and there is no honest way around it except to change the
    colour. This changes it as little as possible: hold a* and b*, which fixes
    the hue angle *and* keeps the colour recognisably the series' own, and walk
    L* towards the far side of the background until WCAG's ratio is met. The
    result stays in the same family as the swatch beside it, where blending
    towards ink (`Theme.ink_color`) drifts every hue towards the same grey.

    `min_ratio` defaults to 4.5, the AA threshold for body text; 3.0 is the
    threshold for large text and for a graphical object such as a rule.

    Hue is held as far as it can be and no further: if the darkest (or
    lightest) colour of this hue still falls short, the hue is given up and the
    answer is black or white, whichever is the readable one. That way the ratio
    is met whenever *any* colour could meet it, and only then.
    """
    lightness, a_star, b_star = to_lab(color)
    start = to_hex(parse_color(color))
    if contrast_ratio(start, on) >= min_ratio:
        return start
    # Away from the background: darker on paper, lighter on a dark ground.
    down = relative_luminance(on) >= relative_luminance(color)
    limit = lightness if down else 100.0 - lightness
    steps = max(1, int(limit / _L_STEP))
    for step in range(1, steps + 1):
        level = lightness + (-_L_STEP if down else _L_STEP) * step
        candidate = from_lab((level, a_star, b_star))
        if contrast_ratio(candidate, on) >= min_ratio:
            return candidate
    edge = from_lab((0.0 if down else 100.0, a_star, b_star))
    if contrast_ratio(edge, on) >= min_ratio:
        return edge
    return "#000000" if down else "#ffffff"


def interpolate_lab(stops: Sequence[str], t: float) -> str:
    """Sample a ramp of evenly spaced `stops` in CIELAB, t in 0..1."""
    if not stops:
        raise ColorError("cannot interpolate an empty ramp")
    t = min(1.0, max(0.0, t))
    if len(stops) == 1:
        return to_hex(parse_color(stops[0]))
    position = t * (len(stops) - 1)
    index = min(int(position), len(stops) - 2)
    return mix_lab(stops[index], stops[index + 1], position - index)
