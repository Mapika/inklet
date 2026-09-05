"""Scales: data in, millimetres out, and back again.

A scale is the only thing in `inklet.plot` that knows what a data value means. It
owns three jobs and no others: map a value to a position, invert that, and
propose the numbers a reader should be shown.

That third job is the one plotting libraries get wrong. Ticks at
`linspace(lo, hi, 5)` are correct and useless -- 0.7142857 is not a number
anyone reads off an axis. Ticks here are always 1, 2 or 5 times a power of ten,
chosen so that roughly `count` of them fall inside the domain. A reader can
then interpolate between two of them in their head, which is the entire point
of drawing an axis instead of a table.

Positions are millimetres in the frame of whatever will draw the scale, and a
scale is a value: `with_range` returns a new one rather than mutating. That is
what lets a `Panel` accept `linear((0, 10))` with no idea where it will sit and
fill the range in once it knows.
"""

from __future__ import annotations

import math
from builtins import range as range_indices
from dataclasses import dataclass, replace
from typing import ClassVar, Mapping, Sequence

from ..core import mm

__all__ = [
    "Band", "GroupedBand", "Broken", "Linear", "Log", "Scale", "ScaleError", "SymLog",
    "band", "grouped_band", "broken", "format_number", "linear", "log", "nice_bounds",
    "nice_step", "nice_ticks", "power_label", "si_labels", "symlog",
]

_EPS = 1e-12

Range = tuple[float, float]


class ScaleError(ValueError):
    """A domain, range or value a scale cannot make sense of."""


# -- nice numbers ---------------------------------------------------------


def nice_step(span: float, count: int = 5) -> float:
    """The 1/2/5-times-a-power-of-ten step nearest to `span / count`.

    The cut points are the geometric midpoints of the candidates, so the step
    chosen is the one whose tick count lands closest to what was asked for.
    """
    if not math.isfinite(span) or span <= 0:
        raise ScaleError(f"cannot pick a tick step for a span of {span!r}")
    if count < 1:
        raise ScaleError(f"tick count must be at least 1, got {count}")
    raw = span / count
    magnitude = 10.0 ** math.floor(math.log10(raw))
    fraction = raw / magnitude
    for cut, step in ((1.5, 1.0), (3.0, 2.0), (7.0, 5.0)):
        if fraction < cut:
            return step * magnitude
    return 10.0 * magnitude


def nice_ticks(lo: float, hi: float, count: int = 5) -> tuple[float, ...]:
    """Round numbers inside [lo, hi], about `count` of them.

    Ticks are multiples of the step, so a domain spanning zero always gets a
    tick exactly at zero -- the one value a reader checks for. The result is
    ascending whichever way round the domain was given, and a domain with no
    width has exactly one number in it.
    """
    if not (math.isfinite(lo) and math.isfinite(hi)):
        raise ScaleError(f"cannot tick a non-finite domain ({lo}, {hi})")
    if hi < lo:
        lo, hi = hi, lo
    if hi - lo <= abs(hi) * _EPS:
        return (lo,)
    step = nice_step(hi - lo, count)
    decimals = _decimals(step)
    first = math.ceil(lo / step - _EPS)
    last = math.floor(hi / step + _EPS)
    # Multiplying an integer by the step keeps every tick on the same lattice;
    # accumulating `previous + step` drifts, and the drift shows up as a label
    # reading 0.30000000000000004.
    return tuple(round(i * step, decimals) for i in range(int(first), int(last) + 1))


def nice_bounds(lo: float, hi: float, count: int = 5) -> tuple[float, float]:
    """Widen a domain to the next round number on each side, so that the ends
    of an axis are themselves labelled."""
    if hi < lo:
        lo, hi = hi, lo
    if hi - lo <= abs(hi) * _EPS:
        return (lo, hi)
    step = nice_step(hi - lo, count)
    decimals = _decimals(step)
    return (round(math.floor(lo / step + _EPS) * step, decimals),
            round(math.ceil(hi / step - _EPS) * step, decimals))


def format_number(value: float, step: float | None = None) -> str:
    """A tick label: as many decimals as the step needs and no more.

    Every label on one axis gets the same number of decimals, because a column
    reading 0, 0.5, 1 looks like three different quantities while 0.0, 0.5, 1.0
    looks like one.
    """
    if not math.isfinite(value):
        return str(value)
    decimals = 6 if step is None else _decimals(step)
    magnitude = abs(value)
    # What the axis can resolve, which is the step when there is one: a tick at
    # 1e-7 on an axis stepping by 0.1 is a rounding error in the data, and
    # writing it as 1e-7 gives it a significance the axis does not have.
    resolution = magnitude if step is None else abs(step)
    if magnitude >= 1e5 or resolution < 1e-4:
        # Past five figures, or below the fourth decimal, a plain decimal is a
        # row of zeros nobody can count.
        return "0" if magnitude == 0 else _exponent_form(value)
    text = f"{value:.{decimals}f}"
    if step is None:
        text = text.rstrip("0").rstrip(".")
    if float(text) == 0:
        text = text.lstrip("-")     # a tick at -0.0 is a tick at zero
    return text or "0"


def _exponent_form(value: float) -> str:
    """`2.5e-6`. Plain ASCII on purpose: a superscript minus is a glyph the
    resolved font may not have, and a tick label is not the place to find out."""
    mantissa, exponent = f"{value:.3e}".split("e")
    mantissa = mantissa.rstrip("0").rstrip(".")
    return f"{mantissa}e{int(exponent)}"


#: SI prefixes by power of ten. Only the multiples of three a reader knows on
#: sight: deca, hecto, deci and centi are legal SI and are not read as
#: magnitudes, so an axis in centimetres says "cm" in its own name instead.
SI_PREFIXES: dict[int, str] = {
    -24: "y", -21: "z", -18: "a", -15: "f", -12: "p", -9: "n", -6: "\u00b5",
    -3: "m", 0: "", 3: "k", 6: "M", 9: "G", 12: "T", 15: "P", 18: "E",
    21: "Z", 24: "Y",
}


