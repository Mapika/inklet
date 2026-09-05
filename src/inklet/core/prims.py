"""Leaf drawing content.

A primitive knows its own geometry and nothing about layout. Crucially, core
never measures text: `TextPrim` arrives pre-shaped from `inklet.typeset`, carrying the
metrics HarfBuzz produced. That keeps this module free of font dependencies and
keeps there being exactly one place where glyph advances come from.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable, Sequence

from .envelope import Envelope
from .geom import ORIGIN, Rect, Vec2
from .trace import Trace


#: The two ways a filled path can decide what is inside it. Both are SVG's and
#: PDF's own spelling, so a backend can pass the string straight through.
FILL_RULES = ("nonzero", "evenodd")


class Prim:
    """Interface: report an envelope and a trace in local coordinates."""

    def envelope(self) -> Envelope:
        raise NotImplementedError

    def trace(self) -> Trace:
        raise NotImplementedError


@dataclass(frozen=True, slots=True)
class RectPrim(Prim):
    """Centred on the local origin, like every primitive here. Centring makes
    rotation and stacking behave without an anchor-correction step."""

    width: float
    height: float
    radius: float = 0.0

    @property
    def rect(self) -> Rect:
        return Rect.from_size(self.width, self.height)

    def envelope(self) -> Envelope:
        return Envelope.from_rect(self.rect)

    def trace(self) -> Trace:
        if self.radius <= 0:
            return Trace.from_rect(self.rect)
        return Trace.from_polygon(_rounded_outline(self.rect, self.radius))


@dataclass(frozen=True, slots=True)
class EllipsePrim(Prim):
    rx: float
    ry: float

    def envelope(self) -> Envelope:
        return Envelope.from_ellipse(ORIGIN, self.rx, self.ry)

    def trace(self) -> Trace:
        return Trace.from_ellipse(ORIGIN, self.rx, self.ry)


@dataclass(frozen=True, slots=True)
class Subpath:
    """A polyline with optional cubic segments.

    `points` is always the flattened form, and geometry -- envelopes, traces --
    is computed from it alone. `curves` carries exact control points so a
    renderer can emit real beziers instead of the flattening.

    Invariant: when `curves` is non-empty it must cover the **whole** subpath,
    tip to tip, with each cubic starting where the previous one ended. A
    renderer draws from `curves` alone when it is present, so a partial list --
    say, only the rounded corners of an elbow -- silently loses the straight
    runs between them. Emit degenerate cubics for straight segments instead.
    """

    points: tuple[Vec2, ...]
    closed: bool = False
    curves: tuple[tuple[Vec2, Vec2, Vec2, Vec2], ...] = ()


@dataclass(frozen=True, slots=True)
class PathPrim(Prim):
    subpaths: tuple[Subpath, ...]
    filled: bool = False
    # How overlapping subpaths combine when this is filled: "nonzero" counts
    # winding, "evenodd" counts crossings. Only "evenodd" can express a hole
    # wound the same way as its outer ring -- a glyph counter, a washer traced
    # off a mesh, any ring whose two contours arrived from a source that did
    # not think about winding. Ignored entirely when `filled` is False, since
    # a stroke has no interior to rule on. Default "nonzero" is what every
    # backend already assumed, so nothing that exists changes.
    fill_rule: str = "nonzero"

    def __post_init__(self) -> None:
        if self.fill_rule not in FILL_RULES:
            raise ValueError(
                f"fill_rule must be one of {', '.join(FILL_RULES)}, "
                f"got {self.fill_rule!r}"
            )

    @staticmethod
    def polyline(points: Iterable[Vec2], closed: bool = False,
                 filled: bool = False, fill_rule: str = "nonzero") -> PathPrim:
        return PathPrim((Subpath(tuple(points), closed),), filled, fill_rule)

    def envelope(self) -> Envelope:
        pts = [p for sub in self.subpaths for p in sub.points]
        return Envelope.from_points(pts) if pts else Envelope.empty()

    def trace(self) -> Trace:
        result = Trace.empty()
        for sub in self.subpaths:
            if len(sub.points) >= 2:
                result = result.union(Trace.from_polygon(sub.points, sub.closed))
        return result


@dataclass(frozen=True, slots=True)
class TextRun:
    """A span of one line drawn in one font.

    A line needs more than one run when the family it was shaped in has no
    glyph for part of it -- a Japanese clause inside a Latin caption -- and the
    typesetter found a face that does. `advance` is that span's own shaped
    width, so a backend can place the next run without reshaping anything.
    """

    text: str
    font_family: str
    advance: float
    font_path: str | None = None
    # Which face within a .ttc/.otc collection. Losing it would send anything
    # reopening the file to face 0, which in a CJK collection is a different
    # font with different coverage.
    font_index: int = 0
    # A sub- or superscript: drawn at `size` mm rather than the prim's, with
    # its baseline `shift` mm below the line's (negative is up). Zero shift at
    # the prim's size is ordinary text; `advance` is already measured at `size`.
    size: float | None = None
    shift: float = 0.0
    # This span's own colour, overriding the text node's `fill` for these
    # glyphs alone. None -- the ordinary case -- inherits, so a run that only
    # exists because of a font fallback does not have to restate the style it
    # was already going to be drawn in. Colour has no width, so nothing that
    # measures changes; only a backend painting glyphs reads it.
    fill: str | None = None


@dataclass(frozen=True, slots=True)
class TextLine:
    """One laid-out line. `advance` is the shaped width; `baseline` is the offset
    of this line's baseline from the block's first baseline."""

    text: str
    advance: float
    baseline: float
    # Extra millimetres given to each space in this line, which is how a
    # justified line reaches the column edge. `advance` already includes it, so
    # every measurement in core stays correct without knowing about it; only a
    # backend drawing the glyphs needs to read it.
    word_spacing: float = 0.0
    # The line split into single-font spans, when one font could not draw all
    # of it. Empty is the ordinary case and means the whole line is the prim's
    # family. `text` and `advance` are correct either way, so nothing that only
    # measures needs to look in here -- only a backend placing glyphs does.
    runs: tuple[TextRun, ...] = ()


@dataclass(frozen=True, slots=True)
class TextPrim(Prim):
    lines: tuple[TextLine, ...]
    font_family: str
    font_size: float          # mm
    ascent: float             # mm above the first baseline
    descent: float            # mm below the last baseline, positive downward
    # start | center | end | justify, within the text block. Justified lines
    # arrive already stretched to the block width by the typesetter, so here it
    # only says where the *short* last line sits -- which is at the start.
    align: str = "center"
    font_path: str | None = None
    # What the author asked for, when that differs from what was resolved.
    # fc-match never fails, so a request for Helvetica silently becomes Noto
    # Sans; recording it is what lets the linter say so.
    requested_family: str | None = None
    # Distinct characters no installed font could draw, which will render as
    # empty boxes. A font with no glyph still reports an advance -- the .notdef
    # box has a width -- so this is the only trace left that the measurement
    # was of nothing.
    missing: str = ""
    # The OpenType features these advances were measured under, as sorted
    # `(tag, value)` pairs -- the immutable, comparable form of the dict the
    # caller wrote. Anything that reshapes this block afterwards (outlining it
    # to paths, placing live glyphs) has to ask the shaper the same question or
    # it lays glyphs out by different rules than the layout was built on: ten
    # tabular digits shaped with `tnum` measure 58.00mm and outline 54.24mm
    # without it. Carrying it here is what makes that mismatch impossible
    # rather than merely documented. Empty means "the shaper's defaults", which
    # is every block anyone has written so far.
    features: tuple[tuple[str, bool | int], ...] = ()

    @property
    def text(self) -> str:
        return "\n".join(line.text for line in self.lines)

    @property
    def width(self) -> float:
        return max((line.advance for line in self.lines), default=0.0)

    @property
    def height(self) -> float:
        if not self.lines:
            return 0.0
        return self.ascent + self.lines[-1].baseline + self.descent

    def line_offset(self, line: TextLine) -> float:
        """Horizontal offset of a line's start within the centred block."""
        slack = self.width - line.advance
        return {"start": 0.0, "center": slack / 2, "end": slack,
                "justify": 0.0}[self.align]

    @property
    def first_baseline(self) -> float:
        """Local y of the first baseline. The block is centred on the origin so
        that a text prim drops into a stack like any other shape."""
        return -self.height / 2 + self.ascent

    def envelope(self) -> Envelope:
        if not self.lines:
            return Envelope.empty()
        return Envelope.from_rect(Rect.from_size(self.width, self.height))

    def trace(self) -> Trace:
        if not self.lines:
            return Trace.empty()
        return Trace.from_rect(Rect.from_size(self.width, self.height))


