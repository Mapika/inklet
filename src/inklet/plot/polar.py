"""The polar plot area: a disc, or a fan cut out of one, that data maps into.

A polar panel is the same bargain `plot.panel` makes -- a region of a size you
choose, scales that map data onto it, furniture hanging off its edge -- with
the rectangle replaced by a circle. `radius` sizes the *data* region, exactly
as `panel(width, height)` does, so the finished node is always wider than the
number you passed: the theta labels, the r labels and any key stand outside
the rim.

Three decisions carry the module.

**One angle convention, and it is the library's.** `inklet.draw.shapes` measures
page angles from east, increasing clockwise, because y grows downward here as
it does in SVG. A polar panel keeps that for `zero=`, which is where theta = 0
points: `zero="up"` and `zero=-90` are the same instruction. What varies by
field is the *data* convention, and that is `winding=`: `"ccw"` is the
mathematical default, `"cw"` the compass one, and a head-direction figure that
wants 0 degrees at the top going clockwise writes `zero="up", winding="cw"`
and never converts an angle by hand again.

**Ticks live on an angular lattice, not the 1/2/5 one.** `nice_ticks` is right
for a quantity and wrong for a turn: nobody labels a circle at 0, 50, 100,
150. Degrees step by 15, 30, 45, 60, 90; radians by a twelfth, an eighth, a
sixth, a quarter, a third or a half of pi, and are *written* as fractions of
pi, because `1.5707963` on an axis is a number the reader has to decode.

**A label is pushed out along its own radius until its box clears the rim.**
The rectangular axis has four sides and four answers; a circle has one for
every angle. Placing a label by a compass anchor quantises that to eight or
sixteen directions and leaves the in-between ones either touching the rim or
floating clear of it. Instead the distance from the label's centre to its own
boundary is computed *in the direction it is being pushed* -- the exact
continuous form of what a compass anchor approximates -- so twelve theta
labels round a 26mm disc all sit the same 0.6mm off the ticks. See
`_outward`.

    import inklet

    tuning = [(a, 2 + 8 * (a % 180 == 90)) for a in range(0, 360, 30)]
    p = inklet.polar(26, r=(0, 12), zero="up", winding="cw")
    p.grid().line(tuning).theta_axis(count=8).r_axis(count=3)
    inklet.figure(width=70).add(p.build()).save("tuning.svg")

The built node publishes the same two notes a rectangular panel does --
`plot_area` (the upright box round the disc or the fan) and `scale_domain`
(the r domain) -- so `inklet.letters`, `inklet.row`, `OFF_PANEL` and `KEY_MISMATCH`
all keep working without knowing this module exists. A `PolarPanel` is not a
`Panel`, so `inklet.row([...])` takes its `build()` rather than the panel itself.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Iterable, Sequence

from ..core import Diagram, DiagramError, ORIGIN, Rect, Vec2, mm
from ..draw.clip import clip as draw_clip
from ..draw.coords import active_theme, as_drawn, declare_area, drawn_group
from ..draw.path import path as draw_path, polyline
from ..draw.place import place as draw_place
from ..draw.shapes import (
    MARK_KIND, MARK_LINE_KIND, arc_cubics, marker as make_marker,
    sector as draw_sector,
)
from ..themes.color import mix
from . import marks as _marks
from .axis import (
    AXIS_KIND, AXIS_LABEL_KIND, SPINE_KIND, TICK_KIND, TICK_LABEL_KIND,
    _CLEAR_OF_TYPE, _LABEL_PAD_OF_TYPE, _PAD_OF_TYPE, _TICK_OF_TYPE,
    text_node, tick_texts, tick_values,
)
from .key import SWATCH_OF_TYPE, legend as make_legend
from .panel import AREA_KIND, GRID_KIND, PANEL_KIND, TITLE_KIND
from .scale import Linear, Scale, _declare_domain, format_number, linear
from .series import SeriesKey, merge_keys, swatch_for

__all__ = [
    "PolarPanel", "Theta", "THETA_UNITS", "WINDINGS", "ZERO_DIRECTIONS",
    "circular_histogram", "circular_mean", "polar", "theta_ticks",
]

#: Where theta = 0 points, in page degrees -- from east, increasing clockwise,
#: the one convention `inklet.draw.shapes` already pays for. The names are the
#: two vocabularies people actually write: compass points and screen edges.
ZERO_DIRECTIONS: dict[str, float] = {
    "e": 0.0, "east": 0.0, "right": 0.0,
    "n": -90.0, "north": -90.0, "up": -90.0, "top": -90.0,
    "w": 180.0, "west": 180.0, "left": 180.0,
    "s": 90.0, "south": 90.0, "down": 90.0, "bottom": 90.0,
}

#: Which way theta runs on the page. "ccw" is the mathematical convention and
#: the default; "cw" is what a compass, a wind rose and a head-direction plot
#: use, and picking it is the whole reason this is a parameter.
WINDINGS = ("ccw", "cw")

#: The unit theta is given in, and the size of one turn in it.
THETA_UNITS: dict[str, float] = {"deg": 360.0, "rad": 2.0 * math.pi,
                                 "turn": 1.0, "grad": 400.0}

#: Tick steps for an axis in degrees. The 1/2/5 lattice is wrong for a turn --
#: it cannot say "every 45 degrees" -- so the lattice is the one a protractor
#: is printed with, and every step divides 360.
_DEG_STEPS = (1.0, 2.0, 5.0, 10.0, 15.0, 20.0, 30.0, 45.0, 60.0, 90.0, 120.0,
              180.0, 360.0)

#: Tick steps for an axis in radians, as fractions of pi. Same idea, in the
#: units the labels are written in: a tick every pi/6 reads as a twelfth of a
#: turn, and a tick every 0.5 reads as nothing.
_RAD_FRACTIONS = (Fraction(1, 12), Fraction(1, 8), Fraction(1, 6),
                  Fraction(1, 4), Fraction(1, 3), Fraction(1, 2),
                  Fraction(1), Fraction(2))

#: Tick steps for an axis measured in turns, and for gradians via the same
#: shape. Halves, thirds, quarters, sixths, eighths, twelfths.
_TURN_FRACTIONS = (Fraction(1, 36), Fraction(1, 24), Fraction(1, 16),
                   Fraction(1, 12), Fraction(1, 8), Fraction(1, 6),
                   Fraction(1, 4), Fraction(1, 3), Fraction(1, 2), Fraction(1))

#: Page degrees per straight segment when a polar line is densified. At a 30mm
#: radius a 3 degree chord departs from its arc by 10 micrometres -- a fifth of
#: what the thinnest line this library will draw is wide.
_ARC_STEP = 3.0

#: How much of the radial extent a resultant vector of length 1 reaches, when
#: `mean_vector` is not told otherwise. The whole of it: R = 1 means every
#: sample pointed the same way, and that is the rim.
_RESULTANT_FULL = 1.0

#: A polar gridline is read *through* the data far more than a rectangular one
#: is -- every ring crosses every curve -- so the rings and spokes are mixed a
#: little further towards paper than `theme.grid` alone.
_GRID_TINT = 0.35

#: How close two floats have to be to count as the same angle, in page degrees.
_EPS = 1e-9


# -- angles ---------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Theta:
    """The angular scale: data angles in, page degrees out.

    Not a `Scale` -- `Scale.map` answers in millimetres along an axis and this
    answers in degrees round a circle, and a class that returned the wrong
    kind of number to `plot.axis` would be a bug waiting for a caller. It
    carries the same four things a scale does: a domain, what the numbers
    mean, how to tick it and how to write those ticks.
    """

    domain: tuple[float, float] = (0.0, 360.0)
    unit: str = "deg"
    #: Page degrees where theta = 0 points, `inklet.draw.shapes`' convention:
    #: from east, increasing clockwise. `-90` is up.
    zero: float = 0.0
    winding: str = "ccw"

    def __post_init__(self) -> None:
        if self.unit not in THETA_UNITS:
            raise DiagramError(
                f"unknown angle unit {self.unit!r}; expected one of "
                f"{', '.join(sorted(THETA_UNITS))}")
        if self.winding not in WINDINGS:
            raise DiagramError(
                f"winding is 'ccw' or 'cw', not {self.winding!r}")
        if self.turn <= 0:                                  # pragma: no cover
            raise DiagramError(f"a turn of {self.unit!r} has no size")

    @property
    def turn(self) -> float:
        """One whole revolution, in this scale's own unit."""
        return THETA_UNITS[self.unit]

    @property
    def sign(self) -> float:
        """+1 when rising theta goes clockwise on the page, -1 when it does not.

        Page degrees already increase clockwise, so this is the whole of the
        winding: nothing else in the module tests `winding` by name.
        """
        return 1.0 if self.winding == "cw" else -1.0

    def page(self, value: float) -> float:
        """One data angle as page degrees, ready for `draw.shapes`."""
        return self.zero + self.sign * float(value) * 360.0 / self.turn

    def unpage(self, degrees: float) -> float:
        """The inverse of `page`, for a reader turning a picked angle back."""
        return (degrees - self.zero) / self.sign * self.turn / 360.0

    @property
    def span(self) -> float:
        """The signed extent of the view, in data units."""
        return self.domain[1] - self.domain[0]

    @property
    def sweep(self) -> float:
        """The signed extent of the view, in page degrees."""
        return self.sign * self.span * 360.0 / self.turn

    @property
    def full(self) -> bool:
        """Whether the view is a whole disc rather than a fan."""
        return abs(self.sweep) >= 360.0 - 1e-6

    def ticks(self, count: int = 8) -> tuple[float, ...]:
        """Angles to label, on the angular lattice. See `theta_ticks`."""
        return theta_ticks(self.domain[0], self.domain[1], count,
                           unit=self.unit, closed=not self.full)

    def labels(self, values: Sequence[float]) -> tuple[str, ...]:
        """How a set of tick angles is written.

        Degrees get a degree sign, radians get fractions of pi, and turns get
        the bare number -- each the form the reader of that unit expects.
        """
        if self.unit == "rad":
            return tuple(_pi_label(v) for v in values)
        suffix = "°" if self.unit == "deg" else ""
        return tuple(format_number(v) + suffix for v in values)

    def contains(self, value: float) -> bool:
        """Whether a data angle lies in the view, wrapping for a full disc."""
        if self.full:
            return True
        low, high = sorted(self.domain)
        return low - 1e-9 <= value <= high + 1e-9