def si_labels(ticks: Sequence[float],
              step: float | None = None) -> tuple[str, ...]:
    """Tick labels sharing one SI prefix, chosen for the whole set.

    `1.0 k`, `1.5 k`, `2.0 k` -- never `500`, `1 k`, `1.5 k`. The prefix is a
    property of the *axis*, not of each number on it: switching it partway up
    makes two ticks that differ by a factor of two look like they differ by a
    factor of two thousand, which is the one thing an axis exists to prevent.

    The prefix is picked from the largest tick, so the biggest number stays
    under four figures. Anything outside yocto..yotta is left to
    `format_number`, which will write it as an exponent.
    """
    values = [float(t) for t in ticks]
    if not values:
        return ()
    if step is None:
        step = _spacing(values)
    reach = max(abs(v) for v in values)
    if reach == 0 or not math.isfinite(reach):
        exponent = 0
    else:
        exponent = int(math.floor(math.log10(reach) / 3.0 + _EPS)) * 3
    if exponent not in SI_PREFIXES:
        return tuple(format_number(v, step) for v in values)
    factor = 10.0 ** -exponent
    prefix = SI_PREFIXES[exponent]
    scaled = [v * factor for v in values]
    # The step scales with the values, so the shared decimal count is still
    # decided by what the axis can resolve rather than by each number.
    scaled_step = None if step is None else abs(step) * factor
    tail = f" {prefix}" if prefix else ""
    # Zero has no magnitude to prefix, and "0.0 k" reads as a quantity of
    # kilos rather than as the origin. It loses the shared decimals with the
    # prefix: the origin of an axis is "0" in every notation there is.
    return tuple(format_number(v, scaled_step) + tail if v != 0 else "0"
                 for v in scaled)


def _declare_domain(node, scale: "Scale | None") -> None:
    """Record on `node` the numeric domain its colours were mapped through.

    `inklet.diagnostics` checks a key against the picture beside it by comparing
    colours, and colour is blind to the one mismatch that matters most: a bar
    labelled 0..100 over a matrix mapped 0..10 draws exactly the same pixels.
    The rule reads the node's `scale_domain` note, so this is the plot layer
    leaving it. It is a note and nothing else: `Diagram.note` (core M17) is a
    real field, so `replace`, `apply_theme` and `build` all carry it, where the
    plain attribute this used to stamp beside it lived only as long as the node
    did and had to be hand-copied across the rebuild in `figure.py`.

    Silent when there is no scale, or when its domain is not two numbers -- a
    `Band` has categories, not a range, and two band scales cannot disagree
    about one.

    Silent for a `Broken` scale too, and that one is worth spelling out. Its
    `domain` is a pair of numbers and would be accepted here, but it is the two
    outer ends and not what the scale covers: a `broken((0, 400),
    breaks=[(45, 330)])` never maps anything to 200. Declaring `(0, 400)`
    would let a key and a picture that genuinely disagree agree on paper, which
    is the one failure `KEY_MISMATCH` exists to prevent, so the note is left
    off and the rule stays quiet instead of being lied to.
    """
    if scale is None or node is None:
        return
    if getattr(scale, "segments", None) is not None:
        return
    domain = getattr(scale, "domain", None)
    if not isinstance(domain, tuple) or len(domain) != 2:
        return
    try:
        low, high = float(domain[0]), float(domain[1])
    except (TypeError, ValueError):
        return
    _annotate(node, "scale_domain", (low, high))


def _annotate(node, key: str, value) -> None:
    """Leave `value` on `node` under `key`, as a note and only as a note.

    `Diagram.note` (core M17) is a real field, so `replace`, `apply_theme` and
    `build` all carry it and a rule reads it off the built tree -- the only
    tree a rule ever sees. This used to stamp a plain instance attribute
    beside the note as well, for readers written before M17; nothing reads one
    any more, and the attribute was the reason `figure.py::apply_theme` had to
    lift `scale_domain` across the rebuild by name.

    Silent on a node that cannot take a note, which is how this file goes on
    working against a core that predates the slot.
    """
    note = getattr(node, "note", None)
    if callable(note):
        note(key, value)


def power_label(value: float, base: float = 10.0) -> str:
    """`10^{3}`, in inklet's own superscript markup.

    A log axis spanning six decades cannot label its ticks 100000 and 1000000
    -- the reader counts zeros and gets it wrong -- and `1e5` is a programming
    language, not a figure. Non-powers keep their mantissa: `2\u00d710^{5}`.
    """
    if value <= 0 or not math.isfinite(value):
        return format_number(value)
    exponent = math.floor(_log(value, base) + _EPS)
    mantissa = value / base ** exponent
    root = f"{base:g}^{{{exponent}}}"
    if abs(mantissa - 1.0) <= 1e-9:
        return root
    return f"{format_number(mantissa)}\u00d7{root}"


def _log(value: float, base: float) -> float:
    """log10 is exact on powers of ten where log(x, 10) is not: log(1000, 10)
    comes back as 2.9999999999999996, and a decade tick would land one short."""
    return math.log10(value) if base == 10.0 else math.log(value, base)


def _beyond_decimal(value: float) -> bool:
    """Whether `format_number` would give up on a plain decimal for this tick."""
    magnitude = abs(value)
    return magnitude >= 1e5 or (0 < magnitude < 1e-4)


#: Where a log axis stops writing its ticks as plain numbers and starts
#: writing them as powers. Four decades is the point at which the shortest and
#: longest labels on one axis differ by four digits, so the column of numbers
#: stops being a column; below it, `0.1 1 10 100` is more readable than
#: `10^{-1} 10^{0} 10^{1} 10^{2}` and is left alone.
_POWER_DECADES = 4.0

#: How many pieces a major step divides into, by its leading digit. Each keeps
#: the minor spacing itself a 1/2/5 number: 1 -> 0.2, 2 -> 0.5, 5 -> 1.
_SUBDIVISIONS = {1: 5, 2: 4, 5: 5}