def text_features(features) -> tuple[tuple[str, int], ...]:
    """The canonical `TextPrim.features` form of whatever a caller wrote.

    A mapping, a sequence of pairs, or None. Sorted by tag, because a dict
    preserves the order it was typed in and two callers asking for the same two
    features in the other order should build equal prims -- and because a
    shaper does not care what order it is handed them in. `True` becomes 1,
    which is what an OpenType feature value is and what `typeset.feature_key`
    already produces, so the two agree on the bytes and not merely on `==`.
    """
    if not features:
        return ()
    pairs = features.items() if hasattr(features, "items") else features
    return tuple(sorted((str(tag), int(value)) for tag, value in pairs))


@dataclass(frozen=True, slots=True)
class ImagePrim(Prim):
    """A raster placed at a physical size. `outline` is the cutout silhouette in
    local coordinates when one is known, so arrows clip to the subject rather
    than to the picture frame."""

    source: str
    width: float
    height: float
    pixel_size: tuple[int, int] | None = None
    outline: tuple[Vec2, ...] = ()
    # The encoded file itself -- PNG or JPEG bytes -- for a raster that was
    # generated rather than loaded. A heatmap computed into an array has no
    # path to point at, and writing one out only so a backend can read it back
    # makes the figure depend on a temporary file. When this is set `source` is
    # a label: what to call the image in a diagnostic, not where to find it.
    data: bytes | None = None
    # Whether a renderer may resample this raster smoothly. None is not an
    # opinion: it leaves the choice to the backend, which is what a photograph
    # wants and what every existing caller gets. False asks for
    # nearest-neighbour -- a heatmap drawn one pixel per cell is data, and
    # bilinear resampling invents values between the cells and blurs a
    # boundary the reader is meant to be able to point at. True insists on
    # smoothing where a backend would otherwise have guessed not to.
    smooth: bool | None = None

    @property
    def rect(self) -> Rect:
        return Rect.from_size(self.width, self.height)

    def effective_dpi(self) -> float | None:
        if self.pixel_size is None or self.width <= 0:
            return None
        return self.pixel_size[0] / (self.width / 25.4)

    def envelope(self) -> Envelope:
        if self.outline:
            return Envelope.from_points(self.outline)
        return Envelope.from_rect(self.rect)

    def trace(self) -> Trace:
        if self.outline:
            return Trace.from_polygon(self.outline, closed=True)
        return Trace.from_rect(self.rect)


