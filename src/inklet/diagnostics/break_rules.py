"""`BREAK_DISTORTS` -- the rule that lets inklet ship a broken axis at all.

A broken axis is the only piece of furniture in the library that makes the
picture disagree with the numbers on purpose. Two bars whose counts differ by
a factor of thirty come out differing by a factor of eight, and nothing about
the drawing says so: the glyph on the spine announces that a stretch of the
scale is missing, not that the comparison the reader is about to make has been
rescaled. Every argument against broken axes -- and there are good ones -- is
an argument about that silence.

So `inklet.broken` exists, and this exists with it. The feature and the rule were
written in the same afternoon and neither is defensible without the other: a
library that offers a broken axis and cannot say when one is lying is a library
that has taken a side. **Grade: info**, because a broken axis is a legitimate
thing for an author to decide to do -- an inset would cost a second panel, a
log scale would misrepresent a difference of counts -- and the finding's job is
to make sure the decision was taken rather than fallen into. What it asks for
is a caption, not a redraw.

Two heuristics, both read off the picture:

* **A filled mark crosses the break.** A bar drawn straight through a gap is a
  rectangle whose length stands for nothing at all, which is the one case with
  no honest reading. `Panel.break_marks()` draws the journal's glyph across it;
  the finding stands either way, because marking a bar does not make its length
  mean something again.

* **Two marks on one baseline are out of proportion.** Each mark's height is
  read back through the axis into the quantity it stands for -- the note
  `plot.axis` leaves is exactly the table needed -- and the millimetres per
  unit of the tallest is held against the shortest. Marks that live inside one
  band give the same answer to the last bit and this says nothing; the moment
  a comparison spans the break the two disagree, and by how much is the number
  the caption owes the reader.

Both are silent on every figure without a break, structurally: the rule reads
a note that only `plot.scale.broken` causes to be written.
"""

from __future__ import annotations

import math
from collections.abc import Mapping

from ..core import Rect
from ..draw.coords import AREA_NOTE
from ..draw.shapes import MARK_KIND
from ..plot.breaks import BREAK_NOTE, AxisBreaks
from .rules import Diagnostic, Item, LintContext

__all__ = ["BREAK_RATIO_TOLERANCE", "rule_break_distorts"]

#: How far the page may misstate a ratio before it is worth a line in the
#: report. A fifth is about where two bars stop looking like the numbers they
#: stand for; below it the difference is the width of the ink.
BREAK_RATIO_TOLERANCE = 1.2

#: Marks whose two edges agree to this land on one baseline. A bar chart's
#: bars share a baseline exactly; this is float slack, and it is well under the
#: thinnest line the library will draw.
_SAME_BASE_MM = 0.01

#: Below this a mark has no length to read a ratio out of, and the ratio of two
#: numbers this small is noise about where an edge was rounded.
_MIN_LENGTH_MM = 0.05


def rule_break_distorts(ctx: LintContext) -> list[Diagnostic]:
    """Marks compared across a broken axis, and by how much the page lies."""
    out: list[Diagnostic] = []
    for axis_id, breaks in _declared_breaks(ctx):
        placed = ctx.placements.get(axis_id)
        if placed is None or not _upright(placed.world):
            continue                  # a turned axis has no interval to test
        panel_id = _panel_of(ctx, axis_id)
        if panel_id is None:
            continue                  # an axis drawn on its own owns no marks
        reading = _Reading(breaks, placed.world)
        marks = [item for item in ctx.items
                 if item.node.kind == MARK_KIND and item.is_shape and item.draws
                 and _panel_of(ctx, item.id) == panel_id]
        out.extend(_crossings(ctx, panel_id, reading, marks))
        out.extend(_out_of_proportion(ctx, panel_id, reading, marks))
    return out


# -- reading the picture back through the axis ----------------------------