def theta_ticks(low: float, high: float, count: int = 8, *, unit: str = "deg",
                closed: bool = False) -> tuple[float, ...]:
    """Angles a reader can divide in their head, between `low` and `high`.

    The lattice is angular, not decimal: whole divisors of a turn, so an axis
    is labelled every 30 degrees or every pi/4 and never every 0.7 radians.
    `count` is a target number of intervals, and the step chosen is the
    smallest lattice step that does not produce more than that many.

    `closed=False` -- the case for a whole disc -- drops a tick that lands one
    full turn from the first, because 360 degrees and 0 degrees are the same
    spoke and labelling it twice puts two numbers on one tick.
    """
    if unit not in THETA_UNITS:
        raise DiagramError(f"unknown angle unit {unit!r}")
    span = abs(high - low)
    if span <= 0:
        return (float(low),)
    step = _lattice_step(span / max(count, 1), unit, span)
    lo, hi = (low, high) if low <= high else (high, low)
    first = math.ceil(lo / step - 1e-9)
    last = math.floor(hi / step + 1e-9)
    values = [k * step for k in range(first, last + 1)]
    if not closed and len(values) > 1:
        turn = THETA_UNITS[unit]
        if abs(abs(values[-1] - values[0]) - turn) < 1e-9:
            values.pop()
    return tuple(0.0 if v == 0 else v for v in values)


def _lattice_step(target: float, unit: str, span: float) -> float:
    """The smallest angular step at least `target` wide.

    Past the end of the lattice the step is the whole span, which is the only
    honest answer to "tick this 700 degree axis every 400 degrees": two ticks,
    at the ends.
    """
    if unit == "deg":
        candidates = [float(s) for s in _DEG_STEPS]
    elif unit == "rad":
        candidates = [float(f) * math.pi for f in _RAD_FRACTIONS]
    else:
        candidates = [float(f) * THETA_UNITS[unit] for f in _TURN_FRACTIONS]
    for step in candidates:
        if step >= target * (1.0 - 1e-9):
            return step
    return max(span, candidates[-1])


def _pi_label(value: float) -> str:
    """A radian angle written as a fraction of pi.

    Falls back to the plain number when the angle is not a simple fraction of
    one -- a caller's own `ticks=` may be any angle at all, and `0.37π` is a
    worse label than `1.16`.
    """
    if abs(value) < 1e-12:
        return "0"
    frac = Fraction(value / math.pi).limit_denominator(48)
    if abs(float(frac) * math.pi - value) > 1e-9 * max(1.0, abs(value)):
        return format_number(value)
    sign = "-" if frac.numerator < 0 else ""
    top = abs(frac.numerator)
    head = "" if top == 1 else str(top)
    tail = "" if frac.denominator == 1 else f"/{frac.denominator}"
    return f"{sign}{head}π{tail}"


# -- circular statistics --------------------------------------------------


def circular_mean(angles: Sequence[float], weights: Sequence[float] | None = None,
                  *, unit: str = "deg", order: int = 1) -> tuple[float, float]:
    """The mean direction of a set of angles, and how concentrated they are.

    Returns `(mean, R)`. The mean is in the same unit as the input, in
    `[0, one turn / order)`. `R` is the resultant length: 1 when every sample
    points the same way, 0 when they cancel exactly. It is the number a
    head-direction or orientation figure reports beside the arrow, and it is
    not the standard deviation of the numbers -- averaging 359 and 1
    arithmetically gives 180, which is the reason this function exists.

        mean, R = inklet.circular_mean(spikes, unit="deg")

    `weights` makes it the mean of a *histogram* rather than of a sample:
    pass the bin centres as `angles` and the counts as `weights`, which is how
    a rose's arrow is computed.

    **`order=2` is the orientation statistic**, and a figure about gratings,
    dendrites or fibre alignment needs it. Direction and orientation are
    different quantities: a cell that answers equally to 90 and 270 degrees is
    perfectly *oriented* and has no *direction*, and order 1 reports its
    resultant as zero -- correctly, and uselessly. Doubling the angles before
    averaging and halving the answer afterwards (Batschelet's axial mean) puts
    the two lobes on top of each other, and the R that comes back is the
    orientation selectivity every such paper prints. The mean is then in the
    half turn, since 20 and 200 degrees are the same orientation.
    """
    if unit not in THETA_UNITS:
        raise DiagramError(f"unknown angle unit {unit!r}")
    data = [float(a) for a in angles]
    if not data:
        raise DiagramError("circular_mean() was given no angles")
    if weights is None:
        w = [1.0] * len(data)
    else:
        w = [float(v) for v in weights]
        if len(w) != len(data):
            raise DiagramError(
                f"weights= has {len(w)} values for {len(data)} angles")
    total = math.fsum(w)
    if total <= 0:
        raise DiagramError("circular_mean() needs weights that sum above zero")
    if order < 1:
        raise DiagramError(f"circular_mean(order=) is 1 or more, got {order}")
    turn = THETA_UNITS[unit]
    k = order * 2 * math.pi / turn
    # fsum rather than sum: a rose with ten thousand counts in it is exactly
    # the case where the running error shows up in the third decimal of R,
    # and R is a number figures print.
    cx = math.fsum(wi * math.cos(a * k) for a, wi in zip(data, w))
    cy = math.fsum(wi * math.sin(a * k) for a, wi in zip(data, w))
    resultant = math.hypot(cx, cy) / total
    period = turn / order
    mean = (math.atan2(cy, cx) / k) % period
    # `%` on a float can hand back the modulus itself: atan2 of a hair below
    # zero divided by k is a hair below zero, and `-1e-17 % 360.0` is exactly
    # 360.0 once the subtraction rounds. The documented range is half open,
    # and a mean of 360 degrees printed in a caption is a bug report.
    return (0.0 if mean >= period else mean), resultant


def circular_histogram(angles: Sequence[float], bins: int = 12, *,
                       unit: str = "deg",
                       domain: tuple[float, float] | None = None,
                       density: bool = False
                       ) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """Bin angles into equal sectors: `(centres, heights)` for `rose()`.

    The bins tile the whole turn by default, and a sample is placed by its
    angle modulo that turn -- which is the difference between this and
    `plot.histogram`, and the reason a wind rose cannot be built from the
    rectangular one. Give `domain=` to bin a fan instead, and anything outside
    it is dropped rather than wrapped.

    `density=True` divides by the sample count, so the bars are fractions and
    two roses of different sample sizes can be read against each other.
    """
    if bins < 1:
        raise DiagramError(f"a circular histogram needs at least one bin, got {bins}")
    turn = THETA_UNITS.get(unit)
    if turn is None:
        raise DiagramError(f"unknown angle unit {unit!r}")
    low, high = (0.0, turn) if domain is None else (float(domain[0]), float(domain[1]))
    if low > high:
        low, high = high, low
    width = (high - low) / bins
    if width <= 0:
        raise DiagramError(f"a circular histogram needs a domain with width, got {domain!r}")
    wraps = domain is None
    counts = [0.0] * bins
    kept = 0
    for value in angles:
        a = float(value)
        if wraps:
            a = low + (a - low) % turn
        elif not low - 1e-9 <= a <= high + 1e-9:
            continue
        index = min(bins - 1, max(0, int((a - low) / width)))
        counts[index] += 1.0
        kept += 1
    if density and kept:
        counts = [c / kept for c in counts]
    centres = tuple(low + width * (i + 0.5) for i in range(bins))
    return centres, tuple(counts)


# -- the panel ------------------------------------------------------------