@dataclass(frozen=True, slots=True)
class PhantomPrim(Prim):
    """Occupies space without drawing anything, and without catching rays.

    Asymmetric padding needs an envelope contribution that renderers ignore.
    The empty trace is the important half: padding must not clip an arrow that
    is aiming for the shape inside it.
    """

    box: Rect

    def envelope(self) -> Envelope:
        return Envelope.from_rect(self.box)

    def trace(self) -> Trace:
        return Trace.empty()


def _rounded_outline(rect: Rect, radius: float, steps: int = 6) -> tuple[Vec2, ...]:
    """Polygonal stand-in for a rounded rectangle, used only for ray hits."""
    r = min(radius, rect.width / 2, rect.height / 2)
    if r <= 0:
        return rect.corners
    centres = [
        (Vec2(rect.x1 - r, rect.y1 - r), 0.0),
        (Vec2(rect.x0 + r, rect.y1 - r), 90.0),
        (Vec2(rect.x0 + r, rect.y0 + r), 180.0),
        (Vec2(rect.x1 - r, rect.y0 + r), 270.0),
    ]
    points: list[Vec2] = []
    for centre, start in centres:
        for i in range(steps + 1):
            angle = math.radians(start + 90.0 * i / steps)
            points.append(centre + Vec2(math.cos(angle), math.sin(angle)) * r)
    return tuple(points)
