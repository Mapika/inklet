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
    "to_oklab", "from_oklab", "to_oklch", "from_oklch", "in_gamut_oklab",
    "mix_oklab", "interpolate_oklab", "delta_e_2000", "delta_e_ok",
    "CVD_METHODS",
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


# Machado, Oliveira & Fernandes (2009), "A physiologically-based model for
# simulation of color vision deficiency", IEEE TVCG 15(6), 1291-1298,
# doi:10.1109/TVCG.2009.113. The matrices are the authors' supplementary
# table (https://www.inf.ufrgs.br/~oliveira/pubs_files/CVD_Simulation/
# CVD_Simulation.html), one per 0.1 of severity, applied to *linear* sRGB.
# Severity 1.0 is the dichromat; anything below it is the anomalous
# trichromat -- deuteranomaly is the single most common case, ~5% of men --
# which the Vienot projection above cannot express at all.
_MACHADO: dict[str, tuple[Matrix, ...]] = {
    "protanopia": (
        ((1.000000, 0.000000, -0.000000), (0.000000, 1.000000, 0.000000), (-0.000000, -0.000000, 1.000000)),
        ((0.856167, 0.182038, -0.038205), (0.029342, 0.955115, 0.015544), (-0.002880, -0.001563, 1.004443)),
        ((0.734766, 0.334872, -0.069637), (0.051840, 0.919198, 0.028963), (-0.004928, -0.004209, 1.009137)),
        ((0.630323, 0.465641, -0.095964), (0.069181, 0.890046, 0.040773), (-0.006308, -0.007724, 1.014032)),
        ((0.539009, 0.579343, -0.118352), (0.082546, 0.866121, 0.051332), (-0.007136, -0.011959, 1.019095)),
        ((0.458064, 0.679578, -0.137642), (0.092785, 0.846313, 0.060902), (-0.007494, -0.016807, 1.024301)),
        ((0.385450, 0.769005, -0.154455), (0.100526, 0.829802, 0.069673), (-0.007442, -0.022190, 1.029632)),
        ((0.319627, 0.849633, -0.169261), (0.106241, 0.815969, 0.077790), (-0.007025, -0.028051, 1.035076)),
        ((0.259411, 0.923008, -0.182420), (0.110296, 0.804340, 0.085364), (-0.006276, -0.034346, 1.040622)),
        ((0.203876, 0.990338, -0.194214), (0.112975, 0.794542, 0.092483), (-0.005222, -0.041043, 1.046265)),
        ((0.152286, 1.052583, -0.204868), (0.114503, 0.786281, 0.099216), (-0.003882, -0.048116, 1.051998)),
    ),
    "deuteranopia": (
        ((1.000000, 0.000000, -0.000000), (0.000000, 1.000000, 0.000000), (-0.000000, -0.000000, 1.000000)),
        ((0.866435, 0.177704, -0.044139), (0.049567, 0.939063, 0.011370), (-0.003453, 0.007233, 0.996220)),
        ((0.760729, 0.319078, -0.079807), (0.090568, 0.889315, 0.020117), (-0.006027, 0.013325, 0.992702)),
        ((0.675425, 0.433850, -0.109275), (0.125303, 0.847755, 0.026942), (-0.007950, 0.018572, 0.989378)),
        ((0.605511, 0.528560, -0.134071), (0.155318, 0.812366, 0.032316), (-0.009376, 0.023176, 0.986200)),
        ((0.547494, 0.607765, -0.155259), (0.181692, 0.781742, 0.036566), (-0.010410, 0.027275, 0.983136)),
        ((0.498864, 0.674741, -0.173604), (0.205199, 0.754872, 0.039929), (-0.011131, 0.030969, 0.980162)),
        ((0.457771, 0.731899, -0.189670), (0.226409, 0.731012, 0.042579), (-0.011595, 0.034333, 0.977261)),
        ((0.422823, 0.781057, -0.203881), (0.245752, 0.709602, 0.044646), (-0.011843, 0.037423, 0.974421)),
        ((0.392952, 0.823610, -0.216562), (0.263559, 0.690210, 0.046232), (-0.011910, 0.040281, 0.971630)),
        ((0.367322, 0.860646, -0.227968), (0.280085, 0.672501, 0.047413), (-0.011820, 0.042940, 0.968881)),
    ),
    "tritanopia": (
        ((1.000000, 0.000000, -0.000000), (0.000000, 1.000000, 0.000000), (-0.000000, -0.000000, 1.000000)),
        ((0.926670, 0.092514, -0.019184), (0.021191, 0.964503, 0.014306), (0.008437, 0.054813, 0.936750)),
        ((0.895720, 0.133330, -0.029050), (0.029997, 0.945400, 0.024603), (0.013027, 0.104707, 0.882266)),
        ((0.905871, 0.127791, -0.033662), (0.026856, 0.941251, 0.031893), (0.013410, 0.148296, 0.838294)),
        ((0.948035, 0.089490, -0.037526), (0.014364, 0.946792, 0.038844), (0.010853, 0.193991, 0.795156)),
        ((1.017277, 0.027029, -0.044306), (-0.006113, 0.958479, 0.047634), (0.006379, 0.248708, 0.744913)),
        ((1.104996, -0.046633, -0.058363), (-0.032137, 0.971635, 0.060503), (0.001336, 0.317922, 0.680742)),
        ((1.193214, -0.109812, -0.083402), (-0.058496, 0.979410, 0.079086), (-0.002346, 0.403492, 0.598854)),
        ((1.257728, -0.139648, -0.118081), (-0.078003, 0.975409, 0.102594), (-0.003316, 0.501214, 0.502102)),
        ((1.278864, -0.125333, -0.153531), (-0.084748, 0.957674, 0.127074), (-0.000989, 0.601151, 0.399838)),
        ((1.255528, -0.076749, -0.178779), (-0.078411, 0.930809, 0.147602), (0.004733, 0.691367, 0.303900)),
    ),
}