def _piece_counts(majors: Sequence, count: int | None) -> tuple[int, ...]:
    """How finely to try dividing a step, coarsening until something fits."""
    if count is not None:
        return (count,)
    if len(majors) < 2:
        return ()
    step = abs(float(majors[1]) - float(majors[0]))
    if step <= 0:
        return ()
    leading = round(step / 10.0 ** math.floor(math.log10(step) + _EPS))
    fine = _SUBDIVISIONS.get(leading, 5)
    return (fine, 2) if fine > 2 else (fine,)


def _fits(values: Sequence[float], majors: Sequence, mapper,
          clear: float) -> bool:
    """Whether a set of minor ticks keeps `clear` millimetres from each other
    and from the majors they subdivide."""
    if not values:
        return False
    if clear <= 0:
        return True
    places = sorted([mapper(v) for v in values] + [mapper(m) for m in majors])
    return all(b - a >= clear - 1e-9 for a, b in zip(places, places[1:]))


def _linear_minors(domain: tuple[float, float], majors: Sequence,
                   count: int | None) -> tuple[float, ...]:
    if len(majors) < 2:
        return ()
    lo, hi = sorted(domain)
    step = abs(float(majors[1]) - float(majors[0]))
    if step <= 0:
        return ()
    pieces = count if count is not None else _SUBDIVISIONS.get(
        round(step / 10.0 ** math.floor(math.log10(step) + _EPS)), 5)
    if pieces < 2:
        return ()
    sub = step / pieces
    decimals = _decimals(sub)
    first = math.ceil(lo / sub - _EPS)
    last = math.floor(hi / sub + _EPS)
    known = {round(float(m) / sub) for m in majors}
    return tuple(round(i * sub, decimals)
                 for i in range(int(first), int(last) + 1) if i not in known)


def _decimals(step: float) -> int:
    """How many decimal places `step` needs to be written exactly."""
    for places in range(12):
        if abs(round(step, places) - step) <= abs(step) * 1e-12:
            return places
    return 12


# -- the interface --------------------------------------------------------


class Scale:
    """Data to millimetres. Subclasses fill in `map`, `invert` and `ticks`."""

    range: Range

    #: Whether these ticks are an enumeration rather than a rhythm. A
    #: continuous scale's ticks are a rhythm: every second one still reads as a
    #: rhythm, so an axis may thin them to fit. An enumerated scale's ticks are
    #: its categories, and thinning those leaves a row nobody can name.
    enumerated: ClassVar[bool] = False

    #: Whether this scale writes its tick labels in inklet's inline markup. False
    #: nearly everywhere, and that is the safe answer: a tick label is *data*
    #: -- a category called `Notch1**` or a condition written `//in vitro//` --
    #: and reading it as markup silently restyles or eats it. A log scale sets
    #: it, because `10^{3}` is markup the scale wrote itself.
    label_markup: ClassVar[bool] = False

    def map(self, value):
        """One data value to its millimetre position along this scale."""
        raise NotImplementedError

    def invert(self, position: float):
        """The reverse of `map`: millimetres back to a data value."""
        raise NotImplementedError

    def ticks(self, count: int = 5) -> tuple:
        """About `count` round values to label, chosen to suit the scale."""
        raise NotImplementedError

    def with_range(self, lo: float, hi: float) -> "Scale":
        """The same scale measuring into a different span of millimetres.

        The one call that lets a colorbar and a heatmap share a scale object:
        re-ranged to `0, 1` it maps a value to a ramp position, re-ranged to a
        panel's width it maps the same value to the page.
        """
        return replace(self, range=(mm(lo), mm(hi)))

    def tick_labels(self, ticks: Sequence) -> tuple[str, ...]:
        """Labels for a set of ticks, formatted against their own spacing."""
        step = _spacing(ticks)
        return tuple(format_number(t, step) for t in ticks)

    def minor_ticks(self, majors: Sequence, count: int | None = None,
                    clear: float = 0.0) -> tuple:
        """Unlabelled subdivisions between the major ticks.

        None by default, because most scales have no rhythm to subdivide: a
        band scale's categories have nothing between them, and inventing
        something there would draw ticks that stand for nothing. Continuous
        scales override it.

        `clear` is the least room, in millimetres, the caller will accept
        between neighbouring ticks. A scale that cannot subdivide that coarsely
        returns nothing rather than a comb: minor ticks packed tighter than the
        eye resolves are a grey stripe along the spine, which reads as a
        heavier axis and not as more information.
        """
        return ()

    @property
    def length(self) -> float:
        return abs(self.range[1] - self.range[0])

    def positions(self, values: Sequence) -> tuple[float, ...]:
        """`map` over a sequence of values."""
        return tuple(self.map(v) for v in values)


def _spacing(ticks: Sequence) -> float | None:
    gaps = [abs(b - a) for a, b in zip(ticks, ticks[1:]) if abs(b - a) > 0]
    return min(gaps) if gaps else None


def _interpolate(t: float, lo: float, hi: float) -> float:
    return lo + t * (hi - lo)