@dataclass
class PolarPanel:
    """A disc, or a fan of one, plus the scales that map data into it.

    Build it with `polar()`. Like `Panel`, every method that adds something
    returns the panel, so a plot reads as a sentence, and `build()` turns it
    into a `Diagram`. Data points are `(theta, r)` pairs throughout, in that
    order, because that is the order the two axes are named in.
    """

    #: The rim, in millimetres from the pole: what `panel(width, height)` is to
    #: a rectangular panel.
    radius: float
    r: Scale
    theta: Theta
    #: A hole at the pole, in millimetres. A rose whose bars start at the
    #: centre puts all its thin ends in one place; a donut separates them.
    hole: float = 0.0
    #: Whether data is cut to the disc. Off by default, exactly as `Panel`
    #: leaves it off, and for the same reason: a mark on the rim should stay a
    #: whole mark.
    clip: bool = False
    _under: list[Diagram] = field(default_factory=list, repr=False)
    _content: list[Diagram] = field(default_factory=list, repr=False)
    _over: list[Diagram] = field(default_factory=list, repr=False)
    _title: tuple[Diagram, float] | None = field(default=None, repr=False)
    _built: Diagram | None = field(default=None, repr=False, compare=False)
    _keys: list[SeriesKey] = field(default_factory=list, repr=False,
                                   compare=False)
    #: Page angles of the spokes last drawn, so an r axis nobody positioned
    #: can stand between two of them rather than on one. Written by `grid`
    #: and by `theta_axis`, so in the usual order the axis's ticks -- the ones
    #: that carry labels, and so the ones worth missing -- have the last word.
    _spokes: list[float] = field(default_factory=list, repr=False,
                                 compare=False)
    #: `(page angle, box)` for each theta label drawn, in panel coordinates,
    #: so the r axis's name can be pushed clear of the ring of numbers rather
    #: than into it. Written by `theta_axis`.
    _ring: list[tuple[float, Rect]] = field(default_factory=list, repr=False,
                                            compare=False)

    # -- coordinates ------------------------------------------------------

    @property
    def area(self) -> Rect:
        """The upright box round the data region, in panel coordinates.

        For a whole disc that is the square on the rim. For a fan it is the
        box round the wedge, which is genuinely smaller -- a 180 degree fan
        opening upward is half as tall as it is wide, and declaring the square
        would hang its panel letter a centimetre above the ink.
        """
        return _sector_bounds(self.radius, self.hole, *self._page_ends())

    @property
    def centre(self) -> Vec2:
        """The pole, in panel coordinates. Always the local origin."""
        return ORIGIN

    def _page_ends(self) -> tuple[float, float]:
        """The two ends of the view, in page degrees."""
        return self.theta.page(self.theta.domain[0]), \
            self.theta.page(self.theta.domain[1])

    def angle(self, theta: float) -> float:
        """One data angle in page degrees -- east is 0, clockwise is positive."""
        return self.theta.page(theta)

    def reach(self, r: float) -> float:
        """One data radius in millimetres from the pole."""
        return self.r.map(r)

    def point(self, theta, r) -> Vec2:
        """One data point in panel coordinates, in millimetres."""
        radians = math.radians(self.theta.page(theta))
        distance = self.r.map(r)
        return Vec2(math.cos(radians) * distance, math.sin(radians) * distance)

    def map(self, points: Iterable[Sequence]) -> tuple[Vec2, ...]:
        """`point()` over a sequence: `(theta, r)` pairs in, millimetres out."""
        return tuple(self.point(*p) for p in points)

    # -- content ----------------------------------------------------------

    def draw(self, *items: Diagram, clip: bool | None = None) -> "PolarPanel":
        """Add content already expressed in panel coordinates."""
        return self._add(self._content, [as_drawn(item) for item in items], clip)

    def under(self, *items: Diagram, clip: bool | None = None) -> "PolarPanel":
        """Add content beneath the data."""
        return self._add(self._under, [as_drawn(item) for item in items], clip)

    def over(self, *items: Diagram, clip: bool | None = None) -> "PolarPanel":
        """Add content above the data."""
        return self._add(self._over, [as_drawn(item) for item in items], clip)

    def place(self, items, *, clip: bool | None = None) -> "PolarPanel":
        """`draw.place()` in data coordinates: `((theta, r), diagram)` pairs."""
        mapped = [item if isinstance(item, Diagram)
                  else (self.point(*item[0]), item[1]) for item in items]
        return self.draw(draw_place(mapped), clip=clip)

    def _add(self, into: list[Diagram], nodes: Sequence[Diagram],
             clip: bool | None) -> "PolarPanel":
        into.extend(self._to_area(nodes, clip))
        return self._touched()

    def _to_area(self, nodes: Sequence[Diagram],
                 clip: bool | None) -> list[Diagram]:
        """`nodes`, cut to the disc or the fan when this panel clips.

        `inklet.clip` cuts against a *convex polygon*, and a circle is not one, so
        the boundary is a polygon through enough vertices that its error is
        under a printer's resolution -- and **circumscribed**, touching the rim
        at each vertex from outside, so the approximation can only ever keep a
        shade too much rather than eat data that was inside the domain.
        """
        if not (self.clip if clip is None else clip):
            return list(nodes)
        boundary = self._boundary()
        return [draw_clip(node, boundary) for node in nodes]

    def _boundary(self) -> list[Vec2]:
        """The clipping polygon: the fan, circumscribed about its own arc.

        A whole disc is convex and so is a fan of at most a half turn. Past
        that the wedge is re-entrant at the pole and Sutherland-Hodgman would
        return a plausible wrong answer, so the boundary falls back to the
        circumscribed polygon of the whole disc -- which clips to the rim, the
        part of the boundary a caller asking for `clip=True` on a 270 degree
        fan is actually worried about.
        """
        a0, a1 = self._page_ends()
        if self.theta.full or abs(a1 - a0) > 180.0 + 1e-9:
            a0, a1, wedge = 0.0, 360.0, False
        else:
            wedge = True
        steps = max(4, math.ceil(abs(a1 - a0) / 6.0))
        step = (a1 - a0) / steps
        # Circumscribed: pushing each vertex out by 1/cos(half a step) puts the
        # polygon's edges tangent to the circle instead of chord-secant to it.
        out = self.radius / math.cos(math.radians(step) / 2.0)
        ring = [Vec2(math.cos(math.radians(a0 + step * i)),
                     math.sin(math.radians(a0 + step * i))) * out
                for i in range(steps + 1)]
        return ring + [ORIGIN] if wedge else ring

    def _touched(self) -> "PolarPanel":
        self._built = None
        return self

    # -- furniture --------------------------------------------------------

    def background(self, **style) -> "PolarPanel":
        """Fill the data region, beneath everything already in it."""
        node = self._region(kind=AREA_KIND, **style)
        self._under.insert(0, as_drawn(node))
        return self._touched()

    def spine(self, *, rim: bool = True, edges: bool | None = None,
              **style) -> "PolarPanel":
        """The rim, and for a fan the two straight edges, drawn over the data.

        Styled as a spine rather than as the area: it is the outer axis of the
        panel, and it should match the ticks that hang off it. `edges` defaults
        to drawing them on a fan and not on a whole disc, where there is
        nothing to draw.
        """
        a0, a1 = self._page_ends()
        lines: list[Diagram] = []
        if rim:
            lines.append(_arc_path(self.radius, a0, a1, kind=SPINE_KIND, **style))
        if edges if edges is not None else not self.theta.full:
            for angle in (a0, a1):
                lines.append(polyline((_polar(self.hole, angle),
                                       _polar(self.radius, angle)),
                                      kind=SPINE_KIND, **style))
        self._over.extend(as_drawn(line) for line in lines)
        return self._touched()

    #: `outline` is `Panel`'s name for the same thing, and a reader who has
    #: written one should not have to look up the other.
    outline = spine

    def grid(self, *, r: bool = True, theta: bool = True, r_count: int = 4,
             theta_count: int = 8, r_ticks: Sequence | None = None,
             theta_ticks: Sequence | None = None, **style) -> "PolarPanel":
        """Rings at the r ticks and spokes at the theta ticks, under the data.

        The values come from the same tick machinery the axes use, so a ring
        always has a number against it -- the rule `plot.Panel.grid` states and
        the one polar plots break most often, by drawing a ring per unit and
        labelling every fifth.

        A ring at the innermost r is the pole itself on a panel with no hole,
        and is dropped: a dot at the centre of a polar plot reads as data.
        """
        rings = list(self.r.ticks(r_count) if r_ticks is None else r_ticks) \
            if r else []
        spokes = list(self.theta.ticks(theta_count) if theta_ticks is None
                      else theta_ticks) if theta else []
        a0, a1 = self._page_ends()
        lines: list[Diagram] = []
        for value in rings:
            distance = self.r.map(value)
            if distance <= max(self.hole, 1e-6) + 1e-9 or distance > self.radius + 1e-9:
                continue
            lines.append(_arc_path(distance, a0, a1, kind=GRID_KIND, **style))
        for value in spokes:
            if not self.theta.contains(value):
                continue
            angle = self.theta.page(value)
            lines.append(polyline((_polar(self.hole, angle),
                                   _polar(self.radius, angle)),
                                  kind=GRID_KIND, **style))
        drawn = [self.theta.page(v) for v in spokes if self.theta.contains(v)]
        if drawn:
            self._spokes = drawn
        self._under.extend(as_drawn(line) for line in lines)
        return self._touched()

    def theta_axis(self, *, count: int = 8, ticks: Sequence | None = None,
                   labels: bool = True, format=None, label: str | Diagram | None = None,
                   spine: bool = True, tick_size: float | str | None = None,
                   pad: float | str | None = None,
                   label_pad: float | str | None = None,
                   thin: bool = True, curved: bool = False,
                   kind: str = AXIS_KIND, **style) -> "PolarPanel":
        """Ticks round the rim, their angles written outside it.

        Every label is pushed straight out along its own radius until its box
        clears the ticks, so the set sits on a common offset rather than on a
        common circle -- a wide label like `270°` needs more room at the west
        of a disc than a tall one needs at the north, and giving them all the
        same circle either wastes a millimetre or laps the rim.

        `thin` drops every second or third *label* when they would collide,
        the stride chosen so it still divides the turn evenly: an axis labelled
        0, 45, 90 and then 180 has lost its rhythm and the reader counts wrong.
        Only strides that keep the rhythm are tried, which on a whole disc
        means strides that divide the tick count.

        **The ticks stay.** `plot.axis` drops the tick with its label, because
        along a straight axis an unlabelled tick is a value the reader cannot
        name. A circle is a clock face: the marks are a uniform rhythm the
        reader counts round, and keeping all twenty-four while labelling twelve
        is how every compass rose and every dial is drawn. It also keeps the
        ticks agreeing with `grid()`, which draws a spoke per tick and has no
        labels to collide.

        The rim is this axis's spine -- it is the line the ticks hang off, the
        way the bottom of a rectangular panel is -- so it is drawn here and
        `spine=False` turns it off. `PolarPanel.spine()` draws it alone, for a
        panel with no theta ticks at all.

        `label` is the name of the quantity, set outside the numbers: at the
        middle of a fan, and below a whole disc, which has no middle.

        `curved=True` sets the numbers *along* the rim instead of upright,
        with `inklet.text_on_arc`, which is what a compass rose and a dial do.
        It is off by default because a ring of upright numbers is easier to
        read at small sizes and is what every plotting library the reader has
        seen produces; it earns its keep on a dial with long labels, where
        upright text at 45 degrees wastes a corner of the figure. **Which
        labels survive `thin` does not change**: the stride is chosen from the
        upright boxes either way, so turning curving on rotates the numbers
        and does not silently relabel the axis.

        A curved label eats angular room rather than radial, so on a crowded
        ring it reaches towards its neighbours' spokes: at twelve ticks on an
        18mm disc a curved `330°` laps the plate behind the outermost r tick,
        which the default `at` puts halfway between two spokes. Give `r_axis`
        an explicit `at=` or `plate=False` if that pair reports.
        """
        theme = active_theme()
        values = tuple(self.theta.ticks(count) if ticks is None else ticks)
        values = tuple(v for v in values if self.theta.contains(v))
        if values:
            self._spokes = [self.theta.page(v) for v in values]
        reach = _TICK_OF_TYPE * theme.font_size if tick_size is None else mm(tick_size)
        gap = _PAD_OF_TYPE * theme.font_size if pad is None else mm(pad)
        texts = (tuple(format(v) for v in values) if callable(format)
                 else _formatted(self.theta.labels(values), format))
        items: list = []
        if spine:
            a0, a1 = self._page_ends()
            items.append(_arc_path(self.radius, a0, a1, kind=SPINE_KIND))
        for value in values:
            angle = self.theta.page(value)
            items.append(polyline((_polar(self.radius, angle),
                                   _polar(self.radius + reach, angle)),
                                  kind=TICK_KIND))
        placed: list[tuple[Vec2, Diagram, float, Diagram | None]] = []
        if labels:
            edge = max(reach, 0.0) + gap
            for value, text in zip(values, texts):
                if not text:
                    continue
                node = text_node(text, theme.font_size_small, TICK_LABEL_KIND,
                                 markup=False)
                angle = self.theta.page(value)
                tip = _polar(self.radius + edge, angle)
                bent = (_curved_label(text, self.radius + edge, angle, theme)
                        if curved else None)
                placed.append(_outward(node, tip, angle) + (angle, bent))
            placed = _keep_round(placed, _CLEAR_OF_TYPE * theme.font_size,
                                 self.theta.full, thin)
            # A curved label is already drawn in the panel's own coordinates,
            # so it goes in bare and `place` puts it back where `text_on_arc`
            # put it; an upright one is a node plus the point to centre it on.
            items.extend(bent if bent is not None else (at, node)
                         for at, node, _a, bent in placed)
            self._ring = [(a, bent.bbox if bent is not None
                           else _shifted(node.bbox, at))
                          for at, node, a, bent in placed]
        if label is not None:
            items.append(self._theta_name(label, placed, reach, gap,
                                          label_pad, theme))
        self._over.append(as_drawn(draw_place(items, kind=kind, origin=(0, 0),
                                              **style)))
        return self._touched()

    def _theta_name(self, label, placed, reach: float, gap: float,
                    label_pad, theme):
        """The name of the angular quantity, outside its numbers.

        Upright and centred on the middle of the view, at the radius the
        widest tick label reaches -- so it clears them all rather than the one
        it happens to sit past. Curving it along the rim, as `curved=True`
        does for the numbers, is the typographically better answer and is not
        done: a `text_on_arc` run carries its own position, and everything
        here places a node on a point it computed. It wants its own path
        through `theta_axis`; see BACKLOG.
        """
        node = (label if isinstance(label, Diagram)
                else text_node(label, theme.font_size, AXIS_LABEL_KIND))
        pad = _LABEL_PAD_OF_TYPE * theme.font_size if label_pad is None \
            else mm(label_pad)
        far = max((at.length + _outward_reach(n.bbox, a)
                   for at, n, a, *_ in placed),
                  default=self.radius + max(reach, 0.0) + gap)
        # A whole disc has no middle to centre the name on, so it goes under
        # the plot, where a rectangular panel's x axis name goes.
        middle = 90.0 if self.theta.full \
            else self.theta.page(sum(self.theta.domain) / 2.0)
        tip = _polar(far + pad, middle)
        at, node = _outward(node, tip, middle)
        return (at, node)

    def r_axis(self, *, at: float | None = None, count: int = 4,
               ticks: Sequence | None = None, labels: bool = True,
               format=None, si: bool = False, label: str | Diagram | None = None,
               side: str | None = None, spine: bool = False,
               plate: bool | None = None,
               tick_size: float | str | None = None,
               pad: float | str | None = None,
               label_pad: float | str | None = None,
               kind: str = AXIS_KIND, **style) -> "PolarPanel":
        """The radial scale, written along one spoke.

        `at` is the **data angle** the spoke sits on. On a fan it defaults to
        the start of the view -- one of the two straight edges, which is where
        the numbers belong. On a whole disc there is no edge, so it defaults
        half a default tick step round from the zero direction: 22.5 degrees,
        which falls between two spokes at 4, 8 and 24 theta ticks and clear of
        the zero label at all of them. A busy plot wants it moved somewhere
        quieter still, and that is what the argument is for.

        The labels stand beside the spoke rather than on it, on the side away
        from the data for a fan and on the clockwise side for a whole disc.
        `side="cw"` or `"ccw"` overrides. They stay upright at every angle: a
        radius is read as a quantity, and a quantity written sideways is
        harder to read than one written across its own axis.

        `label` is the name of the quantity, set *along* the spoke and flipped
        as needed so it never runs upside-down.

        **The numbers are knocked out of what is behind them.** A radial axis
        runs *through* the picture -- there is no outside for it to stand in --
        so its labels land on gridlines, on the rim, and on the data. The one
        that lands on the rim cannot be nudged clear of it either: at the
        outermost tick the direction the label is offset in is the tangent, so
        moving it slides it along the circle it is trying to escape. An opaque
        tile behind each number is the answer a contour label has used for a
        century, and it costs one unstroked rectangle per tick.
        `plate=False` turns it off, which is right for an axis drawn on a
        panel with no grid and no rim.

        **A tick at the pole is dropped.** A tick is a mark across the axis at
        one radius, and at radius zero there is no across -- every angle owns
        that point. The number against it labels the one place a mean vector,
        a spiral or any curve through the origin has to pass, and it is in the
        way of all three. `hole=` gives the innermost value a circle to be
        written against, if it needs one.
        """
        theme = active_theme()
        angle = (self._quiet_spoke() if at is None else self.theta.page(at))
        values = tuple(tick_values(self.r, count) if ticks is None else ticks)
        texts = tick_texts(self.r, values, format, si)
        reach = _TICK_OF_TYPE * theme.font_size if tick_size is None else mm(tick_size)
        gap = _PAD_OF_TYPE * theme.font_size if pad is None else mm(pad)
        out = _perpendicular(angle, self._label_side(side))
        items: list = []
        if spine:
            items.append(polyline((_polar(self.hole, angle),
                                   _polar(self.radius, angle)),
                                  kind=SPINE_KIND))
        written: list[tuple[Vec2, Diagram]] = []
        for value, text in zip(values, texts):
            distance = self.r.map(value)
            if not self.hole - 1e-9 <= distance <= self.radius + 1e-9:
                continue
            if distance <= 1e-9:
                continue        # the pole carries no tick; see the docstring
            foot = _polar(distance, angle)
            items.append(polyline((foot, foot + out * reach), kind=TICK_KIND))
            if not labels or not text:
                continue
            node = text_node(text, theme.font_size_small, TICK_LABEL_KIND,
                             markup=False)
            if plate is not False:
                node = _knockout(node, theme)
            written.append(_outward(node, foot + out * (max(reach, 0.0) + gap),
                                    _degrees(out)))
        items.extend(written)
        if label is not None:
            items.append(self._r_name(label, written, angle, out, label_pad, theme))
        self._over.append(as_drawn(draw_place(items, kind=kind, origin=(0, 0),
                                              **style)))
        return self._touched()

    def _quiet_spoke(self) -> float:
        """Where the r axis goes when nobody said: a page angle with no tick.

        A fan puts it at the start of the view, where its numbers stand
        outside the data. A whole disc has no such edge, so it bisects the
        widest gap between the spokes that were actually drawn -- ties to the
        first gap round from zero, which is deterministic and is the quadrant
        a reader looks at last. That is a half step for any even ring: 45
        degrees at 4 ticks, 22.5 at 8, 15 at 12. A fixed 22.5 (matplotlib's
        answer, and this method's first one) is only the midpoint at 8 and 24,
        and at 12 it lands 7.5 degrees off the `30` label, which `CROWDING`
        duly reports. `_QUIET_SPOKE` remains the answer for a disc with no
        spokes at all, where there is nothing to bisect.
        """
        if not self.theta.full:
            return self.theta.page(self.theta.domain[0])
        if not self._spokes:
            return self.theta.zero + self.theta.sign * _QUIET_SPOKE
        # In the winding's own sense, so "first round from zero" means the
        # same thing clockwise and anticlockwise.
        seen = {(self.theta.sign * (a - self.theta.zero)) % 360.0: 0.0
                for a in self._spokes}
        # How much of each gap the labels themselves eat. A ring of `pi/6`,
        # `2pi/3`, `5pi/6` is not the uniform ring its spokes are: the widest
        # gap in *ink* is the one between the two narrowest labels, and that
        # is where an r axis with a plated number at the rim can stand.
        for angle, box in self._ring:
            turn = (self.theta.sign * (angle - self.theta.zero)) % 360.0
            if turn in seen:
                seen[turn] = max(seen[turn], _angular_half(box))
        turns = sorted(seen)
        gaps = [(hi - lo - seen[lo] - seen[hi % 360.0], hi - lo, lo)
                for lo, hi in zip(turns, turns[1:] + [turns[0] + 360.0])]
        _clear, width, start = max(gaps, key=lambda g: (round(g[0], 6), -g[2]))
        return self.theta.zero + self.theta.sign * (start + width / 2.0)

    def _label_side(self, side: str | None) -> float:
        """Which side of the r spoke the numbers stand on, as +1 or -1.

        Both defaults are "away from the crowd", and on a fan and a disc that
        is opposite sides of the spoke. A fan's numbers go *outside* it, since
        the interior is where the data is. A whole disc's spoke is already
        offset a half step round from zero (`_quiet_spoke`), so its numbers
        continue in that direction, away from the zero tick and its label --
        which is what the 0.2mm between `10` and `0°` was, before.
        """
        if side is None:
            if self.theta.full:
                return self.theta.sign
            return -1.0 if self.theta.sweep > 0 else 1.0
        if side in ("cw", "clockwise"):
            return 1.0
        if side in ("ccw", "anticlockwise", "counterclockwise"):
            return -1.0
        raise DiagramError(
            f"r_axis(side=) is 'cw' or 'ccw', not {side!r}")

    def _r_name(self, label, written, angle: float, out: Vec2, label_pad, theme):
        """The name of the radial quantity, at the outer end of its own spoke.

        Along the spoke, not across it: a radius runs from the pole outward and
        its name reads the same way, exactly as a rectangular y axis's name
        reads bottom-to-top. Flipped through half a turn where the spoke points
        into the left half of the page, so the words never arrive upside-down.

        *Outside* the rim, because the spoke itself runs through the data: the
        one place on a polar panel where an axis name is guaranteed to cover
        nothing is past the edge. And offset onto the same line as the numbers
        rather than onto the spoke, so it reads as the last item in their
        column and clears the theta tick label that sits on the spoke's own
        angle -- which is the collision that put `power` on top of `0` the
        first time this was drawn.
        """
        node = (label if isinstance(label, Diagram)
                else text_node(label, theme.font_size, AXIS_LABEL_KIND))
        pad = _LABEL_PAD_OF_TYPE * theme.font_size if label_pad is None \
            else mm(label_pad)
        turned = ((angle % 360.0) + 360.0) % 360.0
        flip = 90.0 < turned < 270.0
        # `rotated` takes anticlockwise degrees; page angles run clockwise.
        node = node.rotated(-(angle + 180.0) if flip else -angle)
        along = _polar(1.0, angle)
        far = max((at.dot(along) + _outward_reach(n.bbox, angle)
                   for at, n in written), default=self.radius)
        # And past the theta labels this spoke runs between. Their ring is
        # further out than the r numbers on any panel with a theta axis, and
        # the name is set along the spoke, so without this it reads straight
        # into the nearest angle -- the collision that put `spikes s-1` on top
        # of `315` the first three times this figure was drawn. Only the
        # neighbours count: a label a quarter turn away is centimetres of arc
        # from anything this name can reach.
        near = [box for a, box in self._ring
                if abs(((a - angle + 180.0) % 360.0) - 180.0) <= _R_NAME_ARC]
        across = out * max((at.dot(out) for at, _n in written), default=0.0)
        base = max(far, self.radius) + pad
        clear = _CLEAR_OF_TYPE * theme.font_size
        for step in range(_R_NAME_STEPS + 1):
            spot, node = _outward(node, _polar(base + step * _R_NAME_NUDGE,
                                               angle) + across, angle)
            if all(_boxes_clear(_shifted(node.bbox, spot), box, clear)
                   for box in near):
                break
        return spot, node

    def title(self, content: str | Diagram, *,
              pad: float | str | None = None) -> "PolarPanel":
        """A heading over the panel, clear of whatever is already in it."""
        node = (content if isinstance(content, Diagram)
                else text_node(content, active_theme().font_size, TITLE_KIND))
        gap = active_theme().gap("s") if pad is None else mm(pad)
        self._title = (node, gap)
        return self._touched()

    # -- data -------------------------------------------------------------

    def line(self, points: Iterable[Sequence], *, closed: bool | None = None,
             interpolate: bool = True, name: str | None = None,
             **style) -> "PolarPanel":
        """A path through `(theta, r)` points -- a tuning curve, a radiation
        pattern, a profile round a cell.

        **The segments between samples are arcs, not chords.** A tuning curve
        sampled every 30 degrees drawn with straight lines is a dodecagon, and
        a reader cannot tell the flat sides from a real plateau in the data.
        So each segment is densified along the straight line in *(theta, r)*
        -- the interpolation the sampling itself implies -- which for equal
        radii is exactly the arc through them. `interpolate=False` gets the
        chords back, which is what a polygon of measured vertices wants.

        `closed` defaults to closing the curve on a whole-disc panel and
        leaving it open on a fan. A sample set that does not go all the way
        round a full panel wants `closed=False`.
        """
        data = [(float(t), float(r)) for t, r in points]
        if len(data) < 2:
            raise DiagramError("a polar line needs at least two points")
        shut = self.theta.full if closed is None else closed
        style.setdefault("stroke", self._series_color(name, style.pop("color", None)))
        if style["stroke"] is None:
            del style["stroke"]
        self._note(name, "line", color=style.get("stroke"),
                   dash=style.get("stroke_dash"))
        style.setdefault("kind", MARK_LINE_KIND)
        return self.draw(polyline(self._track(data, shut, interpolate),
                                  closed=shut, **style),
                         clip=_clip_flag(style))

    def scatter(self, points: Iterable[Sequence], *, size=None, color=None,
                marker: str = "circle", name: str | None = None,
                **style) -> "PolarPanel":
        """Markers at `(theta, r)` points, with size and colour that may be
        data too. The rectangular `Panel.scatter` in polar coordinates: the
        same call, through this panel's own `point()`."""
        clip = _clip_flag(style)
        if color is None or isinstance(color, str):
            color = self._series_color(name, color)
        self._note(name, "marker", marker=marker,
                   color=color if isinstance(color, str) else None)
        return self.draw(_marks.scatter(self, points, size=size, color=color,
                                        marker=marker, **style), clip=clip)

    def marks(self, item: Diagram, points: Iterable[Sequence], *,
              name: str | None = None, **style) -> "PolarPanel":
        """A copy of `item` centred on every `(theta, r)` point."""
        clip = _clip_flag(style)
        placed = [(self.point(*p), item.copy()) for p in points]
        self._note(name, "marker", node=item.copy())
        return self.draw(draw_place(placed, **style), clip=clip)

    def band(self, theta: Sequence, low, high, *, closed: bool | None = None,
             interpolate: bool = True, name: str | None = None,
             color: str | None = None, **style) -> "PolarPanel":
        """The region between two radii at each angle: a spread round a curve.

        The polar form of `Panel.band`, and the shape a tuning curve with a
        standard error round it actually needs -- drawn as one ring so that it
        is one object to clip, to colour and to lint.
        """
        angles = [float(t) for t in theta]
        lo = _per_angle(low, len(angles), "low")
        hi = _per_angle(high, len(angles), "high")
        shut = self.theta.full if closed is None else closed
        outer = self._track(list(zip(angles, hi)), shut, interpolate)
        inner = self._track(list(zip(angles, lo)), shut, interpolate)
        tint = self._series_color(name, color)
        shade = mix(active_theme().ink if tint is None else tint,
                    active_theme().paper, _BAND_TINT)
        style.setdefault("fill", shade)
        style.setdefault("stroke", "none")
        self._note(name, "band", fill=style["fill"], color=tint)
        style.setdefault("kind", MARK_KIND)
        ring = outer + list(reversed(inner))
        return self.under(draw_path(ring, closed=True, filled=True, **style),
                          clip=_clip_flag(style))

    def rose(self, heights: Sequence[float], *, at: Sequence[float] | None = None,
             width: float = 1.0, base: float | None = None,
             name: str | None = None, color: str | None = None,
             **style) -> "PolarPanel":
        """Sector bars: the wind rose, and every circular histogram there is.

        `heights` are r values and `at` their bin centres in theta units; with
        no `at` the bars tile the whole view evenly, which is what
        `circular_histogram` hands back. `width` is the fraction of the bin a
        bar fills, so `width=1` is a continuous rose and `0.8` leaves paper
        between the petals.

        A sector, not a rectangle: the area of a polar bar grows as the square
        of its height, which is a known way to mislead, and drawing it as the
        wedge it actually occupies at least makes the picture honest about
        what it is doing. `base=` in r units starts the bars off the pole.

        A lone rose is a **tint of the ink**, not palette colour 0 -- which in
        the print theme is black, and sixteen black wedges meeting at a point
        is a wall with a hole in it. That is `plot.marks.series_colors`' rule
        for a single series of bars, and a rose is a bar chart bent round.
        """
        values = [float(v) for v in heights]
        if not values:
            raise DiagramError("rose() was given no bars")
        centres = _bin_centres(self.theta, len(values)) if at is None \
            else [float(a) for a in at]
        if len(centres) != len(values):
            raise DiagramError(
                f"at= has {len(centres)} angles for {len(values)} bars")
        if not 0 < width <= 1:
            raise DiagramError(f"rose(width=) is a fraction of a bin, got {width}")
        step = _bin_step(self.theta, centres)
        floor = self.r.domain[0] if base is None else float(base)
        tint = self._area_color(name, color)
        style.setdefault("fill", _marks.series_colors(tint, 1)[0])
        style.setdefault("stroke", "none")
        self._note(name, "area", fill=style["fill"], color=tint)
        inner = self.r.map(floor)
        wedges: list[Diagram] = []
        for centre, value in zip(centres, values):
            outer = self.r.map(value)
            if abs(outer - inner) < 1e-9:
                continue
            half = self.theta.sign * step * width / 2.0 * 360.0 / self.theta.turn
            mid = self.theta.page(centre)
            lo, hi = sorted((mid - half, mid + half))
            wedges.append(as_drawn(draw_sector(max(outer, inner), lo, hi,
                                               inner=min(outer, inner),
                                               kind=MARK_KIND, **style)))
        return self.draw(draw_place(wedges, origin=(0, 0)),
                         clip=_clip_flag(style))

    def mean_vector(self, angles: Sequence[float],
                    weights: Sequence[float] | None = None, *,
                    r: float | None = None, order: int = 1,
                    head: str = "triangle", label: str | Diagram | None = None,
                    name: str | None = None, color: str | None = None,
                    **style) -> "PolarPanel":
        """The circular mean of `angles`, drawn as an arrow from the pole.

        The length carries the *resultant* R -- how concentrated the sample is
        -- with R = 1 reaching the rim, which is the convention every
        head-direction and orientation figure uses and the reason the arrow is
        worth drawing at all: a mean direction with no R beside it says nothing
        about whether the cell was tuned.

        `weights` makes it the mean of a histogram; pass the rose's own bin
        centres and counts. `order=2` is the orientation statistic and draws
        the arrow through both lobes -- see `circular_mean`, which returns the
        two numbers for the caption. `r=` overrides the length in r units for
        the rare figure that scales it some other way.

        **A resultant too short to carry its own arrowhead is drawn as a dot at
        the pole**, not as a stub. An arrow shorter than the triangle on its
        end is not a shorter arrow, it is a triangle -- it reads as a large
        resultant pointing nowhere, which is the exact opposite of what the
        data says -- and `inklet.lint` reports the collapsed link besides. The dot
        is the honest picture of a sample with no mean direction, and it is
        also what `order=1` should show you for orientation data, as a prompt
        to pass `order=2`.
        """
        mean, resultant = circular_mean(angles, weights, unit=self.theta.unit,
                                        order=order)
        distance = (self.hole + (self.radius - self.hole)
                    * min(resultant / _RESULTANT_FULL, 1.0)) if r is None \
            else self.r.map(r)
        theme = active_theme()
        tint = self._series_color(name, color) or theme.accent
        style.setdefault("stroke", tint)
        self._note(name, "line", color=tint)
        angle = self.theta.page(mean)
        if distance - self.hole < _STUB_OF_HEAD * theme.arrow_size:
            dot = make_marker("circle", _DOT_OF_TYPE * theme.font_size,
                              fill=tint, stroke="none")
            return self.over(draw_place([(_polar(self.hole, angle), dot)],
                                        origin=(0, 0)), clip=False)
        node = _vector(ORIGIN if self.hole <= 0 else _polar(self.hole, angle),
                       _polar(distance, angle), head=head, size=theme.arrow_size,
                       label=label, **style)
        return self.over(node, clip=False)

    def text(self, theta, r, content: str | Diagram, *, anchor: str = "center",
             offset: Sequence[float] = (0.0, 0.0),
             size: float | str | None = None, markup: bool = True,
             **style) -> "PolarPanel":
        """Writing at one data point, `anchor` of it on that point."""
        from .notes import text_at

        return self.over(text_at(self, theta, r, content, anchor=anchor,
                                 offset=offset, size=size, markup=markup,
                                 **style), clip=False)

    # -- keys --------------------------------------------------------------

    def _note(self, name: str | None, form: str, **fields) -> "PolarPanel":
        """Remember that a series called `name` was drawn as `form`."""
        if name is not None:
            self._keys.append(SeriesKey(name=str(name),
                                        forms=frozenset((form,)), **fields))
        return self

    def _area_color(self, name: str | None, given: str | None) -> str | None:
        """The colour a named *area* is filled with, or None for the tint.

        Deliberately not `_series_color`: that hands an unclaimed name the next
        palette colour, which is right for a line and wrong for a wedge -- see
        `rose`. What it does keep is the agreement between a rose and a line of
        the same name, since a name already drawn in a colour keeps it.
        """
        if given is not None:
            return given
        if name is not None:
            for key in self._keys:
                if key.name == str(name) and key.color is not None:
                    return key.color
        return None

    def _series_color(self, name: str | None, given: str | None) -> str | None:
        """The colour a named series is drawn in; see `Panel._series_color`."""
        if given is not None or name is None:
            return given
        name = str(name)
        seen: list[str] = []
        for key in self._keys:
            if key.name == name and key.color is not None:
                return key.color
            if key.name not in seen:
                seen.append(key.name)
        index = seen.index(name) if name in seen else len(seen)
        return active_theme().color(index)

    @property
    def keys(self) -> tuple[SeriesKey, ...]:
        """The named series in this panel, one entry each, in drawing order."""
        return tuple(merge_keys(self._keys))

    def legend(self, *, corner: str | None = "ne", side: str | None = None,
               entries: Sequence[tuple[str, object]] | None = None,
               columns: int = 1, swatch: float | str | None = None,
               pad: float | str | None = None, plate: bool | None = None,
               title: str | None = None, markup: bool = True,
               **style) -> "PolarPanel":
        """A key built from the series this panel actually drew.

        `corner` puts it in a corner of the box round the disc -- which on a
        polar panel is *paper*, the quarter the data cannot reach, and the one
        place a key can sit inside the plot without covering anything.
        `side` puts it outside instead.
        """
        from .panel import _into_corner, _plated

        theme = active_theme()
        rows = list(entries) if entries is not None else self._legend_rows(swatch)
        if not rows:
            raise DiagramError(
                "legend() found no named series: pass name= to line(), "
                "scatter(), rose() or band(), or give legend(entries=[...])")
        node = make_legend(rows, columns=columns, swatch=swatch, title=title,
                           markup=markup, **style)
        gap = theme.gap("s") if pad is None else mm(pad)
        if side is not None:
            self._over.append(self._beside(node, side, gap))
            return self._touched()
        if plate is None:
            # A corner of a polar panel is empty paper, so the plate a
            # rectangular panel needs to knock its key out of the data is
            # usually just a box drawn round nothing.
            plate = False
        if plate:
            node = _plated(node, theme, theme.gap("xs"))
        self._over.append(_into_corner(node, self.area, corner or "ne", gap))
        return self._touched()

    def _beside(self, node: Diagram, side: str, gap: float) -> Diagram:
        """Put a key outside the panel, clear of the furniture already there.

        Measured against everything built so far rather than against the disc,
        so a key to the right of a panel whose right side is empty sits close
        in and one on the left clears the r axis and its name -- the same rule
        `Panel._beside` follows, over a box that happens to be round.
        """
        if side not in ("left", "right", "top", "bottom"):
            raise DiagramError(
                f"unknown side {side!r}; expected left, right, top or bottom")
        box = _union_box(self._under + self._content + self._over) or self.area
        here = node.bbox
        if side == "right":
            at = Vec2(box.x1 + gap + here.width / 2, self.area.center.y)
        elif side == "left":
            at = Vec2(box.x0 - gap - here.width / 2, self.area.center.y)
        elif side == "top":
            at = Vec2(self.area.center.x, box.y0 - gap - here.height / 2)
        else:
            at = Vec2(self.area.center.x, box.y1 + gap + here.height / 2)
        return node.translated(at.x - here.center.x, at.y - here.center.y)

    def _legend_rows(self, swatch: float | str | None) -> list[tuple[str, object]]:
        theme = active_theme()
        size = (SWATCH_OF_TYPE * theme.font_size_small if swatch is None
                else mm(swatch))
        return [(entry.name, swatch_for(entry, size)) for entry in self.keys]

    # -- output ------------------------------------------------------------

    def build(self) -> Diagram:
        """The panel as a diagram, with its `origin` anchor on the pole.

        The `plot_area` note and the `area-nw`/`area-se` anchors come too, in
        the frame the panel was drawn in, exactly as `Panel.build` leaves them
        -- so `inklet.letters`, `OFF_PANEL` and a hand-composed figure lining
        panels up all read a polar panel the way they read a rectangular one.
        The rectangle is the upright box round the disc or the fan, because
        that is what those readers are asking about: where the ink that *is*
        the data stops and the furniture begins.

        Cached, because building mints fresh node ids and rendering the same
        panel twice must not produce two different files.
        """
        if self._built is not None:
            return self._built
        children = list(self._under) + list(self._content) + list(self._over)
        if self._title is not None:
            children.append(self._titled(children))
        self._built = drawn_group(children, PANEL_KIND)
        declare_area(self._built, self.area)
        _declare_domain(self._built, self.r)
        return self._built

    def _titled(self, children: Sequence[Diagram]) -> Diagram:
        node, pad = self._title
        box = _union_box(children) or self.area
        text_box = node.bbox
        at = Vec2(self.area.center.x, box.y0 - pad - text_box.height / 2)
        centre = node.transform.apply(node.anchor_point("center"))
        return node.translated(at.x - centre.x, at.y - centre.y)

    def _region(self, *, kind: str, **style) -> Diagram:
        """The data region as one fillable shape: a disc, a fan or a ring."""
        a0, a1 = self._page_ends()
        if self.theta.full and self.hole <= 0:
            return draw_path(_ring_points(self.radius, 0.0, 360.0),
                             closed=True, filled=True, kind=kind, **style)
        return draw_sector(self.radius, a0, a1, inner=self.hole, kind=kind,
                           **style)

    def _track(self, data: Sequence[tuple[float, float]], closed: bool,
               interpolate: bool) -> list[Vec2]:
        """The vertices of a polar path through `(theta, r)` samples."""
        pairs = list(data) + ([data[0]] if closed and len(data) > 1 else [])
        if not interpolate:
            return [self.point(t, r) for t, r in pairs]
        out: list[Vec2] = [self.point(*pairs[0])]
        for (t0, r0), (t1, r1) in zip(pairs, pairs[1:]):
            steps = max(1, math.ceil(abs(self.theta.page(t1) - self.theta.page(t0))
                                     / _ARC_STEP - 1e-9))
            for i in range(1, steps + 1):
                f = i / steps
                out.append(self.point(t0 + (t1 - t0) * f, r0 + (r1 - r0) * f))
        return out[:-1] if closed else out


