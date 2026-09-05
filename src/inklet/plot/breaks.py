"""The break glyph, and the note that says a break happened.

A broken axis is two claims drawn at once: *this stretch of the scale is not
here*, and *what you are looking at either side of it is still the same
quantity*. A gap on its own makes the first claim and not the second -- a reader
who meets 1.5mm of blank spine has no way to tell a break from a hairline that
did not print -- so the gap gets a mark, and journals put the same mark on any
*bar* that crosses it, because a bar drawn straight through a break is a
rectangle whose length stands for nothing.

Two shapes, one angle. On the spine it is the classic pair of parallel slashes
straddling the interruption. On a bar it is the same pair with the page showing
through between them, which is what makes the bar read as cut rather than as
striped: a bar with two lines drawn on it is a bar with two lines drawn on it.

Everything here is measured from the type size, like the rest of the axis (see
`plot.axis`), so a figure retuned for a slide keeps the proportions it was
designed with. Nothing is inferred: `plot.scale.broken` is the only thing that
creates a break, and it takes the breaks as an argument.

## What else meets a break, and what it does

A break is a hole in the middle of a scale, so everything that reads a value
through that scale meets it. Each of these was tried and decided rather than
left to whatever fell out:

* **Ticks and gridlines.** Never inside the gap. `Broken.ticks` puts one
  lattice across every segment and refines it until each band has a number of
  its own; `outside_breaks` then drops anything a hand-written `ticks=` would
  have put in the hole, and `axis.tick_values` runs it too, so `Panel.grid`
  cannot rule across a break the axis refused to tick.

* **Bars, areas, violins, histograms.** Cut, if `Panel.break_marks()` is
  called, and reported by `BREAK_DISTORTS` whether it is or not.

* **Lines and steps.** Drawn straight across the gap and *not* marked. A line
  says "between these two points the quantity went from here to there", and
  across a break the slope of that segment never meant anything to begin with;
  a glyph on it would suggest the rest of the line is to scale in a way the
  break already denies. The gap in the spine is the notice.

* **Errorbars.** A whisker crosses the gap the way a line does and is not
  marked either: at a quarter of a millimetre wide there is nothing to cut, and
  a zigzag across a stroke reads as a second datum. Where the whisker runs up
  a bar that *is* cut, the bar's break paints over it, which is right -- that
  strip of the page is not part of the scale. `BREAK_DISTORTS` does not see
  whiskers; a mean whose interval spans a break is a figure whose author should
  be reaching for a log axis.

* **Brackets.** `Panel.bracket` with no `y` clears the drawn content in
  millimetres and so cannot land in a gap by accident. Given an explicit `y`
  inside a break it lands on the nearer band edge, beside the glyph, which
  looks like a mistake and is one -- pass a `y` the axis actually draws.

* **`scale_domain`.** Not declared for a broken scale. Its `domain` is the two
  outer ends and not what it covers, and letting `KEY_MISMATCH` compare a key
  against that number would make a genuine disagreement agree; see
  `plot.scale._declare_domain`.

* **`OFF_PANEL`.** Unaffected, and checked: it reports *text* that leaves the
  plot box, and nothing here is text. A datum inside a break maps to the band
  edge, which is inside the box, so a label written at one is not reported --
  it is simply in the wrong place, and no rule can tell that from a label in
  the right one.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from ..core import Diagram, EllipsePrim, PathPrim, Rect, RectPrim, resolve
from ..draw.coords import active_theme
from ..draw.path import polygon, polyline
from ..draw.place import place as draw_place
from ..draw.shapes import MARK_KIND

__all__ = ["AxisBreaks", "BREAK_NOTE", "BREAK_KIND", "axis_break_glyph",
           "break_marks", "gap_bands", "mark_break_glyph", "outside_breaks"]

#: The kind on each stroke of a break glyph. Not in the theme's role table on
#: purpose: inside an axis group it inherits the spine's ink and weight, which
#: is what it is a piece of, and a caller who wants to restyle only the breaks
#: still has a selector for them.
BREAK_KIND = "axis-break"

#: What the paper showing through a broken bar is drawn as. It *is* the plot
#: area -- the page the bar was painted onto -- so it takes the plot area's
#: role and follows the theme's paper into a dark variant instead of carrying
#: a baked-in white.
PAPER_KIND = "plot-area"

#: The note an axis leaves to say it was drawn broken, in the axis's own frame.
#: `inklet.diagnostics.break_rules` is the reader; see `AxisBreaks`.
BREAK_NOTE = "axis_breaks"

#: Half the glyph's reach across the axis line, as a fraction of body size:
#: about 1mm at 7pt, so the pair reads as a mark at 89mm wide without becoming
#: a piece of data.
_REACH_OF_TYPE = 0.40

#: The slash's lean, as a fraction of its half-reach -- about 24 degrees off
#: perpendicular. Steeper and the two strokes stop reading as parallel; flatter
#: and they read as a second axis crossing this one.
_LEAN = 0.45

#: The distance between the two strokes, as a fraction of body size. Under
#: about a quarter em they merge into one thick mark at print size.
_SEP_OF_TYPE = 0.26

#: One tooth of the cut across a mark, as a fraction of body size: about 2mm
#: at 7pt, so a column-width bar is cut with five or six of them.
_TOOTH_OF_TYPE = 0.8

#: How far each tooth rises off the cut line, as a fraction of body size. Just
#: enough to read as a saw at 89mm wide and not so much that the two cuts of
#: one break meet in the middle of the default gap.
_TOOTH_RISE_OF_TYPE = 0.16

#: How far inside a gap a tick has to fall before it is dropped. A tick exactly
#: on a band edge is the last value the axis draws and is kept; this is float
#: slack, not a design choice.
_INSIDE_SLACK = 1e-6


@dataclass(frozen=True, slots=True)
class AxisBreaks:
    """Where an axis stopped and started again, in the frame it was built in.

    Left as a note on the axis node so that a rule can answer the one question
    geometry alone cannot: is that gap in the bar a break, or is it two bars?
    The data `segments` come with the millimetre `bands` they were drawn into,
    which is what lets `BREAK_DISTORTS` read a mark's height back into the
    quantity it stands for and say by how much the page disagrees with the
    numbers.

    Frozen and hashable: it travels up through every wrapper that
    `carry_notes` builds, and the reader keeps the deepest node carrying each
    distinct value -- the axis that wrote it, whose own frame this is.
    """

    #: Whether the broken scale runs along x. False for a left or right axis.
    horizontal: bool
    #: The data intervals the axis draws, low to high.
    segments: tuple[tuple[float, float], ...]
    #: Each segment's millimetres, in the same order and the range's direction.
    bands: tuple[tuple[float, float], ...]

    @property
    def gaps(self) -> tuple[tuple[float, float], ...]:
        """The millimetre stretches between bands, in the range's direction."""
        return tuple((a[1], b[0]) for a, b in zip(self.bands, self.bands[1:]))

    def value_at(self, position: float) -> float:
        """The data value a millimetre position stands for.

        The inverse of the scale, restated from the note so that a rule needs
        no scale object -- it has a picture and a node, not the code that drew
        them. Inside a gap, or off the ends, the nearest band's answer: a rule
        asking this about a mark's edge is asking how tall the mark reads as,
        and every millimetre of it reads as something.
        """
        low = self.bands[0][0]
        step = 1.0 if self.bands[-1][1] >= low else -1.0
        for (start, end), (lo, hi) in zip(self.bands, self.segments):
            if (position - end) * step <= 0:
                if end == start:                         # pragma: no cover
                    return lo
                return lo + (position - start) / (end - start) * (hi - lo)
        start, end = self.bands[-1]
        lo, hi = self.segments[-1]
        return lo + (position - start) / (end - start) * (hi - lo)