# -- linear ---------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Linear(Scale):
    domain: tuple[float, float] = (0.0, 1.0)
    range: Range = (0.0, 1.0)
    clamp: bool = False

    def map(self, value: float) -> float:
        d0, d1 = self.domain
        span = d1 - d0
        # A domain of one value has no inside; putting it in the middle is the
        # only answer that does not divide by zero or pick an end arbitrarily.
        t = 0.5 if span == 0 else (value - d0) / span
        if self.clamp:
            t = min(1.0, max(0.0, t))
        return _interpolate(t, *self.range)

    def invert(self, position: float) -> float:
        r0, r1 = self.range
        span = r1 - r0
        if span == 0:
            return self.domain[0]
        return _interpolate((position - r0) / span, *self.domain)

    def ticks(self, count: int = 5) -> tuple[float, ...]:
        return nice_ticks(self.domain[0], self.domain[1], count)

    def minor_ticks(self, majors: Sequence, count: int | None = None,
                    clear: float = 0.0) -> tuple:
        """Subdivisions of the major step, out to the ends of the domain.

        How many depends on the step, not on a constant: a step of 1 divides
        into five, a step of 2 into four, a step of 5 into five. Each keeps the
        minor spacing itself on the 1/2/5 lattice, so the small ticks read as
        tenths and halves rather than as an arbitrary comb. Too tight for
        `clear`, and the division halves before it gives up.
        """
        for pieces in _piece_counts(majors, count):
            out = _linear_minors(self.domain, majors, pieces)
            if _fits(out, majors, self.map, clear):
                return out
        return ()

    def nice(self, count: int = 5) -> "Linear":
        """The same scale over round bounds, so the axis ends on a labelled tick."""
        return replace(self, domain=nice_bounds(self.domain[0], self.domain[1], count))


def linear(domain: tuple[float, float] = (0.0, 1.0),
           range: Range = (0.0, 1.0), *, clamp: bool = False,
           nice: bool = False) -> Linear:
    """A proportional scale. `nice=True` rounds the domain out to whole ticks."""
    scale = Linear(_domain(domain), _range(range), clamp)
    return scale.nice() if nice else scale


# -- logarithmic ----------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Log(Scale):
    domain: tuple[float, float] = (1.0, 10.0)
    range: Range = (0.0, 1.0)
    base: float = 10.0
    clamp: bool = False

    #: `tick_labels` may return `10^{3}`, which is markup and has to be read
    #: as such. Nothing else this scale writes contains a markup delimiter.
    label_markup: ClassVar[bool] = True

    def __post_init__(self) -> None:
        if self.base <= 1.0:
            raise ScaleError(f"a log scale needs a base above 1, got {self.base}")
        for value in self.domain:
            if value <= 0:
                raise ScaleError(
                    f"a log domain must be positive, got {self.domain}; "
                    "use symlog() for data that reaches zero or below"
                )

    def map(self, value: float) -> float:
        if value <= 0:
            raise ScaleError(
                f"a log scale cannot place {value}; the logarithm is undefined "
                "at or below zero -- use symlog() for data that goes there"
            )
        d0, d1 = (_log(v, self.base) for v in self.domain)
        span = d1 - d0
        t = 0.5 if span == 0 else (_log(value, self.base) - d0) / span
        if self.clamp:
            t = min(1.0, max(0.0, t))
        return _interpolate(t, *self.range)

    def invert(self, position: float) -> float:
        r0, r1 = self.range
        span = r1 - r0
        if span == 0:
            return self.domain[0]
        d0, d1 = (_log(v, self.base) for v in self.domain)
        return self.base ** _interpolate((position - r0) / span, d0, d1)

    def ticks(self, count: int = 5) -> tuple[float, ...]:
        return log_ticks(self.domain[0], self.domain[1], count, self.base)

    def tick_labels(self, ticks: Sequence) -> tuple[str, ...]:
        # Across decades each tick is an exact power and is written to its own
        # precision -- a shared one would print 1 as 1.000 to match 0.001.
        # Within a decade the ticks are a lattice again and share a step.
        if len(ticks) > 1 and ticks[-1] > ticks[0] * self.base * (1 + 1e-9):
            # Two reasons to set the exponent form. Either a tick would be
            # written `1e5` or `2.5e-6`, where the superscript is both shorter
            # and what a journal prints; or the axis is long enough that the
            # reader is counting decades rather than reading values, which is
            # what `_POWER_DECADES` means. Over four decades a column of
            # 0.001 ... 10000 is six different widths of number and the eye
            # has to parse each one; `10^{-3} ... 10^{4}` is one shape
            # repeated, and the exponent is the quantity being read.
            if (any(_beyond_decimal(t) for t in ticks)
                    or self._decades(ticks) >= _POWER_DECADES):
                return tuple(power_label(t, self.base) for t in ticks)
            return tuple(format_number(t) for t in ticks)
        # Not `super()`: `slots=True` rebuilds the class, which leaves the
        # zero-argument form pointing at a class object that no longer exists.
        return Scale.tick_labels(self, ticks)

    def _decades(self, ticks: Sequence) -> float:
        """How many powers of the base the labelled ticks span."""
        low, high = min(ticks), max(ticks)
        if low <= 0 or high <= 0:
            return 0.0
        return _log(high, self.base) - _log(low, self.base)

    def minor_ticks(self, majors: Sequence, count: int | None = None,
                    clear: float = 0.0) -> tuple:
        """The mantissas between the decades: 2, 3, ... 9 times each power.

        A log axis is read by *where* a value sits inside its decade, and
        without the mantissa ticks there is nothing to read that against -- the
        gap from 1 to 10 is the same length as the gap from 10 to 100 and looks
        linear inside itself.

        A decade crowds from the top: 8 and 9 are a tenth of a decade apart
        while 1 and 2 are a third of one. So the choice is between whole
        mantissa *sets* -- 2 and 5, then 2/3/5, then all eight -- and the
        densest one that clears `clear` wins. Thinning the full set by a stride
        instead would drop a different mantissa in each decade, and a comb
        whose rhythm changes every decade is worse than a coarser one.
        """
        if not majors or self.base != 10.0:
            return ()
        chosen: tuple[float, ...] = ()
        for mantissas in ((2, 5), (2, 3, 5), (2, 3, 4, 5, 6, 7, 8, 9)):
            out = self._mantissa_ticks(mantissas, majors)
            if not _fits(out, majors, self.map, clear):
                break
            chosen = out
        return chosen

    def _mantissa_ticks(self, mantissas: Sequence[int],
                        majors: Sequence) -> tuple[float, ...]:
        lo, hi = sorted(self.domain)
        low = math.floor(_log(lo, self.base) + _EPS)
        high = math.ceil(_log(hi, self.base) - _EPS)
        known = {round(_log(m, self.base), 9) for m in majors}
        out = []
        for exponent in range(low, high + 1):
            for mantissa in mantissas:
                value = mantissa * self.base ** exponent
                if not lo * (1 - 1e-9) <= value <= hi * (1 + 1e-9):
                    continue
                if round(_log(value, self.base), 9) in known:
                    continue
                out.append(value)
        return tuple(out)


