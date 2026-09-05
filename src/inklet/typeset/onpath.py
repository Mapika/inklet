"""Type set along a curve, and type set at an angle.

Two things that look like one. A rotated block and a curved one both need the
shaped run to be *placed* rather than re-measured, and the whole point of
`inklet.typeset` is that measurement happened once, in HarfBuzz, with the right
face and the right features. So nothing here reshapes anything it did not
have to: `text_on_path` walks the same buffer `render.glyphs` walks, stops at
the shaping cluster rather than at the glyph, and hands each cluster to the
station its own advance puts it at.

**The sign convention, once, loudly.** Angles are degrees, y grows downward,
and `Affine.rotation` turns +x toward +y -- so a *positive* angle turns
**clockwise on the page**. `angle=90` reads top-to-bottom; `angle=-90` is the
bottom-to-top y-axis label every plot wants. Bearings on an arc are the same
degrees: 0 is due east, 90 is due *south* on the page, and increasing bearing
sweeps clockwise. This matches `Vec2.angle()`, `inklet.arc` and `draw.sector`,
and it is the only convention in the library.

## What comes back

A group whose children are the placed clusters, one live `TextPrim` each under
a rotate-and-translate. That is what keeps the searchable-text contract: under
`text="names"` and `text="embed"` the words are still text elements, one per
cluster, in reading order; under `text="outline"` and in PDF they outline
through the ordinary path with no special case, because they are ordinary text
nodes. The cost is that a reader copying the string out of the SVG may get it
cluster by cluster rather than as one run -- the alternative was an SVG
`<textPath>`, which hands the shaping back to the viewer and would place the
glyphs by advances inklet never measured.

The group's envelope is the union of the placed clusters, so it is the real
curved extent and `hstack`, `inklet.lint` and `Figure.report` all see the truth
rather than the straight block's box. The whole string is recorded on the
group as `typeset.outline.TEXT_NOTE`, so a diagnostic can quote the label even
though no single node spells it.
"""

from __future__ import annotations

import bisect
import math
from dataclasses import dataclass
from typing import Iterable, Sequence

from ..core.diagram import Diagram
from ..core.geom import IDENTITY, ORIGIN, Affine, Vec2
from ..core.prims import PathPrim, Subpath, TextLine, TextPrim
from ..core.style import EMPTY_STYLE, Style
from .fonts import FontFace, load_face
from .outline import TEXT_NOTE
from .shaping import feature_key, shape_buffer

__all__ = ["Baseline", "ONPATH_KIND", "CLUSTER_KIND", "OVERFLOW_MODES",
           "baseline", "baseline_arc", "text_on_arc", "text_on_path"]

#: The group `text_on_path` returns. Selectable, and distinct from `"text"` so
#: that counting the text blocks on a page does not count every letter of a
#: curved label as one.
ONPATH_KIND = "text-on-path"

#: One placed cluster. `"glyphs"` is `diagnostics.rules._CARRIER_KINDS`, the
#: existing name for "geometry a transform generated, never authored" -- which
#: is exactly what these are, and what makes a finding about one of them speak
#: of the label above it instead of quoting an id the author never wrote.
CLUSTER_KIND = "glyphs"

#: What `text_on_path(overflow=)` accepts. See `text_on_path` for why
#: `"extend"` is the default.
OVERFLOW_MODES = ("extend", "raise")

#: The anchor `inklet.draw` puts on a shape it has recentred, recording where the
#: author's (0, 0) went -- `draw.coords.ORIGIN_ANCHOR`. Spelled again here
#: rather than imported because `draw` imports `typeset` and not the other way
#: round; `tests/test_text_on_path.py` pins the two spellings together. Copying
#: it from the curve onto the placed run is what makes `inklet.drawn([ring,
#: label])` put the type back on the ring rather than beside it.
_ORIGIN_ANCHOR = "origin"

# Station resolution of a sampled baseline, in samples per millimetre. A
# cluster is placed by interpolating between two samples, so this bounds the
# station error at half a sample -- 25 micrometres, which is a fifth of the
# thinnest hairline the themes draw. Tangents are exact at every sample (they
# come from the curve's own derivative), so only the position interpolates.
_SAMPLES_PER_MM = 20