# -- construction ---------------------------------------------------------


def polar(radius: float | str = 30.0, *, r=None, theta=None,
          zero: float | str = "east", winding: str = "ccw",
          unit: str = "deg", hole: float | str = 0.0,
          clip: bool = False, nice: bool = False) -> PolarPanel:
    """A polar plot area of a given rim radius.

    `radius` sizes the data region the way `panel(width, height)` does: the
    finished node is wider, by whatever the labels need.

    `r` is the radial domain -- `(0, 12)`, or a `Scale` of your own -- and maps
    onto `hole..radius` millimetres. `theta` is the angular domain in `unit`,
    and defaults to a whole turn; give `(0, 180)` for a fan.

    `zero` is where theta = 0 points, in page degrees from east increasing
    clockwise, or one of the names in `ZERO_DIRECTIONS` -- `"up"`, `"east"`,
    `"north"`. `winding` is which way the data runs: `"ccw"` is the
    mathematical convention, `"cw"` the compass one.

        p = inklet.polar(26, r=(0, 12), zero="up", winding="cw")   # a compass
        p = inklet.polar(26, r=(0, 1), theta=(0, 180))             # a 180 fan

    `nice=True` rounds the r domain out to whole ticks, so the outermost ring
    lands on the rim rather than a millimetre inside it.
    """
    rim = mm(radius)
    pit = mm(hole)
    if rim <= 0:
        raise DiagramError(f"a polar panel needs a positive radius, got {radius!r}")
    if not 0 <= pit < rim:
        raise DiagramError(f"hole= must be inside the rim, got {hole!r} of {radius!r}")
    scale = _r_scale(r, pit, rim, nice)
    angles = _theta_of(theta, unit, zero, winding)
    return PolarPanel(radius=rim, r=scale, theta=angles, hole=pit, clip=clip)