def log(domain: tuple[float, float] = (1.0, 10.0), range: Range = (0.0, 1.0), *,
        base: float = 10.0, clamp: bool = False) -> Log:
    """A logarithmic scale. The domain must not span or touch zero.

    `clamp=True` pins values outside the domain to its ends instead of letting
    them map past the plot area. See `symlog` for data that crosses zero.
    """
    return Log(_domain(domain), _range(range), float(base), clamp)


def log_ticks(lo: float, hi: float, count: int = 5,
              base: float = 10.0) -> tuple[float, ...]:
    """Decade ticks, subdivided when there is room and thinned when there is not.

    A log axis is read by its decades, so those come first and the mantissas
    fill in only while the label count stays near what was asked for. Under one
    decade there are no powers to show and the subdivision is all there is.
    """
    if lo > hi:
        lo, hi = hi, lo
    if lo <= 0:
        raise ScaleError(f"a log domain must be positive, got ({lo}, {hi})")
    low = math.floor(_log(lo, base) + _EPS)
    high = math.ceil(_log(hi, base) - _EPS)

    if base == 10.0:
        chosen = ()
        for mantissas in ((1,), (1, 3), (1, 2, 5), (1, 2, 3, 4, 5, 6, 7, 8, 9)):
            out = _decade_ticks(lo, hi, low, high, 1, mantissas, base)
            if chosen and len(out) > count * 1.2:
                break
            chosen = out
        if 2 <= len(chosen) <= count * 1.2:
            return chosen

    stride = max(1, math.ceil((high - low) / count))
    return _decade_ticks(lo, hi, low, high, stride, (1,), base)


def _decade_ticks(lo: float, hi: float, low: int, high: int, stride: int,
                  mantissas: Sequence[int], base: float) -> tuple[float, ...]:
    out: list[float] = []
    for exponent in range(low, high + 1, stride):
        for mantissa in mantissas:
            value = mantissa * base ** exponent
            if lo * (1 - 1e-9) <= value <= hi * (1 + 1e-9):
                out.append(value)
    return tuple(out)


# -- symmetric log --------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SymLog(Scale):
    """Logarithmic outside a linear window around zero.

    Data that crosses zero and still spans decades -- a log fold change, a
    residual, a current -- has no log scale and is unreadable on a linear one.
    `linthresh` sets the half-width of the linear window; outside it, each
    factor of `base` takes as much room as the whole window does.
    """

    domain: tuple[float, float] = (-1.0, 1.0)
    range: Range = (0.0, 1.0)
    linthresh: float = 1.0
    base: float = 10.0

    def __post_init__(self) -> None:
        if self.linthresh <= 0:
            raise ScaleError(f"linthresh must be positive, got {self.linthresh}")
        if self.base <= 1.0:
            raise ScaleError(f"a symlog scale needs a base above 1, got {self.base}")

    def _forward(self, value: float) -> float:
        magnitude = abs(value) / self.linthresh
        sign = -1.0 if value < 0 else 1.0
        if magnitude <= 1.0:
            return sign * magnitude
        return sign * (1.0 + math.log(magnitude, self.base))

    def _back(self, value: float) -> float:
        sign = -1.0 if value < 0 else 1.0
        magnitude = abs(value)
        if magnitude <= 1.0:
            return sign * magnitude * self.linthresh
        return sign * self.linthresh * self.base ** (magnitude - 1.0)

    def map(self, value: float) -> float:
        d0, d1 = (self._forward(v) for v in self.domain)
        span = d1 - d0
        t = 0.5 if span == 0 else (self._forward(value) - d0) / span
        return _interpolate(t, *self.range)

    def invert(self, position: float) -> float:
        r0, r1 = self.range
        span = r1 - r0
        if span == 0:
            return self.domain[0]
        d0, d1 = (self._forward(v) for v in self.domain)
        return self._back(_interpolate((position - r0) / span, d0, d1))

    def ticks(self, count: int = 5) -> tuple[float, ...]:
        lo, hi = sorted(self.domain)
        out: list[float] = []
        if lo <= 0 <= hi:
            out.append(0.0)
        reach = max(abs(lo), abs(hi))
        decades = 0 if reach <= self.linthresh else int(
            math.floor(_log(reach / self.linthresh, self.base) + _EPS))
        for exponent in range(decades + 1):
            value = self.linthresh * self.base ** exponent
            for signed in (-value, value):
                if lo - _EPS <= signed <= hi + _EPS:
                    out.append(signed)
        return tuple(sorted(out))


def symlog(domain: tuple[float, float] = (-1.0, 1.0), range: Range = (0.0, 1.0), *,
           linthresh: float = 1.0, base: float = 10.0) -> SymLog:
    """Logarithmic away from zero, linear across it.

    `linthresh` is where the change happens: inside it the scale is linear, so
    data that crosses zero -- a difference, a log ratio, a current -- can be
    drawn on one axis without the singularity a plain `log` has there.
    """
    return SymLog(_domain(domain), _range(range), float(linthresh), float(base))


# -- broken ---------------------------------------------------------------
#
# A broken axis is the one piece of plotting furniture that is a rhetorical
# device before it is a geometric one. It exists so that a small quantity and
# a large one can be read off the same picture, and it pays for that by making
# the picture's proportions untrue: two bars whose heights differ by a factor
# of forty come out differing by a factor of two. That is why `inklet` ships it
# with `BREAK_DISTORTS` (`inklet.diagnostics.break_rules`), and why nothing here
# is ever inferred -- the segments are written down by the author, in the
# figure, where a reader of the source can see the decision.