# Floor and ceiling on the samples one cubic gets, so that a 0.1mm joining
# segment still has a direction and a 400mm spiral does not cost a megabyte.
_MIN_SAMPLES = 8
_MAX_SAMPLES = 4096

_EPS = 1e-12


# -- the curve -------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Baseline:
    """A curve to set type along, resampled as one arclength axis.

    `points[i]` is at `lengths[i]` millimetres along the curve and the unit
    tangent there is `tangents[i]`. Building this eagerly is what makes glyph
    stations deterministic: every run over the same curve interpolates the same
    table, so the SVG is byte-identical twice, and a caller cannot accidentally
    ask for a different sampling.
    """

    points: tuple[Vec2, ...]
    tangents: tuple[Vec2, ...]
    lengths: tuple[float, ...]

    @property
    def length(self) -> float:
        return self.lengths[-1]

    @property
    def start(self) -> Vec2:
        return self.points[0]

    @property
    def end(self) -> Vec2:
        return self.points[-1]

    def at(self, station: float) -> tuple[Vec2, Vec2]:
        """The point and unit tangent `station` mm along, from the start.

        Off either end the curve is continued straight along its own end
        tangent, which is what `overflow="extend"` draws and what makes a
        cluster that only half overhangs still line up with the one before it.
        """
        if station <= 0.0:
            return self.points[0] + self.tangents[0] * station, self.tangents[0]
        if station >= self.length:
            over = station - self.length
            return self.points[-1] + self.tangents[-1] * over, self.tangents[-1]
        i = bisect.bisect_right(self.lengths, station) - 1
        span = self.lengths[i + 1] - self.lengths[i]
        t = 0.0 if span <= _EPS else (station - self.lengths[i]) / span
        point = self.points[i] + (self.points[i + 1] - self.points[i]) * t
        return point, _lerp_direction(self.tangents[i], self.tangents[i + 1], t)

    def offset(self, distance: float) -> Baseline:
        """The parallel curve `distance` mm to the *right* of the direction of
        travel -- which for text set `side="above"` is below the letters.

        Type set on the offset of a drawn curve stands clear of it instead of
        sitting on the stroke, and the stations come out right: the parallel of
        a bend is longer on the outside and shorter on the inside, and
        recomputing the arclength here is what stops a run from creeping when
        it is lifted off a tight corner.

        Approximate in one way worth knowing: the offset of a curve whose
        radius of curvature is smaller than `distance` folds back on itself,
        and nothing here detects that. Offsetting a 2mm fillet by 3mm gives a
        cusp, exactly as it does in every other offsetting code.
        """
        points = tuple(p + Vec2(-t.y, t.x) * distance
                       for p, t in zip(self.points, self.tangents))
        lengths = [0.0]
        for a, b in zip(points, points[1:]):
            lengths.append(lengths[-1] + (b - a).length)
        return Baseline(points, self.tangents, tuple(lengths))

    def reversed(self) -> Baseline:
        """The same curve walked the other way: stations measured from the far
        end, tangents turned round. Setting a run on it is what puts the type
        on the other side of the line without mirroring a single glyph."""
        total = self.length
        return Baseline(
            points=tuple(reversed(self.points)),
            tangents=tuple(-t for t in reversed(self.tangents)),
            lengths=tuple(total - v for v in reversed(self.lengths)),
        )


def _lerp_direction(a: Vec2, b: Vec2, t: float) -> Vec2:
    """A unit direction between two unit directions.

    Linear then renormalised rather than a slerp: at the sampling this module
    uses, neighbouring tangents are under a degree apart and the two agree to
    better than a millidegree. The degenerate case -- exactly opposite
    tangents, which only a cusp produces -- keeps `a` rather than dividing by
    a length of zero.
    """
    mix = a * (1.0 - t) + b * t
    return a if mix.length <= _EPS else mix.normalized()


