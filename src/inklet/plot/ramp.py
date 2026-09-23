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

from ..themes.color import ColorError, interpolate, interpolate_lab, to_hex, parse_color
from ..themes.palettes import Palette, palette

__all__ = ["Ramp", "ramp", "default_ramp", "SEQUENTIAL", "DIVERGING"]

SPACES = ("lab", "srgb")


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
    published in sRGB; it is not the better default.
    """
    if isinstance(stops, Ramp):
        return stops if stops.space == space else Ramp(stops.stops, space)
    if isinstance(stops, str):
        stops = palette(stops)
    if isinstance(stops, Palette):
        stops = stops.colors
    colors = tuple(to_hex(parse_color(c)) for c in stops)
    return Ramp(colors, space)


#: The ramp `Panel.matrix` uses when it is given none: magma run from pale
#: yellow (low) to deep purple (high), so the highest values are the darkest
#: cells on white paper. The near-black first stop is left out; the darkest
#: cell is then still distinct from black outlines and text drawn over it.
SEQUENTIAL = Ramp(tuple(reversed(palette("magma").colors[1:])))

#: The ramp `Panel.matrix` uses for data on both sides of a centre: Tol's
#: blue-white-red, with white at the centre value.
DIVERGING = Ramp(palette("tol-burd").colors)


def default_ramp(diverging: bool = False) -> Ramp:
    """The built-in sequential ramp, or the diverging one."""
    return DIVERGING if diverging else SEQUENTIAL