def gap_bands(scale) -> tuple[tuple[float, float], ...]:
    """The millimetre gaps a scale leaves for its breaks, or none.

    Asked of the scale by name rather than by type, so a caller's own broken
    scale gets an interrupted spine and a break glyph for free -- and so that
    every scale in the library keeps working without knowing this exists.
    """
    reader = getattr(scale, "gap_bands", None)
    if not callable(reader):
        return ()
    return tuple((min(a, b), max(a, b)) for a, b in reader())


def outside_breaks(scale, values: Sequence) -> tuple:
    """`values`, less any that would land inside a break.

    A tick in the gap is the one thing a broken axis cannot have: it says the
    scale runs through, which is the exact opposite of what the gap claims.
    `Broken.ticks` never proposes one, so this is for the caller who passed
    `ticks=` by hand -- and for the gridlines, which come through the same
    `axis.tick_values` and would otherwise rule across the break.

    Judged in data units where the scale can say what its breaks are, because
    `map` puts a value inside a break on the nearer *band edge* -- so a tick at
    100 on an axis broken at (45, 330) would sit exactly on the 45 mark and be
    kept, labelled 100, which is worse than the tick this exists to remove. A
    scale that only knows its millimetres falls back to asking where the value
    lands, which catches everything except that edge.
    """
    cuts = getattr(scale, "breaks", None)
    if cuts:
        return tuple(v for v in values if not _in_span(v, cuts))
    gaps = gap_bands(scale)
    if not gaps:
        return tuple(values)
    kept = []
    for value in values:
        at = scale.map(value)
        if any(lo + _INSIDE_SLACK < at < hi - _INSIDE_SLACK for lo, hi in gaps):
            continue
        kept.append(value)
    return tuple(kept)


