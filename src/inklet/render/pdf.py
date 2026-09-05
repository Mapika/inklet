"""PDF output for `inklet`.

Where SVG mirrors the tree so a designer can keep editing it, PDF is the
*shipping* format: what a journal wants attached to the submission and what a
printer imposes. Nothing downstream of it will be restyled, so this backend
takes the opposite decisions all the way down. It walks `core.flatten()` rather
than the tree, because a PDF content stream has no grouping worth the name; and
it outlines every glyph, because embedding a font subset would trade a solved
problem -- geometry that draws identically anywhere -- for a smaller file and a
new class of failure. `inklet.render.outline` is the same machinery the SVG
`text="outline"` mode uses, so the two backends draw the same figure.

The writer is deliberately dependency-free: a PDF is a handful of dictionaries,
one content stream and a cross-reference table, and pulling in a rendering
library to emit that would be worse than writing it. Pillow is needed only to
decode a PNG that a figure actually places, and the error says so.

Units: `inklet` works in millimetres and PDF in points, so one `cm` at the top of
the stream sets 1 user unit = 1 mm and flips y, and every number after it is a
millimetre. Stroke widths and dashes therefore need no conversion, which is the
same reason the SVG backend uses a millimetre viewBox.

Determinism: no creation date, no producer version drift, object numbers
allocated in walk order, and the file `/ID` is a hash of the page's own bytes.
The same tree renders byte-identically every time.
"""

from __future__ import annotations

import hashlib
import zlib
from io import BytesIO
from pathlib import Path
from typing import Sequence

from ..core.diagram import Diagram, DiagramError
from ..core.geom import IDENTITY, Affine, Rect, Vec2
from ..core.prims import (
    EllipsePrim, ImagePrim, PathPrim, PhantomPrim, Prim, RectPrim, Subpath,
    TextPrim,
)
from ..core.style import EMPTY_STYLE, Style
from ..core.units import mm as to_mm
from ..themes.color import parse_color
from .glyphs import PlacedGlyph, placed_glyphs, to_path
from .pdftext import FontShelf, show_text, text_runs, to_unicode_cmap, widths_array

__all__ = ["to_pdf", "save_pdf", "PDF_TEXT_MODES"]

#: What `to_pdf(text=)` accepts, a subset of `render.TEXT_MODES`. `"names"` --
#: the SVG default, a font-family chain resolved by whatever opens the file --
#: has no PDF spelling worth having: the only faces a reader is required to
#: have are the base 14, and none of them is one `inklet` would have measured
#: against.
PDF_TEXT_MODES = ("outline", "embed")

#: PostScript points per millimetre. The one unit conversion in the file.
PT_PER_MM = 72.0 / 25.4

# The magic number for a circular arc as four cubics: the control points sit
# this fraction of the radius along the tangents.
_KAPPA = 0.5522847498307936

_JOIN_EPS = 1e-9

# SVG's initial values, because matching the SVG render is the specification
# for this backend. PDF's own defaults differ -- notably a miter limit of 10.
_DEFAULT_FILL = "#000000"
from .paint import MITER_LIMIT as _MITER_LIMIT
#: What a halo is painted in when neither the style nor the page says.
DEFAULT_PAPER = "#ffffff"

# Decimals for the page matrix and the MediaBox, which are in points rather
# than millimetres and so are not the caller's `precision` to set.
_PAGE_PRECISION = 6

_CAPS = {"butt": 0, "round": 1, "square": 2}
_JOINS = {"miter": 0, "round": 1, "bevel": 2}


# -- numbers and strings --------------------------------------------------


def _fmt(value: float, precision: int) -> str:
    """Fixed notation, trailing zeros stripped, no negative zero. PDF has no
    exponent syntax at all, so a number that reaches one is a broken file."""
    number = float(value)
    if number != number or number in (float("inf"), float("-inf")):
        raise ValueError(f"cannot render non-finite length {value!r}")
    text = f"{number:.{precision}f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text in ("", "-", "-0") else text


def _pdf_string(text: str) -> str:
    """A PDF text string: ASCII as a literal, anything else as UTF-16BE hex."""
    if text.isascii():
        escaped = text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
        return f"({escaped})"
    return "<FEFF" + text.encode("utf-16-be").hex().upper() + ">"


def _rgb(color: str, precision: int) -> str:
    r, g, b = parse_color(color)
    return " ".join(_fmt(c / 255.0, precision) for c in (r, g, b))


def _paintable(color: str | None) -> bool:
    return color is not None and color != "none"


# -- the content stream ---------------------------------------------------