class _Reading:
    """The broken axis as a figure-space ruler.

    The note is written in the axis's own frame; `world` is the one transform
    that puts that frame on the page, and the axis is upright, so one scale and
    one offset carry a millimetre position across. Everything below then works
    in figure space, which is the space `Item.bbox` is already in.
    """

    def __init__(self, breaks: AxisBreaks, world) -> None:
        self.breaks = breaks
        self.horizontal = breaks.horizontal
        self._scale = world.a if breaks.horizontal else world.d
        self._offset = world.e if breaks.horizontal else world.f

    def to_page(self, local: float) -> float:
        return self._scale * local + self._offset

    def to_local(self, page: float) -> float:
        return (page - self._offset) / self._scale

    def value_at(self, page: float) -> float:
        return self.breaks.value_at(self.to_local(page))

    def gaps(self) -> list[tuple[float, float]]:
        """The breaks as figure-space intervals, low end first."""
        out = []
        for a, b in self.breaks.gaps:
            first, second = self.to_page(a), self.to_page(b)
            out.append((min(first, second), max(first, second)))
        return out

    def span_of(self, box: Rect) -> tuple[float, float]:
        """A mark's two edges along the broken axis."""
        return (box.x0, box.x1) if self.horizontal else (box.y0, box.y1)

    @property
    def named(self) -> str:
        return "x" if self.horizontal else "y"


def _declared_breaks(ctx: LintContext) -> list[tuple[str, AxisBreaks]]:
    """Every distinct break declaration, against the node that wrote it.

    A note travels up onto every wrapper `carry_notes` builds, so one axis
    offers the same declaration two or three times over -- at two or three
    different frames, since the value is not a `Rect` and core rightly leaves
    it alone. The deepest node carrying a given value is the one whose frame it
    is in, which is the axis itself.
    """
    deepest: dict[AxisBreaks, tuple[int, str]] = {}
    for node_id, node in ctx.nodes.items():
        notes = getattr(node, "notes", None)
        value = notes.get(BREAK_NOTE) if isinstance(notes, Mapping) else None
        if not isinstance(value, AxisBreaks) or len(value.bands) < 2:
            continue
        depth = len(ctx.chain(node_id))
        if depth > deepest.get(value, (-1, ""))[0]:
            deepest[value] = (depth, node_id)
    return sorted(((node_id, breaks) for breaks, (_d, node_id) in deepest.items()),
                  key=lambda pair: pair[0])


def _panel_of(ctx: LintContext, node_id: str) -> str | None:
    """The nearest ancestor-or-self that declares a plot area.

    The same walk `OFF_PANEL` makes and for the same reason: a lettered panel
    and the panel inside it both carry the note, and the inner one is the one
    that owns the marks.
    """
    for step in reversed(ctx.chain(node_id)):
        notes = getattr(ctx.nodes.get(step), "notes", None)
        area = notes.get(AREA_NOTE) if isinstance(notes, Mapping) else None
        if isinstance(area, Rect):
            return step
    return None


def _upright(world) -> bool:
    """Whether this frame maps the axis onto a page axis, unrotated."""
    return abs(world.b) < 1e-9 and abs(world.c) < 1e-9 and world.a and world.d


# -- the two heuristics ---------------------------------------------------


def _crossings(ctx: LintContext, panel_id: str, reading: _Reading,
               marks: list[Item]) -> list[Diagnostic]:
    """Filled marks that run from one side of a break to the other."""
    gaps = reading.gaps()
    crossing = [item for item in marks
                if any(_spans(reading.span_of(item.bbox), gap) for gap in gaps)]
    if not crossing:
        return []
    where = crossing[0].bbox
    for item in crossing[1:]:
        where = where.union(item.bbox)
    count = len(crossing)
    return [Diagnostic(
        code="BREAK_DISTORTS",
        severity="info",
        message=(f"{count} filled mark{'' if count == 1 else 's'} cross"
                 f"{'es' if count == 1 else ''} the break in "
                 f"{ctx.label(panel_id)}'s {reading.named} axis"),
        targets=tuple(sorted(item.id for item in crossing)),
        where=where,
        hint=("a bar drawn through a break has a length that stands for "
              "nothing; Panel.break_marks() draws the glyph journals put "
              "there, and the caption still has to say what the two pieces "
              "are"),
    )]