def baseline(source: object = (), *, curves: Sequence[Sequence[object]] | None = None,
             closed: bool = False) -> Baseline:
    """A `Baseline` from whatever describes the curve.

    `source` may be a drawn node (`inklet.curve`, `inklet.arc`, `inklet.polyline` --
    anything holding a `PathPrim`), a `PathPrim` or `Subpath`, or a sequence of
    points; `curves` is a chain of cubics `(p0, c1, c2, p3)` written the way
    `inklet.path(curves=...)` takes them. A node's exact cubics are used when it
    has them, so type set along a curve lands on the curve the backend draws
    rather than on its flattening.

    Only the first subpath is read: a baseline is one run of type, and a path
    with a hole in it has no single arclength axis.

    A node's geometry is taken in the frame the node presents to *its* parent,
    transforms and all, so the run lands where the curve is drawn and not where
    it was authored. `inklet.draw` recentres every shape it builds, so the two
    differ for any arc worth setting type on -- and `text_on_path` copies the
    node's `origin` anchor onto the group it returns, which is what keeps
    `inklet.drawn([ring, label])` in register.
    """
    if isinstance(source, Baseline):
        return source
    if curves is not None:
        return _from_cubics([tuple(_vec(p) for p in c) for c in curves])
    found = _subpath_of(source)
    if found is not None:
        sub, at = found
        if sub.curves:
            chain = [tuple(at.apply(p) for p in c) for c in sub.curves]
            if sub.closed:
                chain.append(_straight(chain[-1][3], chain[0][0]))
            return _from_cubics(chain)
        return _from_points([at.apply(p) for p in sub.points], sub.closed)
    return _from_points([_vec(p) for p in source], closed)   # type: ignore[arg-type]


def baseline_arc(radius: float, start: float, end: float,
                 centre: object = ORIGIN) -> Baseline:
    """The circular arc from bearing `start` to bearing `end`, exactly.

    Degrees, and clockwise-positive like everything else here: `start=0` is due
    east of `centre` and `end` greater than `start` sweeps clockwise on the
    page. Sampled from the circle itself rather than from cubics, so the
    stations are the true arclength and the tangents are exact -- which at a
    5mm radius is the difference between a letter sitting on the curve and one
    sitting a hair inside it.
    """
    if radius <= 0:
        raise ValueError(f"a baseline arc needs a positive radius, got {radius!r}")
    hub = _vec(centre)
    sweep = math.radians(end - start)
    if abs(sweep) <= _EPS:
        raise ValueError(f"an arc from {start} to {end} degrees has no length")
    steps = _sample_count(abs(sweep) * radius)
    a0 = math.radians(start)
    sign = 1.0 if sweep > 0 else -1.0
    points, tangents, lengths = [], [], []
    for i in range(steps + 1):
        a = a0 + sweep * i / steps
        cos, sin = math.cos(a), math.sin(a)
        points.append(Vec2(hub.x + radius * cos, hub.y + radius * sin))
        tangents.append(Vec2(-sin * sign, cos * sign))
        lengths.append(abs(sweep) * radius * i / steps)
    return Baseline(tuple(points), tuple(tangents), tuple(lengths))


def _sample_count(length: float) -> int:
    return max(_MIN_SAMPLES, min(_MAX_SAMPLES,
                                 int(math.ceil(length * _SAMPLES_PER_MM))))


def _subpath_of(source: object) -> tuple[Subpath, Affine] | None:
    """The first subpath under `source`, and the transform into `source`'s frame.

    A bare `Subpath` or `PathPrim` is already in the frame the caller means, so
    it comes back with the identity. A node is searched depth-first for the
    first path leaf, accumulating transforms on the way down -- `inklet.arc`
    returns a leaf and `inklet.curve(...)` inside a group returns a child, and
    both have to answer in the coordinates their holder sees.
    """
    if isinstance(source, Subpath):
        return source, IDENTITY
    if isinstance(source, PathPrim) and source.subpaths:
        return source.subpaths[0], IDENTITY
    if isinstance(source, Diagram):
        return _first_path(source, IDENTITY)
    return None


def _first_path(node: Diagram, at: Affine) -> tuple[Subpath, Affine] | None:
    here = at @ node.transform
    if isinstance(node.prim, PathPrim) and node.prim.subpaths:
        return node.prim.subpaths[0], here
    for child in node.children:
        found = _first_path(child, here)
        if found is not None:
            return found
    return None


def _vec(p: object) -> Vec2:
    if isinstance(p, Vec2):
        return p
    x, y = p                                              # type: ignore[misc]
    return Vec2(float(x), float(y))