class _Resources:
    """Everything the pages of one document share by name.

    Alpha states, rasters and transparency groups are all deduplicated across
    every page and every nested group, because the alternative -- one copy of
    a 2 MB micrograph per sheet -- is what makes a multi-page PDF unusable.
    A raster is keyed on the hash of its own bytes rather than on its path, so
    an `ImagePrim` carrying generated `data` (which has no path, only a label)
    is still shared with an identical one, and two different heatmaps that a
    caller happened to give the same label are not confused for each other.
    """

    def __init__(self) -> None:
        self.alphas: dict[tuple[str, str], str] = {}   # (ca, CA) -> /GS name
        self.images: dict[str, tuple[str, ImagePrim]] = {}   # key -> (name, prim)
        self.forms: list[tuple[str, bytes, Rect]] = []       # name, stream, bbox
        self.fonts = FontShelf()                  # only used by text="embed"

    def alpha(self, fill: str, stroke: str) -> str:
        """The `/GS` name for one (fill alpha, stroke alpha) pair.

        Two numbers rather than one because `Style.fill_opacity` and
        `Style.stroke_opacity` can differ -- a confidence band is a 20% fill
        under a solid line -- and `ca`/`CA` is where PDF keeps that. Where they
        are equal, which is every node that only sets `opacity`, the state
        written is the one this backend has always written.
        """
        key = (fill, stroke)
        if key not in self.alphas:
            self.alphas[key] = f"GS{len(self.alphas)}"
        return self.alphas[key]

    def image(self, prim: ImagePrim) -> str:
        data = getattr(prim, "data", None)
        key = (hashlib.md5(data).hexdigest() if data is not None
               else f"path:{prim.source}")
        # The same bytes asked to resample two different ways are two
        # XObjects, because `/Interpolate` lives in the image dictionary.
        key = f"{key}:{getattr(prim, 'smooth', None)!r}"
        got = self.images.get(key)
        if got is None:
            got = self.images[key] = (f"Im{len(self.images)}", prim)
        return got[0]

    def form(self, stream: bytes, box: Rect) -> str:
        name = f"Fm{len(self.forms)}"
        self.forms.append((name, stream, box))
        return name


class _Content:
    """One operator stream -- a page's, or a transparency group's.

    Graphics state is not tracked across items: every drawable is wrapped in
    `q`/`Q` and sets what it needs. That costs a few bytes against a stream
    nobody reads and removes the whole class of bug where one shape's dash
    pattern leaks into the next.
    """

    def __init__(self, precision: int, shared: _Resources, *,
                 text: str = "outline",
                 paper: str = DEFAULT_PAPER) -> None:
        self.precision = precision
        self.ops: list[str] = []
        self.shared = shared
        self.paper = paper
        # Carried on the stream rather than threaded through every emitter:
        # it is a setting of the whole document, and a transparency group's
        # stream has to inherit it unchanged.
        self.text_mode = text

    def child(self) -> "_Content":
        """A separate stream -- a transparency group's -- with the same
        settings and the same shared resources."""
        return _Content(self.precision, self.shared,
                        text=self.text_mode, paper=self.paper)

    def n(self, value: float) -> str:
        return _fmt(value, self.precision)

    def op(self, *parts: str) -> None:
        self.ops.append(" ".join(parts))

    def matrix(self, t: Affine, precision: int | None = None) -> None:
        """`precision` overrides the drawing precision, which the page's own
        matrix needs: rounding 72/25.4 to three decimals scales the whole
        figure by a part in eight thousand, and a scale error is the one kind
        that does not average out."""
        digits = self.precision if precision is None else precision
        self.op(*(_fmt(v, digits) for v in (t.a, t.b, t.c, t.d, t.e, t.f)), "cm")

    def alpha(self, fill: float, stroke: float | None = None) -> str:
        return self.shared.alpha(self.n(fill),
                                 self.n(fill if stroke is None else stroke))

    def image(self, prim: ImagePrim) -> str:
        return self.shared.image(prim)

    def render(self) -> bytes:
        return ("\n".join(self.ops) + "\n").encode("latin-1")


# -- path geometry --------------------------------------------------------


def _move(c: _Content, p: Vec2) -> None:
    c.op(c.n(p.x), c.n(p.y), "m")


def _line(c: _Content, p: Vec2) -> None:
    c.op(c.n(p.x), c.n(p.y), "l")


def _curve(c: _Content, c1: Vec2, c2: Vec2, p: Vec2) -> None:
    c.op(c.n(c1.x), c.n(c1.y), c.n(c2.x), c.n(c2.y), c.n(p.x), c.n(p.y), "c")