def _in_span(value, spans: Sequence[tuple[float, float]]) -> bool:
    """Whether a tick value falls strictly inside one of the missing pieces.

    Strictly, so that the two values the break starts and stops at -- the last
    number the axis draws on each side -- survive; they are the ones that tell
    the reader what was skipped.
    """
    try:
        at = float(value)
    except (TypeError, ValueError):
        return False              # a category cannot be inside a numeric break
    return any(lo < at < hi for lo, hi in spans)


def axis_break_glyph(a: float, b: float, *, horizontal: bool,
                     theme=None, **style) -> list[Diagram]:
    """The two strokes that mark one interruption of a spine.

    `a` and `b` are the ends of the gap along the axis, in the axis's own
    millimetres; the strokes straddle the spine symmetrically, so which side
    the ticks hang on does not come into it.
    """
    theme = active_theme() if theme is None else theme
    reach = _REACH_OF_TYPE * theme.font_size
    lean = _LEAN * reach
    half = _SEP_OF_TYPE * theme.font_size / 2
    middle = (a + b) / 2
    out = []
    for offset in (-half, half):
        at = middle + offset
        ends = (((at - lean, reach), (at + lean, -reach)) if horizontal
                else ((-reach, at + lean), (reach, at - lean)))
        out.append(polyline(ends, kind=BREAK_KIND, **style))
    return out


def mark_break_glyph(a: float, b: float, across: tuple[float, float], *,
                     horizontal: bool, theme=None) -> list[Diagram]:
    """The same mark across a bar that runs through the break.

    `a` and `b` are the ends of the gap on the broken axis and `across` is the
    mark's two edges on the other one, both in panel millimetres. The page is
    painted back in between the strokes rather than the bar being cut: the bar
    keeps its own geometry, which is what the linter measures and what a
    reader clicking the shape gets, and the break is furniture laid over it.

    Slanted by the same lean as the spine glyph and by an amount that does not
    depend on how wide the bar is, so every break on the figure is the same
    mark at the same angle -- a slant proportional to the bar would give a
    grouped series three different glyphs.
    """
    theme = active_theme() if theme is None else theme
    lo, hi = min(a, b), max(a, b)
    # Half a stroke past each edge, so the bar's own outline does not show
    # through the paper as two ticks in the middle of the break.
    edge0 = min(across) - theme.stroke / 2
    edge1 = max(across) + theme.stroke / 2
    rise = _TOOTH_RISE_OF_TYPE * theme.font_size
    near = _zigzag(edge0, edge1, lo, rise, theme, horizontal)
    far = _zigzag(edge0, edge1, hi, rise, theme, horizontal)
    return [
        polygon(tuple(near) + tuple(reversed(far)), kind=PAPER_KIND),
        polyline(near, kind=BREAK_KIND),
        polyline(far, kind=BREAK_KIND),
    ]


def _zigzag(edge0: float, edge1: float, at: float, rise: float, theme,
            horizontal: bool) -> list[tuple[float, float]]:
    """One cut across a mark: a shallow zigzag about the line `at`.

    A tooth is a fixed width, not a fraction of the mark, so every bar on the
    figure is cut with the same saw and a grouped series does not come out with
    three different glyphs. Two straight slanted lines would be the honest
    alternative and were the first try; at the width of a bar the slant that
    keeps the two lines from crossing is under two degrees, which reads as a
    printing accident rather than as a mark somebody made.

    Under two teeth there is no room for the rhythm, and the cut is a single
    slant -- the same shape the axis draws, at the only angle that fits.
    """
    width = edge1 - edge0
    tooth = _TOOTH_OF_TYPE * theme.font_size
    teeth = int(width / tooth)
    if teeth < 2:
        lean = min(rise, width / 2)
        return _across((edge0, at - lean), (edge1, at + lean), horizontal)
    step = width / teeth
    points = []
    for i in range(teeth + 1):
        offset = rise if i % 2 else -rise
        points.append(_across((edge0 + i * step, at + offset), None, horizontal)[0])
    return points