#: The gap between two bands, as a fraction of the theme's body size. About
#: 1.5mm at the default 7pt, which is two stroke widths clear of the break
#: glyph on either side -- enough to read as an interruption at 89mm wide,
#: small enough that it is not mistaken for empty data.
_BREAK_GAP_OF_TYPE = 0.6

#: How many times `ticks` may refine its step looking for one that gives every
#: segment a number of its own. A short segment beside a long one is the whole
#: reason to break an axis, so the first step the total span suggests often
#: misses the short one entirely; past a few refinements the long segment is a
#: comb and the answer is a different set of segments, not a finer step.
_BREAK_TICK_REFINEMENTS = 4


@dataclass(frozen=True, slots=True)
class Broken(Scale):
    """Two or more pieces of one domain, laid end to end with a gap between.

    Each segment is linear in itself and gets a band of the range in
    proportion to how much data it covers, so **the millimetres per unit are
    the same in every band** and a length read inside one band means what it
    means inside another. Pass `weights` to override that -- and know that a
    band given more room than its span deserves is a second distortion on top
    of the break itself.

    A value inside a break has nowhere to go: there is no room on the page for
    it, which is what the author asked for. `map` puts it on the nearer band
    edge rather than raising, so a line or an area that crosses the break still
    draws; the price is that this is the one scale where `invert(map(v))` is
    not `v`, and it is exactly the values the axis refuses to show.

    Outside the domain the nearest band's rate carries on, like `Linear` and
    for the same reason: data drawn past the end of an axis is a visible fault
    and a silent clamp is not.
    """

    segments: tuple[tuple[float, float], ...] = ((0.0, 1.0),)
    range: Range = (0.0, 1.0)
    #: Millimetres of blank page between two neighbouring bands.
    gap: float = 1.5
    #: Share of the drawable length per segment; None gives each its own span.
    weights: tuple[float, ...] | None = None

    def __post_init__(self) -> None:
        if not self.segments:
            raise ScaleError("a broken scale needs at least one segment")
        previous = None
        for lo, hi in self.segments:
            if not (math.isfinite(lo) and math.isfinite(hi)):
                raise ScaleError(f"a segment must be finite, got ({lo}, {hi})")
            if hi <= lo:
                raise ScaleError(
                    f"a segment runs low to high and must have width, got ({lo}, {hi})"
                )
            if previous is not None and lo <= previous:
                raise ScaleError(
                    f"segments must ascend and not touch; {previous} is not "
                    f"below {lo}"
                )
            previous = hi
        if self.gap < 0:
            raise ScaleError(f"a break gap cannot be negative, got {self.gap}")
        if self.weights is not None:
            if len(self.weights) != len(self.segments):
                raise ScaleError(
                    f"got {len(self.weights)} weights for "
                    f"{len(self.segments)} segments"
                )
            if any(w <= 0 for w in self.weights):
                raise ScaleError(f"every weight must be positive, got {self.weights}")

    # -- what the pieces are ----------------------------------------------

    @property
    def domain(self) -> tuple[float, float]:
        """The two outer ends. **Not** a domain this scale covers: the breaks
        are inside it, and `segments` is the honest answer."""
        return (self.segments[0][0], self.segments[-1][1])

    @property
    def breaks(self) -> tuple[tuple[float, float], ...]:
        """The pieces of the domain that are not drawn."""
        return tuple((a[1], b[0]) for a, b in zip(self.segments, self.segments[1:]))

    def bands(self) -> tuple[tuple[float, float], ...]:
        """Each segment's own stretch of the range, in millimetres.

        In the range's own direction, so a y scale -- whose range runs from the
        bottom of the panel *up*, and therefore backwards -- gets bands that
        run backwards too and need no special case anywhere else.
        """
        start, end = self.range
        direction = 1.0 if end >= start else -1.0
        room = abs(end - start) - self.gap * (len(self.segments) - 1)
        if room <= 0:
            raise ScaleError(
                f"{len(self.segments)} bands and {self.gap}mm gaps do not fit "
                f"in {abs(end - start):.3g}mm of range"
            )
        shares = (tuple(hi - lo for lo, hi in self.segments)
                  if self.weights is None else self.weights)
        total = sum(shares)
        out: list[tuple[float, float]] = []
        at = start
        for share in shares:
            length = room * share / total
            out.append((at, at + direction * length))
            at += direction * (length + self.gap)
        # The last band ends on the range, exactly: accumulating a length and a
        # gap per segment drifts by a bit or two, and a scale whose top tick
        # sits 3e-15mm inside the panel is a diff nobody can explain.
        out[-1] = (out[-1][0], end)
        return tuple(out)

    def gap_bands(self) -> tuple[tuple[float, float], ...]:
        """The blank stretches between bands, in millimetres.

        This is what an axis reads to know where to interrupt its spine and
        draw the break glyph, and what `inklet.lint` reads to know which marks
        cross a break. Named on the scale rather than discovered by the axis so
        that a caller's own broken scale gets the same treatment.
        """
        bands = self.bands()
        return tuple((a[1], b[0]) for a, b in zip(bands, bands[1:]))

    # -- the mapping -------------------------------------------------------

    def map(self, value: float) -> float:
        bands = self.bands()
        for index, (lo, hi) in enumerate(self.segments):
            if value < lo:
                if index == 0:
                    return _band_place(value, lo, hi, bands[0])   # below the axis
                # Inside a break. The nearer edge, because the value has no
                # room of its own and the two edges are the only places on the
                # page that stand for anything near it.
                previous = self.segments[index - 1]
                if value - previous[1] <= lo - value:
                    return bands[index - 1][1]
                return bands[index][0]
            if value <= hi:
                return _band_place(value, lo, hi, bands[index])
        return _band_place(value, *self.segments[-1], bands[-1])

    def invert(self, position: float) -> float:
        bands = self.bands()
        forward = bands[0][0] <= bands[-1][1]
        for index, (start, end) in enumerate(bands):
            lo, hi = self.segments[index]
            before = position < start if forward else position > start
            if before:
                if index == 0:
                    return _band_value(position, lo, hi, (start, end))
                return self.segments[index - 1][1] if _nearer_back(
                    position, bands[index - 1][1], start) else lo
            inside = position <= end if forward else position >= end
            if inside:
                return _band_value(position, lo, hi, (start, end))
        return _band_value(position, *self.segments[-1], bands[-1])

    # -- what a reader is shown --------------------------------------------

    def ticks(self, count: int = 5) -> tuple[float, ...]:
        """Round numbers on one lattice, none of them inside a break.

        One step for the whole axis, chosen from the span the axis actually
        draws -- the sum of the segments, not the distance between its ends,
        which is the number the break exists to throw away. The step then
        refines until every segment has a tick of its own, because a band with
        no number against it is a band the reader cannot read.
        """
        span = sum(hi - lo for lo, hi in self.segments)
        step = nice_step(span, count)
        for _ in range(_BREAK_TICK_REFINEMENTS):
            out = self._lattice(step)
            if all(any(lo - _EPS <= t <= hi + _EPS for t in out)
                   for lo, hi in self.segments):
                return out
            step = _finer_step(step)
        return self._lattice(step)

    def _lattice(self, step: float) -> tuple[float, ...]:
        decimals = _decimals(step)
        out: list[float] = []
        for lo, hi in self.segments:
            first = math.ceil(lo / step - _EPS)
            last = math.floor(hi / step + _EPS)
            out.extend(round(i * step, decimals)
                       for i in range(int(first), int(last) + 1))
        return tuple(out)

    def minor_ticks(self, majors: Sequence, count: int | None = None,
                    clear: float = 0.0) -> tuple:
        """Subdivisions inside each band, and never across a break.

        Subdividing the axis as a whole would put minor ticks in the gap, which
        is the one place on a broken axis that must stay empty: a tick there
        says the scale runs through, and the entire claim of the break is that
        it does not.
        """
        for pieces in _piece_counts(majors, count):
            out: list[float] = []
            for lo, hi in self.segments:
                inside = [m for m in majors if lo - _EPS <= float(m) <= hi + _EPS]
                if len(inside) >= 2:
                    out.extend(_linear_minors((lo, hi), inside, pieces))
            if _fits(tuple(out), majors, self.map, clear):
                return tuple(out)
        return ()