def _same(a: Vec2, b: Vec2) -> bool:
    return abs(a.x - b.x) <= _JOIN_EPS and abs(a.y - b.y) <= _JOIN_EPS


def _subpath(c: _Content, sub: Subpath) -> bool:
    """Lay one subpath into the current path. False if there was nothing to lay."""
    if sub.curves:
        start = sub.curves[0][0]
        _move(c, start)
        cursor = start
        for p0, c1, c2, p3 in sub.curves:
            if not _same(p0, cursor):
                _line(c, p0)
            # Glyph contours mix straight and curved segments, and
            # `Subpath.curves` is all-or-nothing, so the straight ones arrive
            # as cubics with their controls on the endpoints. Writing those
            # back out as lines is a third of the numbers for the same ink.
            if _same(c1, p0) and _same(c2, p3):
                _line(c, p3)
            else:
                _curve(c, c1, c2, p3)
            cursor = p3
        if sub.closed:
            c.op("h")
        return True
    if not sub.points:
        return False
    first, *rest = sub.points
    _move(c, first)
    for point in rest:
        _line(c, point)
    if sub.closed:
        c.op("h")
    return True


def _subpaths(c: _Content, subpaths) -> bool:
    """Lay a whole path in. Not `any(...)`: that short-circuits, and a path
    stopping after its first contour is a `T` where the label said "Two-photon"."""
    laid = False
    for sub in subpaths:
        laid = _subpath(c, sub) or laid
    return laid


def _rounded_rect(c: _Content, box: Rect, radius: float) -> None:
    r = min(radius, box.width / 2, box.height / 2)
    k = r * (1.0 - _KAPPA)
    _move(c, Vec2(box.x0 + r, box.y0))
    _line(c, Vec2(box.x1 - r, box.y0))
    _curve(c, Vec2(box.x1 - k, box.y0), Vec2(box.x1, box.y0 + k), Vec2(box.x1, box.y0 + r))
    _line(c, Vec2(box.x1, box.y1 - r))
    _curve(c, Vec2(box.x1, box.y1 - k), Vec2(box.x1 - k, box.y1), Vec2(box.x1 - r, box.y1))
    _line(c, Vec2(box.x0 + r, box.y1))
    _curve(c, Vec2(box.x0 + k, box.y1), Vec2(box.x0, box.y1 - k), Vec2(box.x0, box.y1 - r))
    _line(c, Vec2(box.x0, box.y0 + r))
    _curve(c, Vec2(box.x0, box.y0 + k), Vec2(box.x0 + k, box.y0), Vec2(box.x0 + r, box.y0))
    c.op("h")


def _ellipse(c: _Content, rx: float, ry: float) -> None:
    ox, oy = rx * _KAPPA, ry * _KAPPA
    _move(c, Vec2(rx, 0.0))
    _curve(c, Vec2(rx, oy), Vec2(ox, ry), Vec2(0.0, ry))
    _curve(c, Vec2(-ox, ry), Vec2(-rx, oy), Vec2(-rx, 0.0))
    _curve(c, Vec2(-rx, -oy), Vec2(-ox, -ry), Vec2(0.0, -ry))
    _curve(c, Vec2(ox, -ry), Vec2(rx, -oy), Vec2(rx, 0.0))
    c.op("h")


# -- painting -------------------------------------------------------------


def _paint(c: _Content, style: Style, *, fill: str | None, stroke: str | None,
           rule: str = "nonzero") -> None:
    """Set the colours and stroke state, then choose the painting operator."""
    filling, stroking = _paintable(fill), _paintable(stroke)
    if not filling and not stroking:
        c.op("n")               # a path with no paint still has to be consumed
        return
    if filling:
        c.op(_rgb(fill, c.precision), "rg")
    if stroking:
        c.op(_rgb(stroke, c.precision), "RG")
        c.op(c.n(1.0 if style.stroke_width is None else style.stroke_width), "w")
        if style.stroke_dash:
            pattern = " ".join(c.n(v) for v in style.stroke_dash)
            c.op(f"[{pattern}]", "0", "d")
        if style.stroke_linecap:
            c.op(str(_CAPS.get(style.stroke_linecap, 0)), "J")
        if style.stroke_linejoin:
            c.op(str(_JOINS.get(style.stroke_linejoin, 0)), "j")
    # The starred operators are the same paints under the even-odd rule, which
    # is the whole of `PathPrim.fill_rule` on this side.
    star = "*" if filling and rule == "evenodd" else ""
    c.op(("B" + star) if filling and stroking
         else (("f" + star) if filling else "S"))