def _straight(a: Vec2, b: Vec2) -> tuple[Vec2, Vec2, Vec2, Vec2]:
    """A cubic on its own chord, so a closing segment joins the chain."""
    return (a, a + (b - a) * (1 / 3), a + (b - a) * (2 / 3), b)


def _from_points(points: Iterable[Vec2], closed: bool) -> Baseline:
    pts = [p for p in points]
    if closed and len(pts) >= 2 and (pts[0] - pts[-1]).length > _EPS:
        pts.append(pts[0])
    if len(pts) < 2:
        raise ValueError("a baseline needs at least two points")
    return _from_cubics([_straight(a, b) for a, b in zip(pts, pts[1:])])


def _from_cubics(chain: Sequence[tuple[Vec2, Vec2, Vec2, Vec2]]) -> Baseline:
    """Sample a contiguous chain of cubics into one arclength table.

    Each cubic is sampled by its control polygon's length rather than by a
    fixed count, so a long sweeping segment and the 0.2mm join next to it are
    both resolved to the same 0.05mm and neither costs more than it is worth.
    """
    if not chain:
        raise ValueError("a baseline needs at least one segment")
    points: list[Vec2] = []
    tangents: list[Vec2] = []
    lengths: list[float] = [0.0]
    for p0, c1, c2, p3 in chain:
        rough = ((c1 - p0).length + (c2 - c1).length + (p3 - c2).length)
        steps = _sample_count(rough)
        first = not points
        for i in range(0 if first else 1, steps + 1):
            t = i / steps
            point = _cubic(p0, c1, c2, p3, t)
            if points:
                lengths.append(lengths[-1] + (point - points[-1]).length)
            points.append(point)
            tangents.append(_cubic_tangent(p0, c1, c2, p3, t))
    if lengths[-1] <= _EPS:
        raise ValueError("a baseline of zero length has nothing to set type on")
    return Baseline(tuple(points), tuple(tangents), tuple(lengths))


def _cubic(p0: Vec2, c1: Vec2, c2: Vec2, p3: Vec2, t: float) -> Vec2:
    u = 1.0 - t
    return (p0 * (u * u * u) + c1 * (3 * u * u * t)
            + c2 * (3 * u * t * t) + p3 * (t * t * t))


def _cubic_tangent(p0: Vec2, c1: Vec2, c2: Vec2, p3: Vec2, t: float) -> Vec2:
    """The unit derivative, with the two degeneracies a chord-cubic produces.

    A straight segment written as a cubic has coincident control points at its
    ends, so the derivative vanishes exactly at t=0 or t=1 and the direction
    has to come from the chord instead.
    """
    u = 1.0 - t
    d = ((c1 - p0) * (3 * u * u) + (c2 - c1) * (6 * u * t) + (p3 - c2) * (3 * t * t))
    if d.length > _EPS:
        return d.normalized()
    chord = p3 - p0
    return chord.normalized() if chord.length > _EPS else Vec2(1.0, 0.0)


# -- the shaped run, cluster by cluster ------------------------------------


@dataclass(frozen=True, slots=True)
class _Cluster:
    """One shaping cluster of the run: what to draw, how wide, and in what."""

    text: str
    advance: float          # mm, including any justification slack it earned
    offset: float           # mm from the start of the run to its left edge
    index: int              # how many inter-cluster gaps precede it
    face: FontFace
    size: float
    shift: float            # sub/superscript baseline shift, mm, down positive
    fill: str | None


def _clusters(prim: TextPrim) -> list[_Cluster]:
    """The block's single line, split at shaping clusters.

    Cluster rather than glyph, because a mark has to travel with the letter it
    sits on: placing a combining acute at its own station and its own tangent
    walks it off the vowel. A ligature is the same argument the other way --
    `fi` is one drawing and gets one station.
    """
    line = prim.lines[0]
    face = load_face(prim.font_path)
    otf = feature_key(dict(getattr(prim, "features", ())))
    out: list[_Cluster] = []
    pen = 0.0
    for text, run_face, size, shift, fill in _spans(line, face, prim.font_size):
        if not text:
            continue
        scale = run_face.scale(size)
        buffer = shape_buffer(text, run_face, otf)
        for chars, advance in _cluster_spans(buffer, text).values():
            width = advance * scale
            # Justification slack belongs to the space it was given to, exactly
            # as it does in `render.glyphs`: banked to the end of the run it
            # would open one hole per markup boundary.
            if line.word_spacing and chars == " ":
                width += line.word_spacing
            out.append(_Cluster(text=chars, advance=width, offset=pen,
                                index=len(out), face=run_face, size=size,
                                shift=shift, fill=fill))
            pen += width
    return out