def _band_place(value: float, lo: float, hi: float,
                band: tuple[float, float]) -> float:
    start, end = band
    return _interpolate((value - lo) / (hi - lo), start, end)


def _band_value(position: float, lo: float, hi: float,
                band: tuple[float, float]) -> float:
    start, end = band
    if end == start:
        return lo
    return _interpolate((position - start) / (end - start), lo, hi)


def _nearer_back(position: float, behind: float, ahead: float) -> bool:
    """Whether a position inside a gap is closer to the band that ended."""
    return abs(position - behind) <= abs(ahead - position)


def _finer_step(step: float) -> float:
    """The next step down the 1/2/5 ladder: 5 -> 2, 2 -> 1, 1 -> 0.5."""
    exponent = math.floor(math.log10(step) + _EPS)
    magnitude = 10.0 ** exponent
    leading = round(step / magnitude)
    return {5: 2.0 * magnitude, 2: 1.0 * magnitude}.get(
        leading, 5.0 * magnitude / 10.0)


def broken(domain: tuple[float, float] = (0.0, 1.0), range: Range = (0.0, 1.0),
           *, breaks: Sequence[Sequence[float]] = (),
           gap: float | None = None,
           weights: Sequence[float] | None = None) -> Broken:
    """A linear scale with `breaks` cut out of it.

        y = inklet.broken((0, 400), breaks=[(45, 330)])

    `breaks` is the pieces of the domain **not** to draw, and it is required
    for the scale to be broken at all: there is no threshold, no ratio and no
    gap-finder anywhere in inklet that will decide this for you. A broken axis is
    an argument about the data, and an argument nobody wrote down is one nobody
    can check.

    What is left over becomes the segments, each with its own band of the range
    and the same millimetres per unit as the others. `gap` is the blank between
    two bands and defaults to a little over half the body size; `weights` gives
    the bands unequal shares of the page.

    Pair it with `Panel.break_marks()`, which draws the same glyph across every
    bar that crosses the break, and read what `inklet.lint` says about the result:
    `BREAK_DISTORTS` is the rule that decides whether the figure got away with
    it.
    """
    lo, hi = _domain(domain)
    if hi < lo:
        lo, hi = hi, lo
    segments = _cut(lo, hi, breaks)
    if gap is None:
        # Late, and through `draw`, exactly as `inklet.plot.axis` reads it: the
        # current theme is a global on the package and importing it up here
        # would close a loop through `inklet/__init__`.
        from ..draw.coords import active_theme

        gap = _BREAK_GAP_OF_TYPE * active_theme().font_size
    return Broken(segments, _range(range), mm(gap),
                  None if weights is None else tuple(float(w) for w in weights))


def _cut(lo: float, hi: float,
         breaks: Sequence[Sequence[float]]) -> tuple[tuple[float, float], ...]:
    """`(lo, hi)` with each break removed, left to right."""
    cuts = []
    for piece in breaks:
        try:
            a, b = (float(v) for v in piece)
        except (TypeError, ValueError):
            raise ScaleError(
                f"a break is a (from, to) pair, not {piece!r}") from None
        cuts.append((min(a, b), max(a, b)))
    cuts.sort()
    segments: list[tuple[float, float]] = []
    at = lo
    for a, b in cuts:
        if not lo < a < b < hi:
            raise ScaleError(
                f"break ({a}, {b}) is not strictly inside the domain ({lo}, {hi})"
            )
        if a <= at:
            raise ScaleError(f"breaks overlap: ({a}, {b}) starts inside ({at},)")
        segments.append((at, a))
        at = b
    segments.append((at, hi))
    return tuple(segments)