def _draw_prim(c: _Content, prim: Prim, style: Style) -> None:
    fill = _DEFAULT_FILL if style.fill is None else style.fill

    if isinstance(prim, RectPrim):
        radius = prim.radius if prim.radius > 0 else (style.corner_radius or 0.0)
        box = Rect.from_size(prim.width, prim.height)
        if radius > 0:
            _rounded_rect(c, box, radius)
        else:
            c.op(c.n(box.x0), c.n(box.y0), c.n(prim.width), c.n(prim.height), "re")
        _paint(c, style, fill=fill, stroke=style.stroke)

    elif isinstance(prim, EllipsePrim):
        _ellipse(c, prim.rx, prim.ry)
        _paint(c, style, fill=fill, stroke=style.stroke)

    elif isinstance(prim, PathPrim):
        if _subpaths(c, prim.subpaths):
            _paint(c, style, fill=fill if prim.filled else None,
                   stroke=style.stroke,
                   rule=getattr(prim, "fill_rule", "nonzero"))

    elif isinstance(prim, TextPrim):
        # Glyphs are filled and never stroked, exactly as the SVG backend
        # pins `stroke="none"` on `<text>`: a label inside a group that
        # strokes its shapes would otherwise come out as a fake bold.
        ink = style.text_fill if style.text_fill is not None else fill
        glyphs = placed_glyphs(prim)
        _draw_halo(c, glyphs, style)
        if c.text_mode == "embed":
            _draw_text_live(c, glyphs, style, ink)
        else:
            _draw_text_outlined(c, glyphs, style, ink)

    elif isinstance(prim, ImagePrim):
        _draw_image(c, prim)

    elif not isinstance(prim, PhantomPrim):
        raise NotImplementedError(
            f"the PDF backend cannot draw a {type(prim).__name__}")


def _draw_halo(c: _Content, glyphs: list[PlacedGlyph], style: Style) -> None:
    """The paper-coloured stroke that goes under a label, when one was asked for.

    Always geometry, never a stroked text object, and always the whole block in
    one path -- both for the same reason. `Tr 1` would put the halo in a second
    text object, so the words would extract twice; and stroking glyph by glyph
    would let each letter's halo bite into the ink of the one before it. One
    merged path stroked once has neither problem, and the fill pass on top is
    then free to be live text.
    """
    width = getattr(style, "halo", None)
    if not width or width <= 0:
        return
    paths = to_path(glyphs)
    if paths is None or not _subpaths(c, paths.subpaths):
        return
    colour = getattr(style, "halo_color", None) or c.paper
    c.op(_rgb(colour, c.precision), "RG")
    c.op(c.n(width), "w")
    # Round, as in the SVG backend: a miter on a 0.4mm stroke around a 7pt `V`
    # throws a spike twice the halo's width off the letter.
    c.op("1", "J")
    c.op("1", "j")
    c.op("S")


def _draw_text_outlined(c: _Content, glyphs: list[PlacedGlyph], style: Style,
                        ink: str | None) -> None:
    for colour, run in _ink_runs(glyphs):
        paths = to_path(run)
        if paths is not None and _subpaths(c, paths.subpaths):
            _paint(c, style, fill=colour or ink, stroke=None)


def _draw_text_live(c: _Content, glyphs: list[PlacedGlyph], style: Style,
                    ink: str | None) -> None:
    """The same glyphs as text objects, so a reader can select the words.

    A face that cannot be a `/FontFile2` falls back to outlines for its own
    glyphs and nothing else -- a Japanese clause borrowed from a CFF face
    stops being selectable, and the Latin sentence around it does not.
    """
    for group in text_runs(glyphs, c.shared.fonts):
        colour = group.fill or ink
        if group.font is None:
            paths = to_path(list(group.glyphs))
            if paths is not None and _subpaths(c, paths.subpaths):
                _paint(c, style, fill=colour, stroke=None)
            continue
        c.op("q")
        if _paintable(colour):
            c.op(_rgb(colour, c.precision), "rg")
        else:
            # `fill="none"` on live text: invisible and still selectable,
            # which is what the SVG spelling of it does too.
            c.op("3", "Tr")
        c.ops += show_text(group, c.n)
        c.op("Q")


def _ink_runs(glyphs: list[PlacedGlyph]) -> list[tuple[str | None, list[PlacedGlyph]]]:
    """Consecutive glyphs sharing a colour, in drawing order.

    A PDF content stream sets one fill colour and paints, so a line whose runs
    are coloured differently is several paints. Batching *consecutive* glyphs
    rather than grouping by colour keeps the painting order the tree asked
    for, and the ordinary line -- every glyph the same -- is one batch and one
    path, byte for byte what a single `text_to_paths` produced.
    """
    runs: list[tuple[str | None, list[PlacedGlyph]]] = []
    for glyph in glyphs:
        if runs and runs[-1][0] == glyph.fill:
            runs[-1][1].append(glyph)
        else:
            runs.append((glyph.fill, [glyph]))
    return runs