def _across(first, second, horizontal: bool) -> list[tuple[float, float]]:
    """Points written along the mark, turned to face the broken axis.

    `horizontal` means the *break* runs along x, so the mark lies down and what
    the cut travels along is y. Written once here rather than in a branch per
    shape, which is where the first version of this got the two transposed.
    """
    pairs = [p for p in (first, second) if p is not None]
    if horizontal:
        return [(b, a) for a, b in pairs]
    return list(pairs)


def break_marks(panel):
    """Stamp the break glyph across every filled mark that crosses a break.

    The implementation of `Panel.break_marks`. The *axis* marks its own break;
    this is the other half a journal asks for. Which marks cross is a question
    about the picture, not about the call that drew it -- a stacked series, a
    grouped series and a histogram all cross a break the same way -- so the
    panel's own content is resolved and measured, and any filled data mark that
    spans a gap end to end gets the glyph across its width.

    Deliberately not automatic. `bars()` cannot know whether the panel will
    still have a broken axis by the time it is built, `build()` is shared, and
    a figure that draws its bars through a break on purpose -- to show that the
    scale is the same either side -- is a figure the author is entitled to
    draw. `BREAK_DISTORTS` reports the crossing either way, which is the part
    that must not be optional.
    """
    theme = active_theme()
    items: list[Diagram] = []
    for horizontal, scale in ((True, panel.x), (False, panel.y)):
        for lo, hi in gap_bands(scale):
            for box in _crossing_marks(panel, lo, hi, horizontal):
                across = ((box.y0, box.y1) if horizontal else (box.x0, box.x1))
                items.extend(mark_break_glyph(lo, hi, across,
                                              horizontal=horizontal, theme=theme))
    if not items:
        return panel
    return panel.over(draw_place(items, origin=(0, 0)), clip=False)


def _crossing_marks(panel, lo: float, hi: float,
                    horizontal: bool) -> list[Rect]:
    """The boxes of the filled data marks that span a gap end to end.

    Resolved rather than walked, because a mark's position is the product of
    every transform above it and a bar drawn by `bars()` sits under two. The
    boxes come back in the panel's own frame, which is the frame the gap is in.
    """
    content = Diagram(children=tuple(panel._content))
    if content.is_empty:
        return []
    out = []
    for placed in resolve(content).values():
        node = placed.diagram
        if node.kind != MARK_KIND or not _is_filled(node):
            continue
        box = placed.bbox
        if box is None:                                  # pragma: no cover
            continue
        near, far = ((box.x0, box.x1) if horizontal else (box.y0, box.y1))
        if near < lo - _INSIDE_SLACK and far > hi + _INSIDE_SLACK:
            out.append(box)
    # Left to right, then top to bottom: the order marks were drawn in is the
    # order a `place` happened to build them, and a figure must not depend on
    # it. Two glyphs never overlap, so this only fixes the file's byte order.
    out.sort(key=lambda b: (round(b.x0, 6), round(b.y0, 6)))
    return out


def _is_filled(node: Diagram) -> bool:
    """Whether this mark has area for a break to interrupt.

    A rectangle or an ellipse always does; a path only when it was built
    filled, which is what separates a violin's body from a line through the
    same points.
    """
    prim = node.prim
    if isinstance(prim, PathPrim):
        return prim.filled
    return isinstance(prim, (RectPrim, EllipsePrim))


def axis_breaks_note(scale, *, horizontal: bool) -> AxisBreaks | None:
    """The note for an axis over `scale`, or None when it is not broken."""
    bands = getattr(scale, "bands", None)
    segments = getattr(scale, "segments", None)
    if not callable(bands) or segments is None or len(segments) < 2:
        return None
    return AxisBreaks(horizontal=horizontal,
                      segments=tuple((float(lo), float(hi))
                                     for lo, hi in segments),
                      bands=tuple((float(a), float(b)) for a, b in bands()))


def spine_runs(start: float, end: float,
               gaps: Sequence[tuple[float, float]]) -> list[tuple[float, float]]:
    """`start`..`end` cut into the pieces a broken spine actually draws.

    In the range's own direction, which for a y axis runs backwards, so the
    gaps are sorted along that direction rather than numerically.
    """
    if not gaps:
        return [(start, end)]
    forward = end >= start
    ordered = sorted(gaps, key=lambda g: g[0], reverse=not forward)
    runs = []
    at = start
    for lo, hi in ordered:
        near, far = (lo, hi) if forward else (hi, lo)
        runs.append((at, near))
        at = far
    runs.append((at, end))
    return [(a, b) for a, b in runs if abs(b - a) > _INSIDE_SLACK]