def _cluster_spans(buffer, text: str) -> dict[int, tuple[str, float]]:
    """`{cluster: (characters, advance in font units)}`, in visual order.

    Cluster values index the run's own string and are monotonic in whichever
    direction the run ran, so the characters a value covers end at the next
    value in sorted order -- which is how this stays correct for a
    right-to-left run without being told. Python dicts keep insertion order,
    so iterating the result walks the clusters the way they will be drawn.
    """
    bounds = sorted({info.cluster for info in buffer.glyph_infos})
    ends = {start: (bounds[i + 1] if i + 1 < len(bounds) else len(text))
            for i, start in enumerate(bounds)}
    out: dict[int, tuple[str, float]] = {}
    for info, position in zip(buffer.glyph_infos, buffer.glyph_positions):
        chars, advance = out.get(info.cluster, ("", 0.0))
        if not chars:
            chars = text[info.cluster:ends[info.cluster]]
        out[info.cluster] = (chars, advance + position.x_advance)
    return out


def _spans(line: TextLine, face: FontFace,
           size: float) -> list[tuple[str, FontFace, float, float, str | None]]:
    """The line as (text, face, size, baseline shift, fill) -- one span unless a
    font was borrowed, a sub/superscript was set or a run was recoloured."""
    if not line.runs:
        return [(line.text, face, size, 0.0, None)]
    return [(run.text,
             load_face(run.font_path, run.font_index) if run.font_path else face,
             size if run.size is None else run.size, run.shift,
             getattr(run, "fill", None))
            for run in line.runs]


# -- placing it ------------------------------------------------------------