def _r_scale(spec, hole: float, rim: float, nice: bool) -> Scale:
    """The radial scale: a domain onto `hole..rim` millimetres.

    A `Scale` handed in keeps its own kind -- a log radius is a real thing, and
    a seismologist's magnitude plot wants one -- but its *range* is replaced,
    because the range is millimetres and only this panel knows them.
    """
    if spec is None:
        spec = (0.0, 1.0)
    if isinstance(spec, Scale):
        return spec.with_range(hole, rim)
    low, high = spec
    scale: Linear = linear((float(low), float(high)), (hole, rim))
    return scale.nice().with_range(hole, rim) if nice else scale


def _theta_of(spec, unit: str, zero: float | str, winding: str) -> Theta:
    if isinstance(spec, Theta):
        return spec
    turn = THETA_UNITS.get(unit)
    if turn is None:
        raise DiagramError(
            f"unknown angle unit {unit!r}; expected one of "
            f"{', '.join(sorted(THETA_UNITS))}")
    domain = (0.0, turn) if spec is None else (float(spec[0]), float(spec[1]))
    if abs(domain[1] - domain[0]) < 1e-12:
        raise DiagramError(f"a polar view needs an angular span, got {spec!r}")
    return Theta(domain=domain, unit=unit, zero=_zero_degrees(zero),
                 winding=winding)


