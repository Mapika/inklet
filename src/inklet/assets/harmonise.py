"""Pulling an asset's colours into the figure's palette.

A stock illustration arrives in whatever hues its author liked. Dropped next to
a figure built from eight colour-vision-safe swatches it reads as a foreign
object -- not because it is a photograph, but because it introduces a ninth,
tenth and eleventh hue that mean nothing.

The fix is to quantise *hue* while leaving *luminance* alone. Lightness is what
carries the shape of a photograph: shading, edges, the sense of a solid object.
Chroma is what carries the palette. So each pixel keeps its L* and its
saturation and is rotated onto the nearest palette hue, blended by `strength`.
At 1.0 the asset is drawn entirely in the figure's colours; at 0.0 nothing
happens.

The CIELAB maths here duplicates `themes.color.to_lab`, which is scalar and
would take minutes over a megapixel. The constants are the same ones, on
purpose -- including the 0.03928 transfer-function knee, so that a palette
colour converted by either route lands in the same place.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Any

from ..themes.color import to_lab
from .deps import AssetError, numpy

__all__ = ["Harmonise", "as_harmonise", "harmonise", "palette_colors"]

_D65 = (0.95047, 1.00000, 1.08883)

_RGB_TO_XYZ = (
    (0.4124564, 0.3575761, 0.1804375),
    (0.2126729, 0.7151522, 0.0721750),
    (0.0193339, 0.1191920, 0.9503041),
)

# The published sRGB D65 inverse. Transcribed rather than computed with
# `linalg.inv` so the numbers cannot drift with a BLAS build, which would put
# a machine-dependent byte into a PNG this library promises is reproducible.
_XYZ_TO_RGB = (
    (3.2404542, -1.5371385, -0.4985314),
    (-0.9692660, 1.8760108, 0.0415560),
    (0.0556434, -0.2040259, 1.0572252),
)

_KNEE = 0.03928
_LINEAR_KNEE = _KNEE / 12.92
_DELTA = 6 / 29


@dataclass(frozen=True)
class Harmonise:
    """How far to pull an asset's hues toward the figure's.

    `colors` empty means the active theme's palette. `neutral_chroma` is the
    C* below which a pixel counts as grey and is left alone: rotating the hue
    of a near-neutral is amplifying noise, and it is what turns a white
    highlight faintly green.
    """

    colors: tuple[str, ...] = ()
    strength: float = 0.6
    neutral_chroma: float = 6.0

    def key(self) -> dict[str, Any]:
        return {"colors": list(self.colors), "strength": self.strength,
                "neutral_chroma": self.neutral_chroma}


def as_harmonise(spec: Harmonise | Sequence[str] | float | bool | None,
                 strength: float | None = None) -> Harmonise | None:
    """Coerce the `palette=` argument. None/False mean "leave the colours alone"."""
    if spec is None or spec is False:
        return None
    if spec is True:
        base = Harmonise()
    elif isinstance(spec, Harmonise):
        base = spec
    elif isinstance(spec, (int, float)):
        base = Harmonise(strength=float(spec))
    elif isinstance(spec, Sequence) and not isinstance(spec, str):
        base = Harmonise(colors=tuple(spec))
    else:
        raise AssetError(
            f"palette must be True, a strength, a list of colours or a "
            f"Harmonise, not {spec!r}"
        )
    return base if strength is None else replace(base, strength=strength)


def palette_colors(spec: Harmonise) -> tuple[str, ...]:
    """Resolve the target hues, defaulting to the theme in force at build time."""
    if spec.colors:
        return tuple(spec.colors)
    from .. import current_theme  # late: inklet imports this package, not the reverse

    return tuple(current_theme().palette)


def harmonise(rgba: Any, spec: Harmonise, colors: Sequence[str]) -> Any:
    """Rotate each pixel's hue onto the nearest palette hue, keeping L* and C*."""
    np = numpy()
    if not colors or spec.strength <= 0.0:
        return rgba

    hues = _palette_hues(colors)
    if not hues:
        return rgba  # an all-grey palette has no hue to map onto

    lab = _to_lab(rgba[:, :, :3].astype(np.float64) / 255.0)
    lightness, a, b = lab[:, :, 0], lab[:, :, 1], lab[:, :, 2]
    chroma = np.hypot(a, b)
    angle = np.arctan2(b, a)

    target = _nearest_hue(angle, hues)
    # Fade the effect out as a pixel approaches neutral, so highlights and
    # shadows do not acquire a colour cast.
    amount = spec.strength * np.clip(chroma / max(spec.neutral_chroma, 1e-6), 0.0, 1.0)
    new_a = a + (chroma * np.cos(target) - a) * amount
    new_b = b + (chroma * np.sin(target) - b) * amount

    rgb = _to_rgb(np.dstack([lightness, new_a, new_b]))
    out = rgba.copy()
    out[:, :, :3] = np.clip(rgb * 255.0, 0.0, 255.0).round().astype(np.uint8)
    return out


def _palette_hues(colors: Sequence[str]) -> list[float]:
    """Palette hue angles in radians, in palette order. Near-neutral swatches
    are dropped: they have no hue to rotate anything onto."""
    import math

    hues = []
    for color in colors:
        _, a, b = to_lab(color)
        if math.hypot(a, b) >= 1.0:
            hues.append(math.atan2(b, a))
    return hues


def _nearest_hue(angle: Any, hues: Sequence[float]) -> Any:
    """Closest palette hue per pixel, compared the long way round the circle.

    Kept as a running best rather than a stacked argmin: an eight-colour
    palette over a twelve-megapixel photograph would otherwise allocate a
    gigabyte to answer a question that needs two arrays.
    """
    np = numpy()
    best = np.full(angle.shape, np.inf)
    chosen = np.zeros(angle.shape)
    for hue in hues:
        delta = np.abs(np.arctan2(np.sin(angle - hue), np.cos(angle - hue)))
        closer = delta < best      # strict, so the first swatch wins a tie
        best = np.where(closer, delta, best)
        chosen = np.where(closer, hue, chosen)
    return chosen


# -- colour space ---------------------------------------------------------


def _to_lab(rgb: Any) -> Any:
    np = numpy()
    linear = np.where(rgb <= _KNEE, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    xyz = linear @ np.array(_RGB_TO_XYZ, dtype=np.float64).T
    scaled = xyz / np.array(_D65, dtype=np.float64)
    f = np.where(scaled > _DELTA ** 3,
                 np.cbrt(np.maximum(scaled, 0.0)),
                 scaled / (3 * _DELTA ** 2) + 4 / 29)
    fx, fy, fz = f[:, :, 0], f[:, :, 1], f[:, :, 2]
    return np.dstack([116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)])


def _to_rgb(lab: Any) -> Any:
    np = numpy()
    lightness, a, b = lab[:, :, 0], lab[:, :, 1], lab[:, :, 2]
    fy = (lightness + 16) / 116
    f = np.dstack([fy + a / 500, fy, fy - b / 200])
    scaled = np.where(f > _DELTA, f ** 3, 3 * _DELTA ** 2 * (f - 4 / 29))
    xyz = scaled * np.array(_D65, dtype=np.float64)
    linear = xyz @ np.array(_XYZ_TO_RGB, dtype=np.float64).T
    linear = np.clip(linear, 0.0, 1.0)
    # The inverse of the knee used above, not the usual 0.0031308: encoding with
    # a different threshold from the one we decoded with would leave a residue
    # in the near-blacks on a strength=0 round trip.
    return np.where(linear <= _LINEAR_KNEE, linear * 12.92,
                    1.055 * np.maximum(linear, 0.0) ** (1 / 2.4) - 0.055)