def text_on_path(content: object, along: object, *, align: str = "center",
                 start_offset: float = 0.0, lift: float = 0.0,
                 side: str = "above", flip: bool = True,
                 overflow: str = "extend", spacing: float = 0.0,
                 pivot: float | None = None,
                 kind: str = ONPATH_KIND) -> Diagram:
    """Set an already-shaped block along a curve, one cluster per station.

    `content` is a text node (`inklet.text(...)`, `inklet.label(...)`) or the
    `TextPrim` inside one; `along` is a `Baseline` or anything `baseline()`
    accepts, including the very node the figure draws the curve with. The
    block must be a single line: a curve has one baseline, and stacking a
    second one along it would need an offset curve nobody asked for.

    `align` puts the run at the `"start"`, `"center"` or `"end"` of the curve
    and `start_offset` slides it that many millimetres further along, spelled
    the way SVG's `textPath` spells the same quantity. `spacing` adds
    millimetres between clusters, which is the tracking a tight curve wants.

    `side` says which side of the curve the ink goes, and `lift` how far
    clear. `"above"` is the classic setting -- the baseline *is* the curve, so
    the body stands off it and the descenders cross it -- and `"below"` drops
    the block by its own ascent so it hangs under the curve instead, reading
    exactly the same way up. Both are measured from the direction the letters
    finally run, so `flip` cannot turn a label out from under the line it
    belongs to. `lift` adds millimetres of clearance on top, away from the
    curve: type set on a curve the figure also *draws* wants about a quarter
    of its size, or `inklet.lint` reports -- correctly -- that the stroke runs
    through the letters.

    `flip=True`, the default, turns the whole run over when the tangent at its
    midpoint points leftward, so a label on the far side of a circle reads the
    right way up instead of upside-down. It is the run that flips, not the
    letters: half a word the right way up and half of it inverted is not a
    thing anyone wants. Pass `flip=False` for the badge convention, where the
    bottom of the ring is deliberately set inverted.

    `overflow` decides what happens when the run is longer than the curve.
    `"extend"` continues straight along the exit tangent, which is what was
    picked by rendering both: a label that overruns by a letter and a half
    stays readable and visibly overruns, and the author can see what to
    shorten. `"raise"` refuses instead, for a caller generating labels
    programmatically that would rather fail than ship a figure with type
    hanging off the end of an axis.

    `pivot` is the height above the baseline that each cluster turns about,
    and the answer to the pinch a tight curve puts on the inside of the
    letters. Default (`None`) is half the cap height of the block's face,
    which was picked by measuring: setting "Hamburgefons" at 2.4mm round a
    5mm circle with the letters facing inward closes the tightest gap between
    two outlines from 0.239mm straight to 0.006mm -- touching ink -- and
    pivoting at mid-cap reopens it to 0.193mm. Across r=5mm and r=20mm, inward
    and outward, the worst case improves 4.7x and the spread of gaps narrows
    from 13%-140% of the straight-line gap to 61%-104%. Pass `pivot=0` for the
    naive placement (each cluster turned about its own baseline), or a length
    in millimetres to turn about some other height. A straight curve is
    unaffected either way: its parallel has the same length and the same
    stations. Stations are walked along the curve *at pivot height*, which is
    also the length the overflow test uses -- the room the letters actually
    have, which on the outside of a bend is more than the baseline's own.

    Returns a group of the placed clusters; see the module docstring for what
    that group is and why it is not one node.
    """
    if overflow not in OVERFLOW_MODES:
        raise ValueError(
            f"unknown overflow mode {overflow!r}; expected one of "
            f"{', '.join(OVERFLOW_MODES)}")
    if side not in ("above", "below"):
        raise ValueError(f"side must be 'above' or 'below', got {side!r}")
    if align not in ("start", "center", "end"):
        raise ValueError(
            f"align must be 'start', 'center' or 'end', got {align!r}")

    prim, style = _text_of(content)
    curve = baseline(along)
    clusters = _clusters(prim)
    if not clusters:
        return Diagram(kind=kind, style=style)

    run = _run_length(clusters, spacing)
    # Which way the letters run is settled first, on the curve as it was
    # given, because everything after it -- which side of the curve is "below",
    # which way the pivot offset goes -- is measured from the direction of
    # travel. `turned` remembers it so the run still lands on the piece of the
    # curve `align` asked for and not on the mirror image of it.
    probe = _run_start(align, start_offset, run, curve.length)
    turned = flip and _reads_backwards(curve, probe + run / 2)
    if turned:
        curve = curve.reversed()
    clear = (prim.ascent + lift) if side == "below" else -lift
    if clear:
        curve = curve.offset(clear)

    high = _pivot_height(prim, pivot)
    walk = _walk(curve, high)
    start = _run_start(align, start_offset, run, walk.length)
    if turned:
        start = walk.length - (start + run)
    if overflow == "raise" and (start < -1e-9 or start + run > walk.length + 1e-9):
        raise ValueError(
            f"{prim.text!r} sets {run:.2f}mm of type on a {walk.length:.2f}mm "
            f"curve at align={align!r}, start_offset={start_offset}: it would "
            f"overhang by "
            f"{max(-start, start + run - walk.length):.2f}mm. Shorten the "
            f"string, lengthen the curve, or pass overflow='extend'.")

    children = tuple(_placed(cluster, walk, start, spacing, prim, high)
                     for cluster in clusters)
    group = Diagram(children=children, kind=kind, style=style)
    group.anchor(_ORIGIN_ANCHOR, _authors_origin(along))
    return group.note(TEXT_NOTE, prim.text)