def _zero_degrees(zero: float | str) -> float:
    """Where theta = 0 points, in page degrees."""
    if isinstance(zero, (int, float)) and not isinstance(zero, bool):
        return float(zero)
    key = str(zero).strip().lower()
    if key not in ZERO_DIRECTIONS:
        raise DiagramError(
            f"zero= is a page angle in degrees or one of "
            f"{', '.join(sorted(set(ZERO_DIRECTIONS)))}, not {zero!r}")
    return ZERO_DIRECTIONS[key]


# -- geometry -------------------------------------------------------------


def _polar(distance: float, degrees: float) -> Vec2:
    """A point at `distance` from the pole, `degrees` round the page."""
    radians = math.radians(degrees)
    return Vec2(math.cos(radians) * distance, math.sin(radians) * distance)


def _degrees(direction: Vec2) -> float:
    """The page angle of a direction, in degrees."""
    return math.degrees(math.atan2(direction.y, direction.x))


def _perpendicular(degrees: float, side: float) -> Vec2:
    """The unit normal to a spoke, on the clockwise side for `side` = +1."""
    radians = math.radians(degrees)
    return Vec2(-math.sin(radians), math.cos(radians)) * side


def _arc_path(radius: float, start: float, end: float, **kwargs) -> Diagram:
    """A ring or an arc of one, centred on the pole, as real cubics."""
    if abs(end - start) >= 360.0 - 1e-9:
        return draw_path(curves=arc_cubics(ORIGIN, radius, 0.0, 360.0),
                         closed=True, **kwargs)
    return draw_path(curves=arc_cubics(ORIGIN, radius, start, end), **kwargs)


