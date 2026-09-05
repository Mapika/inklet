"""Converting shaped text to filled outlines.

The SVG backend keeps text as text; PDF, and any SVG that has to leave this
machine, needs glyphs as geometry so the output does not depend on a font being
installed. This re-runs the shaper over the already-broken lines and walks each
glyph with a fontTools pen, so the outlines land exactly where the measured
advances said they would.

Contours are cached per (face, glyph id) in the font's own units, which is what
makes outlining a whole figure affordable: a caption reuses the same twenty
letters over and over, and a page of them is one pen walk each rather than one
per occurrence.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from fontTools.pens.basePen import BasePen
from fontTools.ttLib import TTFont

from ..core.geom import Vec2
from ..core.prims import PathPrim, Subpath, TextPrim
from .fonts import FontFace, load_face
from .shaping import shape_buffer

__all__ = ["Contour", "glyph_contours", "placed_contours", "text_to_paths",
           "TEXT_NOTE"]

#: The note an outlined block keeps its own words on, written by
#: `render.outline_text` and read by `diagnostics.rules.Item.described`.
#:
#: Outlining is the one transform in the library that destroys something a
#: *reader* wants. The glyphs survive as geometry, but nothing in the tree
#: spells them any more, so a finding about an outlined block could name it and
#: not quote it -- `OFF_CANVAS legend-note` where the live block says
#: `legend-note 'Mean response'`. A two-colour block is the sharp case: it
#: keeps no primitive at all, only a `glyphs` child per colour, so there is not
#: even a shrunken `TextPrim` left to excerpt. One string per block is the
#: whole cost. The name lives here rather than in `render` because it names
#: what the shaper produced, and because a diagnostic reading it must not have
#: to import a backend.
TEXT_NOTE = "text"

# Samples per cubic for the flattened `points` list. The exact control points
# survive in `Subpath.curves`, so this only sets the resolution of the geometry
# queries (envelope, ray hits), not of the drawn curve.
_FLATTEN_STEPS = 8


def text_to_paths(prim: TextPrim) -> list[tuple[PathPrim, str | None]]:
    """Outline a shaped text block in its own local frame, one path per colour.

    Returns `(path, fill)` pairs in the order the fills first appear, where
    `fill` is None for the glyphs that take the text node's own colour. A block
    with no `{fill|text}` markup in it — which is nearly every block — comes
    back as exactly one pair, `[(path, None)]`, and an empty one (no lines, or
    only whitespace) as `[]`.

    One `PathPrim` carries one colour, so a recoloured run needs a path of its
    own; the glyphs of two different fills never overlap, so collecting each
    fill's ink into a single path costs nothing and keeps the common case a
    single node. The SVG and PDF backends do not come through here at all --
    `render.glyphs` places the same cached contours and keeps the fill per
    glyph -- so this is the tree transform's route, `inklet.outline_text`.

    Outlining re-runs the shaper over the already-broken lines, so it has to
    ask under the same OpenType features the advances were measured with. It
    takes them off the prim (`TextPrim.features`, contract M13) rather than
    from a parameter, because a parameter is a second place to get it right:
    ten digits shaped with `tnum` measure 58.00mm and outline 54.24mm without.

    Raises ValueError if the prim has no `font_path` (it was not produced by
    `inklet.typeset.shape`), and FontNotFoundError if that path is no longer readable.
    """
    if not prim.lines:
        return []
    if prim.font_path is None:
        raise ValueError(
            "cannot outline a TextPrim with no font_path; build it with inklet.typeset.shape()"
        )

    # TextPrim carries no collection index, so a .ttc always outlines face 0.
    face = load_face(prim.font_path)
    otf = tuple(getattr(prim, "features", ()))

    # A line whose script the named font cannot draw was shaped in a borrowed
    # face, and outlining it here in the named one would put .notdef boxes
    # where the SVG backend puts readable glyphs. Each run is outlined in the
    # face it was measured in, so both backends draw the same figure.
    groups: dict[str | None, list[Subpath]] = {}
    for line in prim.lines:
        if not line.text:
            continue
        pen_x = -prim.width / 2 + prim.line_offset(line)
        pen_y = prim.first_baseline + line.baseline
        for text, run_face, run_size, run_shift, run_fill in _spans(
                line, face, prim.font_size):
            if not text:
                continue
            scale = run_face.scale(run_size)
            subpaths = groups.setdefault(run_fill, [])
            buffer = shape_buffer(text, run_face, otf)
            for info, position in zip(buffer.glyph_infos, buffer.glyph_positions):
                origin = Vec2(pen_x + position.x_offset * scale,
                              pen_y + run_shift - position.y_offset * scale)
                subpaths.extend(placed_contours(run_face.path, run_face.index,
                                                info.codepoint, origin, scale))
                pen_x += position.x_advance * scale
                pen_y -= position.y_advance * scale
                # A justified line's slack belongs to each space in turn, not
                # to the end of the span that holds them: paid at the end, a
                # line reading "...and anode." followed by a bold "(b)" opens a
                # five-space hole in front of the (b) and sets the words behind
                # it solid. Clusters are indices into the run's own string, so
                # this asks the character, not the glyph, whether it is a space.
                if line.word_spacing and text[info.cluster] == " ":
                    pen_x += line.word_spacing

    return [(PathPrim(tuple(subpaths), filled=True), fill)
            for fill, subpaths in groups.items() if subpaths]


def _spans(line, face: FontFace,
           size: float) -> list[tuple[str, FontFace, float, float, str | None]]:
    """The line as (text, face, size, baseline shift, fill) -- one span unless a
    font was borrowed, a sub/superscript was set or a span was recoloured."""
    if not line.runs:
        return [(line.text, face, size, 0.0, None)]
    return [(run.text,
             load_face(run.font_path, run.font_index) if run.font_path else face,
             size if run.size is None else run.size, run.shift,
             getattr(run, "fill", None))
            for run in line.runs]


# -- one glyph, in font units ---------------------------------------------


@dataclass(frozen=True, slots=True)
class Contour:
    """One closed glyph contour in font units, y up, origin on the baseline.

    `points` is the flattened polygon and `curves` the exact cubics, each as
    eight floats; `curves` is empty for a contour with no curve in it, which is
    how a straight-sided glyph stays a polyline instead of a run of degenerate
    beziers.
    """

    points: tuple[tuple[float, float], ...]
    curves: tuple[tuple[float, ...], ...]


def _place(contour: Contour, origin: Vec2, scale: float) -> Subpath:
    """A cached contour in a glyph's place. Font space has y up and inklet has y
    down, so the sign of y flips here and nowhere else."""
    x0, y0 = origin.x, origin.y
    points = tuple(Vec2(x0 + x * scale, y0 - y * scale) for x, y in contour.points)
    curves = tuple(
        (Vec2(x0 + c[0] * scale, y0 - c[1] * scale),
         Vec2(x0 + c[2] * scale, y0 - c[3] * scale),
         Vec2(x0 + c[4] * scale, y0 - c[5] * scale),
         Vec2(x0 + c[6] * scale, y0 - c[7] * scale))
        for c in contour.curves
    )
    return Subpath(points, closed=True, curves=curves)


@lru_cache(maxsize=4096)
def glyph_contours(path: str, index: int, gid: int) -> tuple[Contour, ...]:
    """The contours of one glyph, in font units. Cached: a figure asks for the
    same letter hundreds of times and a pen walk is not free.

    Public so that both outlining backends share one cache. `render.glyphs`
    places glyphs one at a time to keep a per-glyph fill; this module builds
    one path per block. Two caches would mean walking the same alphabet twice.
    """
    glyph_set, glyph_order = _glyph_source(path, index)
    pen = _ContourPen(glyph_set)
    glyph_set[glyph_order[gid]].draw(pen)
    return tuple(pen.contours)


def placed_contours(path: str, index: int, gid: int,
                    origin: Vec2, scale: float) -> list[Subpath]:
    """One glyph's contours, in millimetres, at `origin`.

    `origin` is the glyph's own pen position -- the baseline point the shaper
    placed it at, in the text block's local frame -- and `scale` converts the
    face's units to mm (`FontFace.scale(size)`). This is `glyph_contours`
    followed by the y flip and nothing else, so a caller that has already done
    the shaping arithmetic gets geometry it can hand straight to a `PathPrim`.
    """
    return [_place(contour, origin, scale)
            for contour in glyph_contours(path, index, gid)]


@lru_cache(maxsize=8)
def _glyph_source(path: str, index: int):
    """A font's glyph set, held open.

    The file handle stays open for the life of the process, exactly as
    `shaping._hb_font` keeps its HarfBuzz face open: reopening and re-parsing a
    30 MB CJK collection per glyph is the whole cost of outlining. The cache is
    small because a figure sets its text in one or two faces.
    """
    font = TTFont(path, lazy=True, fontNumber=index)
    return font.getGlyphSet(), font.getGlyphOrder()


class _ContourPen(BasePen):
    """Collects one glyph's contours in font units.

    Implements the fontTools pen protocol, which is why this is a class.
    BasePen decomposes TrueType quadratics into cubics before they reach
    `_curveToOne`, so both outline flavours land here as cubics.

    Straight segments of a contour that also curves are recorded as degenerate
    cubics, because `Subpath.curves` is all-or-nothing: a renderer draws from
    it alone when it is non-empty, so a list holding only the round parts of a
    `b` loses the stem. A contour with no curve at all keeps an empty `curves`
    and stays a polyline, which is both shorter and what it is.
    """

    def __init__(self, glyph_set):
        super().__init__(glyph_set)
        self._points: list[tuple[float, float]] = []
        self._segments: list[tuple[float, ...]] = []
        self._curved = False
        self.contours: list[Contour] = []

    def _moveTo(self, point) -> None:
        self._flush()
        self._points = [(point[0], point[1])]

    def _lineTo(self, point) -> None:
        start = self._points[-1]
        end = (point[0], point[1])
        self._points.append(end)
        self._segments.append((*start, *start, *end, *end))

    def _curveToOne(self, control1, control2, end) -> None:
        self._curved = True
        start = self._points[-1]
        c1, c2, last = tuple(control1), tuple(control2), tuple(end)
        self._segments.append((*start, *c1, *c2, *last))
        for step in range(1, _FLATTEN_STEPS + 1):
            self._points.append(_cubic_at(start, c1, c2, last, step / _FLATTEN_STEPS))

    def _closePath(self) -> None:
        self._flush()

    def _endPath(self) -> None:
        self._flush()

    def _flush(self) -> None:
        """Emit the contour under construction. Glyph contours are always closed,
        including the open-ended ones an `_endPath` would report, so the segment
        back to the start is left implicit."""
        if len(self._points) >= 2:
            self.contours.append(Contour(
                tuple(self._points),
                tuple(self._segments) if self._curved else (),
            ))
        self._points = []
        self._segments = []
        self._curved = False


def _cubic_at(p0, c1, c2, p3, t: float) -> tuple[float, float]:
    u = 1.0 - t
    a, b, c, d = u * u * u, 3 * u * u * t, 3 * u * t * t, t * t * t
    return (p0[0] * a + c1[0] * b + c2[0] * c + p3[0] * d,
            p0[1] * a + c1[1] * b + c2[1] * c + p3[1] * d)