# -- categorical ----------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Band(Scale):
    """Evenly spaced slots, one per category.

    `map` gives the *centre* of a band, because that is where a mark goes;
    `edges` gives the two sides, for anything that fills the slot. `padding` is
    the fraction of each step left blank between neighbours, and `outer` the
    fraction left at the two ends.
    """

    categories: tuple = ()
    range: Range = (0.0, 1.0)
    padding: float = 0.1
    outer: float | None = None

    enumerated: ClassVar[bool] = True

    def __post_init__(self) -> None:
        if not self.categories:
            raise ScaleError("a band scale needs at least one category")
        if len(dict.fromkeys(self.categories)) != len(self.categories):
            raise ScaleError(f"band categories must be distinct: {self.categories}")
        if not 0.0 <= self.padding < 1.0:
            raise ScaleError(f"padding must be within 0..1, got {self.padding}")

    @property
    def domain(self) -> tuple:
        return self.categories

    @property
    def step(self) -> float:
        outer = self.padding if self.outer is None else self.outer
        divisor = max(1.0, len(self.categories) - self.padding + 2 * outer)
        return (self.range[1] - self.range[0]) / divisor

    @property
    def bandwidth(self) -> float:
        return abs(self.step) * (1.0 - self.padding)

    def index(self, category) -> int:
        try:
            return self.categories.index(category)
        except ValueError:
            known = ", ".join(str(c) for c in self.categories)
            raise ScaleError(f"unknown category {category!r}; expected one of {known}")

    def map(self, value) -> float:
        outer = self.padding if self.outer is None else self.outer
        step = self.step
        start = self.range[0] + step * (outer + (1.0 - self.padding) / 2)
        return start + step * self.index(value)

    def edges(self, value) -> tuple[float, float]:
        centre = self.map(value)
        half = self.bandwidth / 2
        return (centre - half, centre + half)

    def invert(self, position: float):
        """The category whose band is nearest -- there is no in-between here."""
        return min(self.categories, key=lambda c: abs(self.map(c) - position))

    def ticks(self, count: int = 5) -> tuple:
        """Every category. A band axis that skipped labels would be lying about
        which bar is which, so `count` is deliberately ignored."""
        return tuple(self.categories)

    def tick_labels(self, ticks: Sequence) -> tuple[str, ...]:
        return tuple(str(t) for t in ticks)


def band(categories: Sequence, range: Range = (0.0, 1.0), *,
         padding: float = 0.1, outer: float | None = None) -> Band:
    """A categorical scale: one evenly spaced slot per category.

    **The first category maps to the low end of the range.** On a panel's y
    axis, which runs from the bottom of the plot area upward, that puts
    `categories[0]` at the *bottom*; list them in the order you want to read
    them upward, or reverse the list to read downward. Getting this backwards
    is invisible to a linter and obvious to a reader, so it is worth checking
    once with `panel.point(x, category)`.

    `padding` is the fraction of each slot left empty, which is the gap between
    neighbouring bars. `outer` is the padding at the two ends of the range, and
    defaults to `padding`.
    """
    return Band(tuple(categories), _range(range), padding, outer)


@dataclass(frozen=True, slots=True)
class GroupedBand(Band):
    """Category slots with an additional gap between supplied groups."""

    group_breaks: tuple[int, ...] = ()
    gap: float = 1.0

    def __post_init__(self):
        Band.__post_init__(self)
        if not math.isfinite(self.gap) or self.gap < 0:
            raise ScaleError("group gap must be finite and non-negative")
        if tuple(sorted(set(self.group_breaks))) != self.group_breaks or any(
                b <= 0 or b >= len(self.categories) for b in self.group_breaks):
            raise ScaleError("group boundaries must be distinct interior category indices")

    @property
    def step(self) -> float:
        outer = self.padding if self.outer is None else self.outer
        divisor = max(1.0, len(self.categories) + self.gap*len(self.group_breaks)
                      - self.padding + 2*outer)
        return (self.range[1]-self.range[0])/divisor

    def map(self, value) -> float:
        index = self.index(value)
        outer = self.padding if self.outer is None else self.outer
        slot = index + self.gap*sum(index >= b for b in self.group_breaks)
        return self.range[0] + self.step*(outer+(1-self.padding)/2+slot)


def grouped_band(groups: Sequence[Sequence] | Mapping, range: Range = (0., 1.), *,
                 gap: float = 1.0, padding: float = .1,
                 outer: float | None = None, reverse: bool = False) -> GroupedBand:
    """A band scale with gaps between groups, measured in category slots.

    Supply groups as sequences or an ordered mapping of group names to
    sequences. `reverse=True` reads top-to-bottom on a panel's y axis.
    Categories remain ordinary values for bars, ticks and annotations.
    """
    rows = [tuple(row) for row in (groups.values() if isinstance(groups, Mapping) else groups)]
    if not rows or any(not row for row in rows):
        raise ScaleError("grouped_band needs non-empty groups")
    if reverse:
        rows = [tuple(reversed(row)) for row in reversed(rows)]
    categories = tuple(c for row in rows for c in row)
    group_breaks = tuple(sum(map(len,rows[:i])) for i in range_indices(1,len(rows)))
    return GroupedBand(categories, _range(range), padding, outer, group_breaks, float(gap))


# -- shared validation ----------------------------------------------------


def _domain(domain) -> tuple[float, float]:
    try:
        lo, hi = domain
    except (TypeError, ValueError):
        raise ScaleError(f"a domain is a (low, high) pair, not {domain!r}") from None
    lo, hi = float(lo), float(hi)
    if not (math.isfinite(lo) and math.isfinite(hi)):
        raise ScaleError(f"a domain must be finite, got ({lo}, {hi})")
    return (lo, hi)


def _range(value) -> Range:
    try:
        lo, hi = value
    except (TypeError, ValueError):
        raise ScaleError(f"a range is a (start, end) pair, not {value!r}") from None
    return (mm(lo), mm(hi))