def _ring_points(radius: float, start: float, end: float,
                 step: float = 6.0) -> list[Vec2]:
    """A ring as flat points, for the shapes that must be polygons."""
    count = max(3, math.ceil(abs(end - start) / step))
    return [_polar(radius, start + (end - start) * i / count)
            for i in range(count)]


def _sector_bounds(radius: float, hole: float, a0: float, a1: float) -> Rect:
    """The upright box round a fan between two page angles."""
    points = _arc_extremes(radius, a0, a1)
    points += _arc_extremes(hole, a0, a1) if hole > 0 else [ORIGIN]
    return Rect.hull(points)


def _arc_extremes(radius: float, a0: float, a1: float) -> list[Vec2]:
    """The points that can touch the box round an arc: its ends, and each
    cardinal direction the sweep passes through."""
    low, high = (a0, a1) if a0 <= a1 else (a1, a0)
    points = [_polar(radius, low), _polar(radius, high)]
    first = math.ceil(low / 90.0 - 1e-9)
    last = math.floor(high / 90.0 + 1e-9)
    points += [_polar(radius, k * 90.0) for k in range(first, last + 1)]
    return points


def _knockout(node: Diagram, theme) -> Diagram:
    """A label on an opaque tile, so it stops what is behind it.

    `plot.panel._plated` under a tighter pad: a legend plate is a block of
    paper the reader sees as an object, and a tick label's is meant to be
    invisible -- just enough to keep a hairline out of the counter of an 8.
    """
    from ..layout import frame as make_frame

    return make_frame(node, pad=_PLATE_OF_TYPE * theme.font_size,
                      kind="tick-plate").styled(fill=theme.paper, stroke="none")


def _outward_reach(box: Rect, degrees: float) -> float:
    """How far a box reaches from its own centre, in one direction.

    The exact continuous form of a compass anchor: for a rectangle the
    boundary in direction u is at `min(w/|ux|, h/|uy|)`, which at 0 degrees is
    half the width, at 90 half the height, and at 30 the thing a sixteen-point
    compass is approximating.
    """
    radians = math.radians(degrees)
    ux, uy = math.cos(radians), math.sin(radians)
    half_w, half_h = box.width / 2.0, box.height / 2.0
    reaches = []
    if abs(ux) > 1e-12:
        reaches.append(half_w / abs(ux))
    if abs(uy) > 1e-12:
        reaches.append(half_h / abs(uy))
    return min(reaches) if reaches else 0.0