def text_on_arc(content: object, radius: float, angle: float, *,
                side: str = "outside", gap: float = 0.0, centre: object = ORIGIN,
                sweep: str = "cw", flip: bool = True, spacing: float = 0.0,
                pivot: float | None = None,
                kind: str = ONPATH_KIND) -> Diagram:
    """Set a block around a circle, centred on the bearing `angle`.

    The convenience the polar plots wanted, and the one call where `side` is
    named for the circle rather than for the direction of travel: `"outside"`
    keeps the block's ink clear of `radius` on the far side from `centre` and
    `"inside"` keeps it clear on the near side, in both cases by `gap`
    millimetres. The baseline circle is worked out from the block's own ascent
    and descent, so a ring of labels sits on one line whether or not a
    particular one has an ascender -- and so that a label the flip turns over
    stays on the side of `radius` it was asked for.

    `angle` is a bearing in the library's degrees: 0 due east, 90 due south on
    the page, increasing clockwise. `sweep="cw"` runs the letters clockwise and
    `"ccw"` anticlockwise; `flip` then overrides either when the result would
    read upside-down, which is what makes a whole ring of theta labels legible
    without the caller working out which half of the circle each is on.
    """
    if side not in ("outside", "inside"):
        raise ValueError(f"side must be 'outside' or 'inside', got {side!r}")
    if sweep not in ("cw", "ccw"):
        raise ValueError(f"sweep must be 'cw' or 'ccw', got {sweep!r}")

    prim, _ = _text_of(content)
    # Which way the letters finally run is settled here and not left to
    # `text_on_path`'s own flip test: the baseline circle depends on it, and
    # two tests of the same question that disagree by a floating-point hair at
    # due east would put one label of a ring on the wrong radius.
    asked_ccw = sweep == "ccw"
    ccw = asked_ccw != (flip and _bearing_reads_backwards(angle, asked_ccw))
    outward = not ccw                            # letters stand away from centre
    if side == "outside":
        r = radius + gap + (prim.descent if outward else prim.ascent)
    else:
        r = radius - gap - (prim.ascent if outward else prim.descent)
    if r <= 0:
        raise ValueError(
            f"a {prim.height:.2f}mm block set {side} a {radius}mm circle with "
            f"gap={gap} needs a baseline at r={r:.2f}mm, which is not a circle")
    # Half a turn either side of the bearing: more curve than a label can use,
    # and centred so that `align="center"` lands the run's middle on `angle`.
    curve = (baseline_arc(r, angle + 180.0, angle - 180.0, centre) if ccw else
             baseline_arc(r, angle - 180.0, angle + 180.0, centre))
    return text_on_path(content, curve, align="center", side="above",
                        flip=False, spacing=spacing, pivot=pivot, kind=kind)


def _bearing_reads_backwards(angle: float, turned: bool) -> bool:
    """Whether a run centred on this bearing would read right-to-left.

    Sweeping clockwise, the tangent at bearing a is (-sin a, cos a), so the run
    reads leftward exactly where sin a is positive -- the lower half of the
    page, y growing downward. Anticlockwise is the other half. Due east and
    due west read forwards either way, which is why the test is strict.
    """
    slope = math.sin(math.radians(angle))
    return slope < 0.0 if turned else slope > 0.0


def _authors_origin(along: object) -> Vec2:
    """Where the author's (0, 0) sits in the frame the run was placed in.

    The curve's own answer when it has one, and (0, 0) otherwise -- a
    `Baseline` built from `baseline_arc` or from typed points is already in the
    author's coordinates, and an anchor on the origin makes `as_drawn` a no-op,
    which is what "already in the right frame" means.
    """
    anchors = getattr(along, "anchors", None)
    if anchors and _ORIGIN_ANCHOR in anchors:
        return getattr(along, "transform", IDENTITY).apply(anchors[_ORIGIN_ANCHOR])
    return ORIGIN


def _pivot_height(block: TextPrim, pivot: float | None) -> float:
    """How far above the baseline the clusters turn, in millimetres.

    Half the cap height by default, read off the block's own face: it is the
    middle of the body of ordinary text, so the two halves of the pinch -- ink
    crowding below the pivot on the inside of a bend, opening above it -- come
    out the same size instead of all landing on one side. An explicit value
    wins, including zero, which is the naive baseline-pivot placement.
    """
    if pivot is not None:
        return float(pivot)
    face = load_face(block.font_path, getattr(block, "font_index", 0) or 0)
    return face.cap_height * face.scale(block.font_size) / 2


