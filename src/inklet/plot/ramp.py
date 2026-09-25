"""Continuous colour: a value in 0..1, a colour out.

The stops are sRGB swatches, as published. What happens *between* them is the
question, and the answer is CIELAB. Interpolating two saturated colours in sRGB
runs a straight line through the middle of the cube, which passes through
whatever desaturated sludge happens to lie there -- blue to red goes via a
muddy purple-grey, and the eye reads that dip as a feature of the data. CIELAB
is built so that equal steps look equal, so the same blend keeps its chroma and
changes at a steady perceived rate.

`inklet.themes` owns the colour space itself; this module is the thin part that
turns it into something a colorbar or a heatmap can call.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from ..themes.color import (
    ColorError, interpolate, interpolate_lab, interpolate_oklab, parse_color, to_hex,
)
from ..themes.palettes import Palette, palette

__all__ = ["Ramp", "ramp", "as_ramp", "default_ramp", "SEQUENTIAL", "DIVERGING"]

SPACES = ("lab", "oklab", "srgb")


@dataclass(frozen=True, slots=True)
class Ramp:
    """A colour ramp, sampled at t in 0..1. Call it, or ask it for `n` stops."""

    stops: tuple[str, ...]
    space: str = "lab"

    def __post_init__(self) -> None:
        if not self.stops:
            raise ColorError("a ramp needs at least one stop")
        if self.space not in SPACES:
            raise ColorError(
                f"unknown colour space {self.space!r}; expected one of {SPACES}"
            )

    def __call__(self, t: float) -> str:
        if self.space == "srgb":
            return interpolate(self.stops, t)
        if self.space == "oklab":
            return interpolate_oklab(self.stops, t)
        return interpolate_lab(self.stops, t)

    def sample(self, count: int) -> tuple[str, ...]:
        """`count` colours spanning the ramp, ends included."""
        if count < 1:
            raise ColorError(f"a ramp sample needs at least one colour, got {count}")
        if count == 1:
            return (self(0.5),)
        return tuple(self(i / (count - 1)) for i in range(count))

    def reversed(self) -> "Ramp":
        """The same colours end to end, for a scale that runs the other way."""
        return Ramp(tuple(reversed(self.stops)), self.space)


def ramp(stops: str | Palette | Sequence[str], *, space: str = "lab") -> Ramp:
    """A ramp from a palette, the name of one, or a list of colours.

    `space="srgb"` is the escape hatch for reproducing a ramp someone else
    published in sRGB; it is not the better default. `space="oklab"` blends
    in OKLab, which keeps hue steadier than CIELAB through saturated blues.
    Named maps such as "viridis" or "batlow" carry enough stops that all
    three spaces reproduce the published colours within CIEDE2000 < 1.
    """
    if isinstance(stops, Ramp):
        return stops if stops.space == space else Ramp(stops.stops, space)
    if isinstance(stops, str):
        stops = palette(stops)
    if isinstance(stops, Palette):
        stops = stops.colors
    colors = tuple(to_hex(parse_color(c)) for c in stops)
    return Ramp(colors, space)


def as_ramp(value):
    """`value` as something callable on 0..1: a palette name, a `Palette` or a
    list of colours become a `Ramp`; a `Ramp` or any other callable passes
    through unchanged. `None` stays `None`, meaning "use the default"."""
    if value is None or isinstance(value, Ramp):
        return value
    if isinstance(value, (str, Palette)) or not callable(value):
        return ramp(value)
    return value


#: The ramp `Panel.matrix` uses when it is given none: magma run from pale
#: yellow (low) to deep purple (high), so the highest values are the darkest
#: cells on white paper. The near-black first stop is left out; the darkest
#: cell is then still distinct from black outlines and text drawn over it.
#: These are the stops `palette("magma")` had before it gained the dense
#: published table, kept literally so the default picture does not move.
SEQUENTIAL = Ramp((
    "#fcfdbf", "#fec488", "#fc8961", "#e75263", "#b73779",
    "#832681", "#51127c", "#1d1147",
))

#: The ramp `Panel.matrix` uses for data on both sides of a centre: Tol's
#: blue-white-red, with white at the centre value.
DIVERGING = Ramp(palette("tol-burd").colors)


def default_ramp(diverging: bool = False) -> Ramp:
    """The built-in sequential ramp, or the diverging one."""
    return DIVERGING if diverging else SEQUENTIAL