def _outward(node: Diagram, tip: Vec2, degrees: float) -> tuple[Vec2, Diagram]:
    """`node` pushed out from `tip` until its own boundary touches it."""
    return tip + _polar(_outward_reach(node.bbox, degrees), degrees), node


def _angular_half(box: Rect) -> float:
    """Half the angle a placed box subtends at the pole, in degrees.

    Its corners' bearings, spread about the box's own centre -- which is a
    fair description of the room a label takes on a ring and is cheap, where
    the exact swept angle of a rectangle seen from a point is neither.
    """
    centre = math.degrees(math.atan2(box.center.y, box.center.x))
    spread = 0.0
    for x in (box.x0, box.x1):
        for y in (box.y0, box.y1):
            off = math.degrees(math.atan2(y, x)) - centre
            spread = max(spread, abs(((off + 180.0) % 360.0) - 180.0))
    return spread


def _shifted(box: Rect, at: Vec2) -> Rect:
    """A node's own box, moved onto the point it was placed at."""
    return Rect(box.x0 + at.x, box.y0 + at.y, box.x1 + at.x, box.y1 + at.y)


def _boxes_clear(a: Rect, b: Rect, gap: float) -> bool:
    """Whether two boxes miss each other by `gap` -- the test `OVERLAP` and
    `CROWDING` between them make, in the frame the panel is drawn in."""
    return (a.x1 + gap <= b.x0 or b.x1 + gap <= a.x0
            or a.y1 + gap <= b.y0 or b.y1 + gap <= a.y0)


def _curved_label(text: str, radius: float, angle: float, theme) -> Diagram:
    """One tick label set along the rim rather than upright.

    `inklet.text_on_arc` is r7-text's, and the two conventions already agree:
    its `angle` is a page bearing in degrees, 0 due east and increasing
    clockwise, which is `Theta.page`'s output unchanged. `gap=0` because
    `radius` has already had the tick length and the pad added to it, so the
    ink starts exactly where an upright label's box would have -- that is what
    keeps `curved=True` from moving the ring in or out.

    Imported inside the call so that a polar figure with upright labels, which
    is the default, never pays for the shaping machinery.
    """
    from ..typeset.onpath import text_on_arc

    block = text_node(text, theme.font_size_small, TICK_LABEL_KIND,
                      markup=False)
    return text_on_arc(block, radius, angle, side="outside", gap=0.0,
                       kind=TICK_LABEL_KIND)


def _keep_round(placed: Sequence[tuple], clear: float,
                full: bool, thin: bool) -> list[tuple]:
    """Thin a ring of labels to a stride whose survivors do not touch.

    Straight out of `plot.axis._keep`, with two differences a circle forces.
    The gap between neighbours is the distance between the labels' *centres*
    less what each box reaches along the line joining them -- there is no axis
    to measure along. And on a whole disc the last label neighbours the first,
    so the stride has to divide the count: a stride of 2 over 9 ticks leaves
    the wrap-around pair adjacent, which is the one collision the reader is
    guaranteed to see, at the top of the plot.
    """
    if not thin or len(placed) < 2:
        return list(placed)
    total = len(placed)
    for stride in range(1, total + 1):
        if full and total % stride:
            continue
        kept = [placed[i] for i in range(0, total, stride)]
        if len(kept) < 2 or _clears_round(kept, clear, full):
            return kept
    return [placed[0]]


def _clears_round(kept: Sequence[tuple], clear: float, full: bool) -> bool:
    pairs = list(zip(kept, kept[1:])) + ([(kept[-1], kept[0])] if full else [])
    for (at_a, node_a, *_), (at_b, node_b, *_) in pairs:
        span = at_b - at_a
        if span.length <= 1e-9:
            return False
        towards = _degrees(span)
        need = (_outward_reach(node_a.bbox, towards)
                + _outward_reach(node_b.bbox, towards + 180.0) + clear)
        if span.length + 1e-9 < need:
            return False
    return True


def _bin_centres(theta: Theta, count: int) -> list[float]:
    """`count` bins tiling the view evenly, at their centres."""
    step = theta.span / count
    return [theta.domain[0] + step * (i + 0.5) for i in range(count)]


def _bin_step(theta: Theta, centres: Sequence[float]) -> float:
    """The width of one bin, in data units.

    From the spacing of the centres where there is more than one, and from the
    whole view where there is not -- a single bar filling the view is what
    `rose([1.0])` means.
    """
    if len(centres) < 2:
        return abs(theta.span)
    return abs(centres[1] - centres[0])


def _per_angle(value, count: int, name: str) -> list[float]:
    if isinstance(value, (int, float)):
        return [float(value)] * count
    given = [float(v) for v in value]
    if len(given) != count:
        raise DiagramError(f"{name}= has {len(given)} values for {count} angles")
    return given


def _formatted(texts: Sequence[str], format) -> tuple[str, ...]:
    """A `format=` string applied to labels the scale already wrote."""
    if format is None:
        return tuple(texts)
    if "{" in format:
        return tuple(format.format(t) for t in texts)
    return tuple(t + format for t in texts)


def _clip_flag(style: dict) -> bool | None:
    return style.pop("clip", None)


def _union_box(items: Iterable[Diagram]) -> Rect | None:
    box = None
    for item in items:
        other = item.envelope.bbox()
        if other is not None:
            box = other if box is None else box.union(other)
    return box


def _vector(start: Vec2, end: Vec2, *, head: str, size: float,
            label: str | Diagram | None, **style) -> Diagram:
    """A straight arrow from `start` to `end`, drawn as *data*.

    Deliberately not a `inklet.links` route, and the reason is a lint decision
    rather than a drawing one. A mean vector leaves the pole, so on any figure
    whose band or ring encloses the pole the shaft *must* cross it -- there is
    no placement that does not, and a routed link would earn a `LINK_CROSSES`
    on the geometry of the statistic itself. Both crossing rules already
    exempt ink whose position was computed rather than chosen (`mark-line` in
    `_COMPUTED_KINDS`, `arrowhead` in `_UNCHOSEN_STROKES`), and that is
    exactly what this is: the arrow points where the sample points, and an
    author who moves it is falsifying the figure.

    What the router would have given and this does not -- clipping to the
    endpoints' outlines, a chosen label side -- costs nothing for a segment
    whose two ends are already known in millimetres. The head is `links`'
    own `_head_prim`, so a mean vector wears the same arrowhead as every
    other arrow in the figure.
    """
    from ..links.link import HEAD_KIND, _head_prim

    tint = style.get("stroke") or active_theme().ink
    span = end - start
    direction = span.normalized()
    items: list[Diagram | tuple] = []
    stop = end
    if head not in ("none", None):
        prim, inset = _head_prim(head, end, direction, size)
        stop = end - direction * inset
        filled = getattr(prim, "filled", True)
        items.append(Diagram(prim=prim, kind=HEAD_KIND).styled(
            fill=tint if filled else "none",
            stroke="none" if filled else tint))
    items.insert(0, polyline((start, stop), kind=MARK_LINE_KIND, **style))
    if label is not None:
        if isinstance(label, str):
            label = text_node(label, active_theme().font_size_small,
                              TICK_LABEL_KIND)
        items.append(_outward(label, end, math.degrees(
            math.atan2(direction.y, direction.x))))
    return draw_place(items, origin=(0, 0), kind="mark-vector")


#: Padding round a knocked-out tick label, as a fraction of the type size.
#: A fifth of an em: enough paper that a gridline stops short of the glyphs,
#: little enough that the tile is not a visible box.
_PLATE_OF_TYPE = 0.2

#: How far round from the r axis a theta label still counts as its neighbour,
#: in page degrees. A quarter turn either side: beyond that the arc between
#: them is centimetres and no axis name reaches it.
_R_NAME_ARC = 90.0

#: How far the r axis's name is pushed out per attempt to clear the ring of
#: theta labels, and how many attempts. A quarter millimetre is under a
#: printer's dot and the search is over 10mm of travel -- but it is a search
#: rather than a formula because the name is set *along* its spoke, so what
#: has to clear is a rotated box against an upright one, and the answer is
#: not a distance anything can compute in closed form.
_R_NAME_NUDGE = 0.25
_R_NAME_STEPS = 40


#: Where the r axis stands on a whole disc, in page degrees from the zero
#: direction and in the winding's own sense. Half a 45 degree step: it clears
#: the tick at zero, and misses every spoke at 4, 8 and 24 ticks.
_QUIET_SPOKE = 22.5

#: How many arrowhead lengths a mean vector must reach before it is drawn as
#: an arrow at all. Below this the head is most of the shaft and the arrow
#: reads longer than it is.
_STUB_OF_HEAD = 1.6

#: The dot that stands in for an arrow too short to draw, as a fraction of the
#: type size. Half a data marker: it is a statement about the sample, not a
#: datum in it.
_DOT_OF_TYPE = 0.34

#: A polar band, as a blend towards paper. The same constant `plot.panel`
#: uses, kept here rather than imported so that the two can diverge if a ring
#: read through gridlines turns out to want a different weight.
_BAND_TINT = 0.78

#: A single unnamed rose against paper. Paler than a bar chart's 14% ink: a
#: rose is a dozen wedges meeting at a point, and at full strength the middle
#: of the plot goes solid.
_ROSE_TINT = 0.72