def _draw_image(c: _Content, prim: ImagePrim) -> None:
    name = c.image(prim)
    # A PDF image fills the unit square with its first row at the top of it,
    # so the height is negated to put row zero at the top of the *local* box,
    # y growing downward here as everywhere else in inklet.
    c.op(c.n(prim.width), "0", "0", c.n(-prim.height),
         c.n(-prim.width / 2), c.n(prim.height / 2), "cm")
    c.op(f"/{name}", "Do")


# -- images ---------------------------------------------------------------


def _image_object(prim: ImagePrim) -> tuple[bytes, bytes, bytes | None]:
    """One raster as (XObject dictionary body, encoded stream, alpha channel).

    Streams come back already encoded, because the two routes encode
    differently: a baseline JPEG is passed through untouched -- `DCTDecode` is
    the same codec, so re-encoding it would cost quality for nothing -- and
    everything else is decoded to RGB and deflated. Only that second route
    needs Pillow, and the error only fires for a figure that actually places a
    raster, so `import inklet` stays free of it.

    A prim carrying its own `data` never touches the filesystem: the bytes are
    the image, and `source` is only what to call it in a diagnostic.
    """
    from ..assets.deps import require

    image_module = require("PIL.Image")
    data = getattr(prim, "data", None)
    source = BytesIO(data) if data is not None else prim.source
    with image_module.open(source) as image:
        width, height = image.size
        if (image.format == "JPEG" and not image.info.get("progressive")
                and image.mode in ("L", "RGB")):
            space = "DeviceGray" if image.mode == "L" else "DeviceRGB"
            raw = data if data is not None else Path(prim.source).read_bytes()
            return (_image_dict(width, height, space, "DCTDecode",
                                _smooth(prim)), raw, None)
        bands = image.getbands()
        alpha = image.getchannel("A").tobytes() if "A" in bands else None
        pixels = image.convert("RGB").tobytes()

    if alpha is not None and min(alpha) == 255:
        alpha = None            # fully opaque: an /SMask would cost bytes and do nothing
    return (_image_dict(width, height, "DeviceRGB", "FlateDecode",
                        _smooth(prim)),
            zlib.compress(pixels, 9), alpha)


def _smooth(prim: ImagePrim) -> bool:
    """Whether this raster may be resampled smoothly when it is scaled.

    A PDF image is nearest-neighbour unless it says otherwise, which is the
    right default for the figure case -- a heatmap drawn one pixel per cell is
    data, and interpolating it invents values between the cells. `smooth=True`
    is a photograph asking not to be shown its own pixel grid.
    """
    return getattr(prim, "smooth", None) is True


def _image_dict(width: int, height: int, space: str, filter_: str,
                smooth: bool = False) -> bytes:
    interpolate = " /Interpolate true" if smooth else ""
    return (f"/Type /XObject /Subtype /Image /Width {width} /Height {height} "
            f"/ColorSpace /{space} /BitsPerComponent 8{interpolate} "
            f"/Filter /{filter_}").encode("ascii")


# -- the file -------------------------------------------------------------


class _Objects:
    """Indirect objects, numbered from 1 in the order they are added."""

    def __init__(self) -> None:
        self.bodies: list[bytes] = []

    def add(self, body: bytes) -> int:
        self.bodies.append(body)
        return len(self.bodies)

    def add_stream(self, header: bytes, data: bytes, *, compress: bool) -> int:
        if compress:
            data = zlib.compress(data, 9)
            header += b" /Filter /FlateDecode"
        return self.add(b"<< " + header + f" /Length {len(data)} >>\nstream\n".encode("ascii")
                        + data + b"\nendstream")

    def serialize(self, root: int, info: int, file_id: str) -> bytes:
        out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = []
        for number, body in enumerate(self.bodies, start=1):
            offsets.append(len(out))
            out += f"{number} 0 obj\n".encode("ascii") + body + b"\nendobj\n"
        start = len(out)
        count = len(self.bodies) + 1
        out += f"xref\n0 {count}\n0000000000 65535 f \n".encode("ascii")
        for offset in offsets:
            out += f"{offset:010d} 00000 n \n".encode("ascii")
        out += (f"trailer\n<< /Size {count} /Root {root} 0 R /Info {info} 0 R "
                f"/ID [<{file_id}><{file_id}>] >>\n"
                f"startxref\n{start}\n%%EOF\n").encode("ascii")
        return bytes(out)