CVD_METHODS: tuple[str, ...] = ("vienot", "machado")


def _machado_matrix(kind: str, severity: float) -> Matrix:
    """The published matrix at `severity`, linearly interpolated between the
    two tabulated tenths either side of it, as the authors suggest."""
    table = _MACHADO[kind]
    position = severity * 10.0
    low = min(int(position), 9)
    frac = position - low
    return tuple(tuple(x + (y - x) * frac for x, y in zip(ra, rb))
                 for ra, rb in zip(table[low], table[low + 1]))


def simulate_cvd(color: str | Sequence[float], kind: str = "deuteranopia", *,
                 method: str = "vienot", severity: float = 1.0) -> str:
    """Render `color` as a reader with colour vision deficiency `kind` sees it.

    `method="vienot"` (the default, unchanged) is the Vienot, Brettel &
    Mollon dichromat projection. `method="machado"` is Machado, Oliveira &
    Fernandes (2009), which also models anomalous trichromats: `severity`
    runs 0..1, and 1.0 is the dichromat. Machado is what `Palette.cvd` and
    `Palette.report` use.

    Out-of-gamut results are clipped, which is what every practical
    implementation does; the alternative (desaturating towards the neutral
    axis) changes distances more than the clipping does.
    """
    key = _ALIASES.get(kind, kind)
    if key not in _PROJECTIONS:
        raise ColorError(f"unknown CVD kind {kind!r}; expected one of {CVD_KINDS}")
    linear = [_linearize(c) for c in parse_color(color)]
    if method == "machado":
        if not 0.0 <= severity <= 1.0:
            raise ColorError(f"CVD severity must be within 0..1, got {severity}")
        simulated = _apply(_machado_matrix(key, severity), linear)
    elif method == "vienot":
        simulated = _apply(_LMS_TO_RGB,
                           _apply(_PROJECTIONS[key], _apply(_RGB_TO_LMS, linear)))
    else:
        raise ColorError(
            f"unknown CVD method {method!r}; expected one of {CVD_METHODS}")
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