def _spans(edges: tuple[float, float], gap: tuple[float, float]) -> bool:
    lo, hi = min(edges), max(edges)
    return lo < gap[0] - 1e-9 and hi > gap[1] + 1e-9


def _out_of_proportion(ctx: LintContext, panel_id: str, reading: _Reading,
                       marks: list[Item]) -> list[Diagnostic]:
    """Two marks on one baseline whose lengths no longer keep their ratio.

    Grouped by the edge they stand on rather than by the call that drew them,
    because the reader groups them that way: what makes two bars comparable is
    that they start from the same line, and the linter has the same evidence
    the reader does and no more.
    """
    worst: tuple[float, tuple[Item, float, float], tuple[Item, float, float]] | None
    worst = None
    for base, group in _baselines(reading, marks):
        rates = []
        for item, tip in group:
            length = abs(tip - base)
            value = abs(reading.value_at(tip) - reading.value_at(base))
            if length < _MIN_LENGTH_MM or value <= 0:
                continue
            rates.append((length / value, item, length, value))
        if len(rates) < 2:
            continue
        rates.sort(key=lambda r: r[0])
        low, high = rates[0], rates[-1]
        distortion = high[0] / low[0]
        if distortion <= BREAK_RATIO_TOLERANCE:
            continue
        if worst is None or distortion > worst[0]:
            worst = (distortion, (high[1], high[2], high[3]),
                     (low[1], low[2], low[3]))
    if worst is None:
        return []
    distortion, dense, sparse = worst
    # Named by the data rather than by which one the page favours: a reader
    # checking the finding looks for the *bigger number* first, and a sentence
    # that opens with the smaller one reads as being about the wrong bar.
    big, small = ((dense, sparse) if dense[2] >= sparse[2] else (sparse, dense))
    page = big[1] / small[1]
    data = big[2] / small[2]
    return [Diagnostic(
        code="BREAK_DISTORTS",
        severity="info",
        message=(f"{ctx.label(panel_id)}'s broken {reading.named} axis shows "
                 f"the marks reading {_number(big[2])} and "
                 f"{_number(small[2])} {page:.3g}x apart where the data says "
                 f"{data:.3g}x"),
        targets=tuple(sorted((big[0].id, small[0].id))),
        where=big[0].bbox.union(small[0].bbox),
        hint=(f"a {distortion:.1f}x distortion of that comparison; say so in "
              f"the caption, or drop the break for a log scale or an inset of "
              f"the small values"),
    )]


def _baselines(reading: _Reading,
               marks: list[Item]) -> list[tuple[float, list[tuple[Item, float]]]]:
    """Marks gathered by the edge they stand on, largest gathering first.

    Both edges of every mark are offered as a baseline, because which one it is
    depends on the sign of the data and on which way the axis runs, and the
    picture answers that better than an assumption would: the edge that several
    marks share is the one they are read from.
    """
    groups: dict[float, list[tuple[Item, float]]] = {}
    for item in marks:
        near, far = reading.span_of(item.bbox)
        for base, tip in ((near, far), (far, near)):
            groups.setdefault(_bucket(base), []).append((item, tip))
    ordered = [(base, group) for base, group in groups.items() if len(group) > 1]
    ordered.sort(key=lambda pair: (-len(pair[1]), pair[0]))
    return ordered


def _bucket(value: float) -> float:
    """A baseline coordinate, rounded so that two bars built by one call land
    in the same bucket whatever the last bit of their arithmetic said."""
    return round(value / _SAME_BASE_MM) * _SAME_BASE_MM


def _number(value: float) -> str:
    """A data value in a sentence: four figures, and no exponent for anything
    a reader would have typed."""
    if value and (abs(value) >= 1e5 or abs(value) < 1e-3):
        return f"{value:.3g}"
    text = f"{value:.4g}"
    return text if not math.isnan(value) else "?"