def _canvas(root: Diagram, width, height, margin: float) -> tuple[Rect, float, float]:
    """Content box (bbox plus margin) and the page size, both in mm.

    Deliberately the same rule as the SVG backend's: a figure has one page size
    whichever file it is written to, or the two would disagree about where the
    content sits.
    """
    try:
        box = root.bbox
    except DiagramError:
        box = Rect(0.0, 0.0, 0.0, 0.0)
    content = box.pad(margin)
    page_w = content.width if width is None else to_mm(width)
    page_h = content.height if height is None else to_mm(height)
    return content, page_w, page_h


def _drawables(node: Diagram) -> int:
    """How many primitives the subtree actually inks. Stops at two, because
    the only question asked of it is whether translucent children can overlap
    each other."""
    count = 0
    for descendant in node.walk():
        if descendant.prim is not None and not isinstance(descendant.prim, PhantomPrim):
            count += 1
            if count > 1:
                return count
    return count


def _world_box(node: Diagram, world: Affine) -> Rect:
    """The subtree's bounding box in page millimetres, for a form's `/BBox`."""
    try:
        box = node.local_bbox
    except DiagramError:
        return Rect(0.0, 0.0, 0.0, 0.0)
    corners = [world.apply(point) for point in box.corners]
    xs = [p.x for p in corners]
    ys = [p.y for p in corners]
    return Rect(min(xs), min(ys), max(xs), max(ys))


def _emit_node(c: _Content, node: Diagram, parent: Affine, inherited: Style,
               alpha: float) -> None:
    """Draw one node and its children, honouring opacity the way SVG does.

    SVG's `opacity` is a property of the *group*: the subtree is composited
    once, at that alpha, so two translucent shapes inside a translucent group
    do not show through each other twice. `core.flatten` cannot express that
    -- it resolves style by inheritance, which hands each leaf the innermost
    value and loses the product -- so the PDF backend walks the tree itself.

    A group that inks more than once becomes a PDF transparency group, which
    is the same composite-then-paint rule. A group with a single drawable
    under it cannot overlap itself, so its alpha is simply multiplied into
    that one shape: the common case (a whole figure faded, one translucent
    box) costs nothing and its bytes do not move.
    """
    world = parent @ node.transform
    style = node.style.over(inherited)
    own = node.style.opacity

    if own is not None and own < 1.0:
        if _drawables(node) > 1:
            inner = c.child()
            _emit_contents(inner, node, world, style, 1.0)
            name = c.shared.form(inner.render(), _world_box(node, world))
            c.op("q")
            c.op(f"/{c.alpha(alpha * own)}", "gs")
            c.op(f"/{name}", "Do")
            c.op("Q")
            return
        alpha *= own

    _emit_contents(c, node, world, style, alpha)


def _emit_contents(c: _Content, node: Diagram, world: Affine, style: Style,
                   alpha: float) -> None:
    """The node's own primitive, then its children. A node's prim paints under
    them, exactly as `core.flatten` orders it."""
    if node.prim is not None and not isinstance(node.prim, PhantomPrim):
        c.op("q")
        # `fill_opacity`/`stroke_opacity` multiply into the group alpha rather
        # than replacing it, as SVG and PDF both define them: a band at 20%
        # inside a subtree faded to 50% is 10%.
        fill_a = alpha * _ratio(style, "fill_opacity")
        stroke_a = alpha * _ratio(style, "stroke_opacity")
        if fill_a < 1.0 or stroke_a < 1.0:
            c.op(f"/{c.alpha(fill_a, stroke_a)}", "gs")
        if not world.is_identity:
            c.matrix(world)
        _draw_prim(c, node.prim, style)
        c.op("Q")
    for child in node.children:
        _emit_node(c, child, world, style, alpha)


def _ratio(style: Style, name: str) -> float:
    """A paint opacity, or 1.0 where the style leaves it to `opacity` alone."""
    value = getattr(style, name, None)
    return 1.0 if value is None else float(value)