# --- OKLab -------------------------------------------------------------------
#
# Bjorn Ottosson, "A perceptual color space for image processing" (2020),
# https://bottosson.github.io/posts/oklab/ -- the published matrices for
# linear sRGB under D65. For ramps OKLab fixes CIELAB's two known faults:
# blue no longer drifts towards purple as it lightens, and hue holds along a
# lightness change, so a blend between two stops does not pass through a
# third hue. L runs 0..1; a and b stay roughly within -0.4..0.4. OKLCH is the
# same space in polar form, with hue in degrees.

_RGB_TO_OKLMS = (
    (0.4122214708, 0.5363325363, 0.0514459929),
    (0.2119034982, 0.6806995451, 0.1073969566),
    (0.0883024619, 0.2817188376, 0.6299787005),
)
_OKLMS_TO_OKLAB = (
    (0.2104542553, 0.7936177850, -0.0040720468),
    (1.9779984951, -2.4285922050, 0.4505937099),
    (0.0259040371, 0.7827717662, -0.8086757660),
)
_OKLAB_TO_OKLMS = (
    (1.0, 0.3963377774, 0.2158037573),
    (1.0, -0.1055613458, -0.0638541728),
    (1.0, -0.0894841775, -1.2914855480),
)
_OKLMS_TO_RGB = (
    (4.0767416621, -3.3077115913, 0.2309699292),
    (-1.2684380046, 2.6097574011, -0.3413193965),
    (-0.0041960863, -0.7034186147, 1.7076147010),
)


def _srgb_decode(channel: float) -> float:
    """IEC 61966-2-1 decoding, with the standard's 0.04045 knee rather than
    WCAG's 0.03928; they differ only below channel value 11, but OKLab is
    defined against the standard."""
    c = channel / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _cbrt(x: float) -> float:
    return math.copysign(abs(x) ** (1.0 / 3.0), x)


def to_oklab(color: str | Sequence[float]) -> tuple[float, float, float]:
    """OKLab (L, a, b) of an sRGB colour; L is 0 for black and 1 for white."""
    linear = [_srgb_decode(c) for c in parse_color(color)]
    return _apply(_OKLMS_TO_OKLAB, [_cbrt(v) for v in _apply(_RGB_TO_OKLMS, linear)])


def _oklab_to_linear(lab: Sequence[float]) -> tuple[float, float, float]:
    return _apply(_OKLMS_TO_RGB, [v ** 3 for v in _apply(_OKLAB_TO_OKLMS, lab)])


def from_oklab(lab: Sequence[float]) -> str:
    """OKLab back to a hex colour, clipped to sRGB."""
    return to_hex([_encode(c) * 255.0 for c in _oklab_to_linear(lab)])


def in_gamut_oklab(lab: Sequence[float], tolerance: float = 1e-4) -> bool:
    """Whether an OKLab colour lies inside the sRGB cube before clipping."""
    return all(-tolerance <= c <= 1.0 + tolerance for c in _oklab_to_linear(lab))


def to_oklch(color: str | Sequence[float]) -> tuple[float, float, float]:
    """OKLCH (L, C, h): OKLab lightness, chroma, and hue in degrees 0..360."""
    lightness, a, b = to_oklab(color)
    return (lightness, math.hypot(a, b), math.degrees(math.atan2(b, a)) % 360.0)


def from_oklch(lch: Sequence[float]) -> str:
    """OKLCH (L, C, h in degrees) to a hex colour, clipped to sRGB."""
    lightness, chroma, hue = lch
    angle = math.radians(hue)
    return from_oklab((lightness, chroma * math.cos(angle), chroma * math.sin(angle)))


def mix_oklab(a: str | Sequence[float], b: str | Sequence[float], t: float) -> str:
    """Blend `a` towards `b` through OKLab; t=0 returns `a`, t=1 returns `b`."""
    if not 0.0 <= t <= 1.0:
        raise ColorError(f"mix amount must be within 0..1, got {t}")
    la, lb = to_oklab(a), to_oklab(b)
    return from_oklab([x + (y - x) * t for x, y in zip(la, lb)])