def _walk(curve: Baseline, lift: float) -> Baseline:
    """`curve` raised `lift` mm toward the letters, or `curve` if that folds.

    The parallel curve on the side the type stands on -- left of the direction
    of travel, which is what `side` has already arranged. A curve bending
    tighter than `lift` has no parallel at that distance: the offset turns
    itself inside out and the run would set backwards through the cusp. That
    is a 0.9mm radius under 2.4mm type, small enough that the label was never
    going to be legible, so this degrades to the uncompensated placement
    rather than refusing a figure over it.
    """
    if abs(lift) <= _EPS:
        return curve
    walk = curve.offset(-lift)
    for a, b, t in zip(walk.points, walk.points[1:], walk.tangents):
        if (b - a).dot(t) < 0.0:
            return curve
    return walk


def _reads_backwards(curve: Baseline, station: float) -> bool:
    """Whether the run's midpoint tangent points leftward on the page.

    The midpoint and not the mean: a run that crosses the top of a circle has
    tangents pointing both ways and their mean says nothing, while the letter
    in the middle of the word is exactly the one a reader's eye starts on.
    """
    return curve.at(station)[1].x < 0.0


def _run_length(clusters: Sequence[_Cluster], spacing: float) -> float:
    return (sum(c.advance for c in clusters)
            + spacing * max(0, len(clusters) - 1))


def _run_start(align: str, start_offset: float, run: float,
               length: float) -> float:
    base = {"start": 0.0, "center": (length - run) / 2, "end": length - run}[align]
    return base + start_offset


def _placed(cluster: _Cluster, walk: Baseline, start: float,
            spacing: float, block: TextPrim, lift: float) -> Diagram:
    """One cluster as a live text node, turned to the tangent under its middle.

    The station is the *middle* of the cluster's own advance rather than its
    left edge, which is the difference between a curved word whose letters lean
    consistently and one that creeps outward across the run: pinned at the left
    edge, every letter is rotated about a point up to an advance behind where
    its ink actually is.

    `walk` is the curve at pivot height and `lift` is how far above the
    baseline that is, so the turn happens about the middle of the letter and
    the baseline lands back on the curve the caller asked for.
    """
    station = (start + cluster.offset + spacing * cluster.index
               + cluster.advance / 2)
    point, tangent = walk.at(station)
    prim = _cluster_prim(cluster, block)
    inner = Affine.translation(0.0, cluster.shift - prim.first_baseline + lift)
    turn = Affine(a=tangent.x, b=tangent.y, c=-tangent.y, d=tangent.x,
                  e=point.x, f=point.y)
    node = Diagram(prim=prim, kind=CLUSTER_KIND, transform=turn @ inner)
    return node.styled(fill=cluster.fill) if cluster.fill else node


def _cluster_prim(cluster: _Cluster, block: TextPrim) -> TextPrim:
    """A one-cluster block, measured exactly as the run it came out of.

    Its advance is the advance the shaper gave those characters *in context*,
    so the placement arithmetic never depends on what a viewer would make of
    the cluster on its own -- and a viewer that reshapes it (which is what
    live text means) draws the same glyphs, because a cluster is by definition
    the smallest run that shapes independently.
    """
    ascent, descent, _ = cluster.face.metrics(cluster.size)
    return TextPrim(
        lines=(TextLine(text=cluster.text, advance=cluster.advance, baseline=0.0),),
        font_family=cluster.face.family,
        font_size=cluster.size,
        ascent=ascent,
        descent=descent,
        align="start",
        font_path=cluster.face.path,
        requested_family=block.requested_family,
        features=getattr(block, "features", ()),
    )


def _text_of(content: object) -> tuple[TextPrim, Style]:
    """The shaped block inside whatever the caller passed, and its style."""
    if isinstance(content, TextPrim):
        prim, style = content, EMPTY_STYLE
    elif isinstance(content, Diagram) and isinstance(content.prim, TextPrim):
        prim, style = content.prim, content.style
    else:
        raise TypeError(
            "text_on_path takes a shaped text block -- inklet.text(...), "
            f"inklet.label(...) or the TextPrim inside one -- not "
            f"{type(content).__name__}")
    if prim.font_path is None:
        raise ValueError(
            "cannot set a TextPrim with no font_path on a path; build it with "
            "inklet.text() or inklet.typeset.shape()")
    if len(prim.lines) > 1:
        raise ValueError(
            f"a curve has one baseline, and {prim.text!r} has "
            f"{len(prim.lines)} lines; set each line on its own curve")
    return prim, style