def to_pdf(root: Diagram | Sequence[Diagram], *, width: float | str | None = None,
           height: float | str | None = None, margin: float = 0.0,
           background: str | None = None, precision: int = 3,
           title: str | None = None, compress: bool = True,
           text: str = "outline") -> bytes:
    """Render one diagram tree, or a sequence of them, to a PDF document.

    `width`/`height`, `margin`, `background` and `precision` mean exactly what
    they mean in `to_svg`, so the same figure written both ways lands on the
    same page at the same size.

    `text` decides what the type in the file *is*, and the default `"outline"`
    is the one a journal wants: every glyph is geometry, the file depends on no
    installed font, and nothing downstream can reflow it. `"embed"` keeps the
    same glyphs at the same places and writes them as real text against a
    subset of each face -- searchable, copyable and reachable by a screen
    reader, at the cost of a font program per face and of a file that a
    printer's preflight will now have an opinion about. `render.pdftext` says
    how the two stay the same picture.

    Pass several roots and they become several pages of one file, each sized
    to its own content, sharing one set of rasters, alpha states and font
    subsets: three sheets that place the same micrograph embed it once.
    `compress` deflates the content streams and is only worth turning off to
    read the operators by hand.
    """
    if text not in PDF_TEXT_MODES:
        raise ValueError(
            f"unknown text mode {text!r} for PDF; expected one of "
            f"{', '.join(PDF_TEXT_MODES)}"
            + ("; PDF has no font-name mode, so a searchable PDF is "
               "text='embed'" if text == "names" else ""))
    roots = [root] if isinstance(root, Diagram) else list(root)
    if not roots:
        raise ValueError("a PDF needs at least one page")
    shared = _Resources()
    pages = []
    for page_root in roots:
        content, page_w, page_h = _canvas(page_root, width, height, margin)
        c = _Content(precision, shared, text=text,
                     paper=background or DEFAULT_PAPER)

        # One transform for the whole page: millimetres in, points out, y
        # flipped, content origin at the top-left corner. Every number after
        # this line is a millimetre, which is what keeps stroke widths honest.
        c.op(c.n(_MITER_LIMIT), "M")
        c.matrix(Affine(a=PT_PER_MM, d=-PT_PER_MM,
                        e=-PT_PER_MM * content.x0,
                        f=PT_PER_MM * (content.y0 + page_h)), _PAGE_PRECISION)
        if background is not None:
            c.op(_rgb(background, precision), "rg")
            c.op(c.n(content.x0), c.n(content.y0), c.n(page_w), c.n(page_h),
                 "re", "f")
        _emit_node(c, page_root, IDENTITY, EMPTY_STYLE, 1.0)
        pages.append((c, page_w, page_h))

    return _assemble(pages, shared, title, compress)


def _assemble(pages: list[tuple[_Content, float, float]], shared: _Resources,
              title: str | None, compress: bool) -> bytes:
    objects = _Objects()
    catalog = objects.add(b"<< /Type /Catalog /Pages 2 0 R >>")
    first = 3                                     # the first page object number
    kids = " ".join(f"{first + i} 0 R" for i in range(len(pages)))
    tree = objects.add(
        f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode("ascii"))
    for _ in pages:
        objects.add(b"")                          # patched below, once numbered
    streams = [c.render() for c, _, _ in pages]
    contents = [objects.add_stream(b"", stream, compress=compress)
                for stream in streams]

    # A transparency group can place a raster, or hold another group, so its
    # resources are the document's -- one dictionary, referenced indirectly,
    # patched once every object in it has a number. Only allocated when there
    # is a group to need it, so a file without one is byte-for-byte the file
    # this backend has always written.
    shelf = objects.add(b"") if shared.forms else 0
    forms = []
    for name, stream, box in shared.forms:
        header = (f"/Type /XObject /Subtype /Form /FormType 1 /BBox "
                  f"[{_fmt(box.x0, _PAGE_PRECISION)} {_fmt(box.y0, _PAGE_PRECISION)} "
                  f"{_fmt(box.x1, _PAGE_PRECISION)} {_fmt(box.y1, _PAGE_PRECISION)}] "
                  f"/Group << /S /Transparency /CS /DeviceRGB /I false /K false >> "
                  f"/Resources {shelf} 0 R").encode("ascii")
        forms.append(f"/{name} {objects.add_stream(header, stream, compress=compress)} 0 R")

    resources = []
    if shared.alphas:
        entries = " ".join(f"/{name} << /ca {fill} /CA {stroke} >>"
                           for (fill, stroke), name in shared.alphas.items())
        resources.append(f"/ExtGState << {entries} >>")
    refs = list(forms)
    for name, prim in shared.images.values():
        body, data, alpha = _image_object(prim)
        if alpha is not None:
            width, height = _dimensions(body)
            # The mask samples the way its image does, or a smoothed
            # photograph gets a stair-stepped edge against a soft one.
            smask = objects.add_stream(
                _image_dict(width, height, "DeviceGray", "FlateDecode",
                            _smooth(prim)),
                zlib.compress(alpha, 9), compress=False)
            body += f" /SMask {smask} 0 R".encode("ascii")
        refs.append(f"/{name} {objects.add_stream(body, data, compress=False)} 0 R")
    if refs:
        resources.append(f"/XObject << {' '.join(refs)} >>")
    fonts = [f"/{use.name} {_font_object(objects, use, compress)} 0 R"
             for use in shared.fonts.faces.values()]
    if fonts:
        resources.append(f"/Font << {' '.join(fonts)} >>")
    resource_dict = f"<< {' '.join(resources)} >>"
    if shelf:
        objects.bodies[shelf - 1] = resource_dict.encode("latin-1")

    boxes = []
    for index, ((_, page_w, page_h), stream_ref) in enumerate(zip(pages, contents)):
        box = (f"[0 0 {_fmt(page_w * PT_PER_MM, _PAGE_PRECISION)} "
               f"{_fmt(page_h * PT_PER_MM, _PAGE_PRECISION)}]")
        boxes.append(box)
        objects.bodies[first + index - 1] = (
            f"<< /Type /Page /Parent {tree} 0 R /MediaBox {box} "
            f"/Resources {resource_dict} /Contents {stream_ref} 0 R >>"
        ).encode("latin-1")

    entries = ["/Producer (inklet)"]
    if title is not None:
        entries.insert(0, f"/Title {_pdf_string(title)}")
    info = objects.add(("<< " + " ".join(entries) + " >>").encode("latin-1"))

    # A fixed `/ID` would make two different documents claim the same identity;
    # a random one would break byte-identical output. The content's own hash is
    # both stable and distinguishing.
    digest = hashlib.md5()
    for stream, box in zip(streams, boxes):
        digest.update(stream + box.encode("ascii"))
    return objects.serialize(catalog, info, digest.hexdigest().upper())