def interpolate_oklab(stops: Sequence[str], t: float) -> str:
    """Sample a ramp of evenly spaced `stops` in OKLab, t in 0..1."""
    if not stops:
        raise ColorError("cannot interpolate an empty ramp")
    t = min(1.0, max(0.0, t))
    if len(stops) == 1:
        return to_hex(parse_color(stops[0]))
    position = t * (len(stops) - 1)
    index = min(int(position), len(stops) - 2)
    return mix_oklab(stops[index], stops[index + 1], position - index)


def delta_e_ok(a: str | Sequence[float], b: str | Sequence[float]) -> float:
    """Euclidean distance in OKLab, times 100 so that it sits on roughly the
    scale of the CIELAB differences (a just-noticeable step is about 2)."""
    return 100.0 * math.dist(to_oklab(a), to_oklab(b))


def delta_e_2000(a: str | Sequence[float], b: str | Sequence[float]) -> float:
    """CIEDE2000 colour difference between two sRGB colours (kL=kC=kH=1)."""
    return _ciede2000(to_lab(a), to_lab(b))


def _ciede2000(lab1: Sequence[float], lab2: Sequence[float]) -> float:
    """CIEDE2000 (CIE 142-2001) between two CIELAB colours.

    Written after Sharma, Wu & Dalal (2005), "The CIEDE2000 color-difference
    formula: implementation notes, supplementary test data and mathematical
    observations", Color Res. Appl. 30(1), 21-30, including their hue-mean and
    hue-difference conventions; the tests run their published pairs. This is
    the metric Paul Tol designs his schemes against, so the palette reports
    use the same measure as the sources.
    """
    l1, a1, b1 = lab1
    l2, a2, b2 = lab2
    c_bar = (math.hypot(a1, b1) + math.hypot(a2, b2)) / 2.0
    g = 0.5 * (1.0 - math.sqrt(c_bar ** 7 / (c_bar ** 7 + 25.0 ** 7)))
    a1p, a2p = (1.0 + g) * a1, (1.0 + g) * a2
    c1p, c2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    h1p = math.degrees(math.atan2(b1, a1p)) % 360.0 if c1p else 0.0
    h2p = math.degrees(math.atan2(b2, a2p)) % 360.0 if c2p else 0.0
    neutral = c1p * c2p == 0.0
    dhp = 0.0 if neutral else h2p - h1p
    if dhp > 180.0:
        dhp -= 360.0
    elif dhp < -180.0:
        dhp += 360.0
    d_l = l2 - l1
    d_c = c2p - c1p
    d_h = 2.0 * math.sqrt(c1p * c2p) * math.sin(math.radians(dhp) / 2.0)
    l_bar = (l1 + l2) / 2.0
    cp_bar = (c1p + c2p) / 2.0
    if neutral:
        hp_bar = h1p + h2p
    elif abs(h1p - h2p) <= 180.0:
        hp_bar = (h1p + h2p) / 2.0
    elif h1p + h2p < 360.0:
        hp_bar = (h1p + h2p + 360.0) / 2.0
    else:
        hp_bar = (h1p + h2p - 360.0) / 2.0
    t = (1.0 - 0.17 * math.cos(math.radians(hp_bar - 30.0))
         + 0.24 * math.cos(math.radians(2.0 * hp_bar))
         + 0.32 * math.cos(math.radians(3.0 * hp_bar + 6.0))
         - 0.20 * math.cos(math.radians(4.0 * hp_bar - 63.0)))
    d_theta = 30.0 * math.exp(-(((hp_bar - 275.0) / 25.0) ** 2))
    r_c = 2.0 * math.sqrt(cp_bar ** 7 / (cp_bar ** 7 + 25.0 ** 7))
    s_l = 1.0 + 0.015 * (l_bar - 50.0) ** 2 / math.sqrt(20.0 + (l_bar - 50.0) ** 2)
    s_c = 1.0 + 0.045 * cp_bar
    s_h = 1.0 + 0.015 * cp_bar * t
    r_t = -math.sin(math.radians(2.0 * d_theta)) * r_c
    return math.sqrt((d_l / s_l) ** 2 + (d_c / s_c) ** 2 + (d_h / s_h) ** 2
                     + r_t * (d_c / s_c) * (d_h / s_h))