def _font_object(objects: _Objects, use, compress: bool) -> int:
    """One face as the four objects a Type0 font is made of, plus its program.

    The split is PDF's, not this backend's: a Type0 font names an encoding and
    delegates the glyphs to a descendant CIDFont, which names a descriptor,
    which names the font file. `/CIDToGIDMap /Identity` is the line that makes
    the whole thing work here -- the CID in the content stream is the glyph id,
    which is exactly what `fontembed.subset_sfnt` preserved.
    """
    subset = use.subset()
    name = f"{subset.tag}+{subset.postscript_name}"
    program = objects.add_stream(f"/Length1 {len(subset.data)}".encode("ascii"),
                                 subset.data, compress=compress)
    descriptor = objects.add((
        f"<< /Type /FontDescriptor /FontName /{name} /Flags {subset.flags} "
        f"/FontBBox [{' '.join(str(v) for v in subset.bbox)}] "
        f"/ItalicAngle {_fmt(subset.italic_angle, 2)} /Ascent {subset.ascent} "
        f"/Descent {subset.descent} /CapHeight {subset.cap_height} "
        # /StemV is required and unknowable from a TrueType file -- it is a
        # Type 1 measurement. Every producer writes a plausible constant.
        f"/StemV 80 /FontFile2 {program} 0 R >>").encode("latin-1"))
    unicode_map = objects.add_stream(b"", to_unicode_cmap(use), compress=compress)
    descendant = objects.add((
        f"<< /Type /Font /Subtype /CIDFontType2 /BaseFont /{name} "
        f"/CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) "
        f"/Supplement 0 >> /FontDescriptor {descriptor} 0 R "
        f"/W {widths_array(subset)} /CIDToGIDMap /Identity >>").encode("latin-1"))
    return objects.add((
        f"<< /Type /Font /Subtype /Type0 /BaseFont /{name} "
        f"/Encoding /Identity-H /DescendantFonts [{descendant} 0 R] "
        f"/ToUnicode {unicode_map} 0 R >>").encode("latin-1"))


def _dimensions(body: bytes) -> tuple[int, int]:
    fields = body.decode("ascii").split()
    return (int(fields[fields.index("/Width") + 1]),
            int(fields[fields.index("/Height") + 1]))


def save_pdf(root: Diagram | Sequence[Diagram], path: str | Path, **kwargs) -> None:
    """Write `root` to `path` as PDF. `to_pdf` is the same thing as bytes.

    By default every glyph is a filled path, so the file needs no font
    installed and no font embedded -- which also means the text in it cannot be
    searched or copied. `text="embed"` writes the same glyphs at the same
    places as real text against a subset of each face; `to_pdf` says what that
    trades.

    A sequence of roots writes one file of several pages:
    `save_pdf([sheet1, sheet2], "figure.pdf")`.
    """
    Path(path).write_bytes(to_pdf(root, **kwargs))
