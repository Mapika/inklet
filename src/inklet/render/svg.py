"""SVG output for `inklet`.

Millimetre-native: the viewBox is expressed in mm and `width`/`height` carry
the same numbers with an explicit `mm` suffix, so one SVG user unit is exactly
one millimetre and `stroke-width="0.25"` is a 0.25 mm hairline on paper.

The output mirrors the `Diagram` tree instead of being flattened: one `<g>` per
node, nested, carrying that node's own `Style` fields as presentation
attributes so SVG's own inheritance does the cascading. `core.flatten()` is
deliberately not used here -- a nested file is one a designer can open in
Illustrator or Inkscape, click a subtree and move it as a unit; a flattened one
is a pile of unrelated shapes. That editability is a product requirement.

Determinism: every number goes through `_fmt`, attributes are written in a
fixed order, and nothing consults a dict's iteration order, the clock or a RNG.
The same tree renders byte-identically every time.

Known limitation (M1): SVG scales stroke widths along with geometry, so a
0.25 mm `stroke_width` inside a `.scaled(2)` subtree paints at 0.5 mm. The two
ways out are both worse than the disease for now -- dividing each node's
stroke width by the accumulated `Affine.uniform_scale()` is wrong under
anisotropic or skewing transforms, and `vector-effect="non-scaling-stroke"`
pins the width to device pixels rather than to millimetres, which defeats the
point of a print backend. Left as-is until a caller actually needs it.

Four `Style` fields have no honest presentation-attribute form and are handled
at the leaf instead of on the group: `corner_radius` becomes a `<rect>`'s `rx`
when the `RectPrim` does not carry its own radius, `text_fill` becomes `fill`
on `<text>` (as a group `fill` it would repaint every shape too), `halo`
becomes a stroke under the glyphs of a `<text>` and nothing at all on a shape,
and `line_height` is already baked into the baselines `inklet.typeset` shaped, so
there is nothing left to emit.

The halo is `paint-order="stroke"` on the one `<text>` element rather than a
second copy of it underneath, and that is a decision with a cost either way.
The duplicate works in every renderer ever written; it also doubles the text
in the file, so a reader's find box matches twice and copying a caption out
gives every word twice -- in a backend whose whole argument for live text is
that it can be read, that is the wrong half to break. `paint-order` costs
about 70 bytes on a haloed label against 200 for the copy, keeps one element
per label, and is painted correctly by every engine of the last decade
(Chrome, Firefox, Safari, Inkscape 1.x, librsvg, resvg, Illustrator CC 2018+).
Where it is *not* understood the attribute is ignored and the paper-coloured
stroke paints over the glyph, which is unreadable rather than merely unhaloed
-- so it goes out only on a node that asked for a halo, and never by default.
Outlined text has no such dilemma and gets a separate stroked `<g>` under the
fills, which is also the only spelling that keeps one glyph's halo from
cutting into its neighbour's ink.
"""

from __future__ import annotations

import base64
import mimetypes
from typing import Sequence

from ..core.diagram import Diagram, DiagramError
from ..core.geom import Affine, Rect
from ..core.prims import (
    EllipsePrim, ImagePrim, PathPrim, PhantomPrim, Prim, RectPrim, Subpath,
    TextPrim,
)
from ..core.style import EMPTY_STYLE, Style
from ..core.units import mm as to_mm
from ..typeset.fonts import load_face
from .glyphs import PlacedGlyph, glyph_outline, placed_glyphs
from .outline import resolve_text_mode
from .pathdata import PACK_ABOVE, Command, Fixed, spell_open, spell_packed

__all__ = ["to_svg", "save_svg"]

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"

_JOIN_EPS = 1e-9
#: What a halo is painted in when neither the style nor the page says.
DEFAULT_PAPER = "#ffffff"
#: A pack threshold no path reaches, which is what `compact=False` means.
_NEVER_PACK = 1 << 30
Attrs = list[tuple[str, str]]
#: A self-closing element: its tag and its attributes.
Shape = tuple[str, Attrs]


# -- formatting -----------------------------------------------------------


#: `Fixed` is stateless past its precision, so one per precision is enough and
#: the common case never builds a second.
_FIXED: dict[int, Fixed] = {}


def fixed_for(precision: int) -> Fixed:
    """The number machinery for `precision` decimals, built once."""
    got = _FIXED.get(precision)
    if got is None:
        got = _FIXED[precision] = Fixed(precision)
    return got


def _fmt(value: float, precision: int) -> str:
    """The single number formatter. See `Fixed.text`."""
    return fixed_for(precision).text(value)


def _escape(text: str, *, quotes: bool = False) -> str:
    out = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return out.replace('"', "&quot;") if quotes else out


def _comment(text: str) -> str:
    """`--` cannot appear inside an XML comment, at all, ever."""
    return f"<!-- {text.replace('--', '- -')} -->"


# -- writer ---------------------------------------------------------------


class _Writer:
    """Lines of markup, and the two dials that decide how much of them there is.

    `indent` is whether the structure is laid out for a reader. `pack_above`
    is the path length past which the packed spelling is used anyway -- 0
    packs everything, and a number no path reaches packs nothing.
    """

    def __init__(self, precision: int, compact: bool | str = False, *,
                 text: str = "names",
                 paper: str = DEFAULT_PAPER) -> None:
        self.precision = precision
        self.fixed = fixed_for(precision)
        self.n = self.fixed.text
        self.compact = compact is True
        self.indent = compact is not True
        self.pack_above = (0 if compact is True
                           else PACK_ABOVE if compact == "auto"
                           else _NEVER_PACK)
        self.lines: list[str] = []
        self.depth = 0
        # How text is written, and the two registries the non-default modes
        # fill in as the body is emitted. Both are read afterwards, which is
        # why the body is rendered into its own writer before the header goes
        # out: `<defs>` and `<style>` have to precede what refers to them.
        self.text_mode = text
        # What an unnamed halo is painted in: the page's own colour, so the
        # halo reads as paper showing through rather than as an outline.
        self.paper = paper
        self.glyphs = _GlyphDefs()
        self.faces = _FaceUse()
    # numbers and attributes

    def nums(self, values: Sequence[float], sep: str = " ") -> str:
        return sep.join(self.n(v) for v in values)

    def _attrs(self, attrs: Attrs) -> str:
        return "".join(f' {k}="{_escape(v, quotes=True)}"' for k, v in attrs)

    # elements

    def line(self, text: str) -> None:
        self.lines.append("  " * self.depth + text if self.indent else text)

    def empty(self, tag: str, attrs: Attrs) -> None:
        self.line(f"<{tag}{self._attrs(attrs)}/>")

    def open(self, tag: str, attrs: Attrs) -> None:
        self.line(f"<{tag}{self._attrs(attrs)}>")
        self.depth += 1

    def close(self, tag: str) -> None:
        self.depth -= 1
        self.line(f"</{tag}>")

    def text_element(self, attrs: Attrs, children: str) -> None:
        """Written on one physical line on purpose: the root sets
        `xml:space="preserve"`, so the whitespace *between* two `<tspan>`s is
        rendered text and pretty indentation would silently inject spaces into
        the figure."""
        self.line(f"<text{self._attrs(attrs)}>{children}</text>")

    def render(self) -> str:
        return "\n".join(self.lines) + "\n"


# -- the two text registries ----------------------------------------------


class _GlyphDefs:
    """One `<path>` per distinct (face, glyph, size), and the ids to reach them.

    A figure's text is the same forty letters over and over, and outlining
    writes every occurrence of every one of them out in full -- which is why
    an outlined page is five to seven times the named-font one. Registering
    each glyph the first time it is placed turns the rest into `<use>`.

    The size is part of the key rather than a `scale()` on each `<use>`,
    because a figure sets its type in two or three sizes and holds thousands
    of glyphs: two more copies of an alphabet is cheaper than a transform on
    every letter of the page. Ids are `G0`, `G1`... in first-placed order,
    unless a node in the tree has already claimed one of those, which
    `reserve` checks for.
    """

    __slots__ = ("prefix", "ids", "order")

    def __init__(self) -> None:
        self.prefix = "G"
        self.ids: dict[tuple[str, int, int, float], str | None] = {}
        self.order: list[PlacedGlyph] = []

    def reserve(self, root: Diagram) -> None:
        """Pick a def-id prefix no node id in `root` starts with."""
        taken = {node.id for node in root.walk()}
        while any(name.startswith(self.prefix) for name in taken):
            self.prefix = "inklet-" + self.prefix

    def ref(self, glyph: PlacedGlyph) -> str | None:
        """The def id for this glyph, or None when the glyph has no ink -- a
        space, which the shaper measures and nothing draws."""
        key = glyph.key
        if key in self.ids:
            return self.ids[key]
        contours = glyph_outline(glyph)
        got = None if not contours else f"{self.prefix}{len(self.order)}"
        self.ids[key] = got
        if got is not None:
            self.order.append(glyph)
        return got

    def emit(self, w: _Writer) -> None:
        if not self.order:
            return
        # Packed regardless of length, unless `compact=False` asked for
        # absolute coordinates everywhere. The readable spelling exists so a
        # person can edit a shape, and nobody edits the outline of an `a`:
        # here it is 40% more bytes for a `d` no one will ever read.
        pack = w.pack_above < _NEVER_PACK
        w.open("defs", [])
        for glyph in self.order:
            commands: list[Command] = []
            for sub in glyph_outline(glyph):
                commands += _subpath_commands(sub, w)
            data = (spell_packed(commands, w.fixed) if pack
                    else spell_open(commands, w.fixed))
            w.empty("path", [("id", self.ids[glyph.key]), ("d", data)])
        w.close("defs")


class _FaceUse:
    """Which characters each face was asked for, and what to call it in CSS.

    `text="embed"` puts one subset per face in the document, so the family
    names the `<text>` elements use have to be this document's own -- two
    faces of one family (the regular and the bold) are two subsets and cannot
    both answer to the family name they share. The name is derived from the
    real one so a person reading the file can still tell what it is.
    """

    __slots__ = ("names", "used")

    def __init__(self) -> None:
        self.names: dict[tuple[str, int], str] = {}
        self.used: dict[tuple[str, int], set[int]] = {}

    def name(self, path: str, index: int, family: str) -> str:
        """This document's name for a face, or the real one if it cannot travel.

        A file the subsetter cannot open is not a broken figure -- it is a
        figure that falls back to `text="names"` for that one face, which is
        decided here rather than at `emit` time because by then the `<text>`
        elements naming the family have already been written.
        """
        from . import fontembed

        key = (path, index)
        got = self.names.get(key)
        if got is None:
            if not fontembed.readable(path, index):
                return family
            slug = "".join(c if c.isalnum() else "-" for c in family).strip("-").lower()
            got = self.names[key] = f"inklet{len(self.names)}-{slug or 'face'}"
            self.used[key] = set()
        return got

    def record(self, path: str, index: int, family: str, text: str) -> str:
        name = self.name(path, index, family)
        used = self.used.get((path, index))
        if used is not None:
            used.update(ord(c) for c in text)
        return name

    def emit(self, w: _Writer) -> None:
        """The `<style>` block, or nothing when no text was embedded."""
        from . import fontembed

        rules = []
        for (path, index), name in self.names.items():
            codepoints = frozenset(self.used[(path, index)])
            try:
                subset = fontembed.subset_face(path, index, codepoints)
            except Exception as exc:                      # noqa: BLE001
                w.line(_comment(f"font not embedded, cannot subset {path}: {exc}"))
                continue
            rules.append(fontembed.face_rule(name, subset))
        if rules:
            w.line("<style>" + "".join(rules) + "</style>")


# -- style ----------------------------------------------------------------


def _style_attrs(style: Style, writer: _Writer) -> Attrs:
    """A node's own style as presentation attributes, in a fixed order. `None`
    means inherit, so the attribute is simply absent -- no defaults are
    invented here, that is `inklet.themes`'s job. A shape with no fill and no
    stroke anywhere above it is invisible, and that is the correct rendering of
    what it was asked to draw."""
    attrs: Attrs = []
    if style.fill is not None:
        attrs.append(("fill", style.fill))
    if getattr(style, "fill_opacity", None) is not None:
        attrs.append(("fill-opacity", writer.n(style.fill_opacity)))
    if style.stroke is not None:
        attrs.append(("stroke", style.stroke))
    if getattr(style, "stroke_opacity", None) is not None:
        attrs.append(("stroke-opacity", writer.n(style.stroke_opacity)))
    if style.stroke_width is not None:
        attrs.append(("stroke-width", writer.n(style.stroke_width)))
    if style.stroke_dash is not None:
        dash = writer.nums(style.stroke_dash, sep=",")
        attrs.append(("stroke-dasharray", dash or "none"))
    if style.stroke_linecap is not None:
        attrs.append(("stroke-linecap", style.stroke_linecap))
    if style.stroke_linejoin is not None:
        attrs.append(("stroke-linejoin", style.stroke_linejoin))
    if style.opacity is not None:
        attrs.append(("opacity", writer.n(style.opacity)))
    if writer.text_mode == "outline":
        # Nothing under here is text any more. The theme puts a family and a
        # size on the page root and on every label group, and once the glyphs
        # are paths they are bytes that address nobody.
        return attrs
    if style.font_family is not None:
        attrs.append(("font-family", style.font_family))
    if style.font_size is not None:
        attrs.append(("font-size", writer.n(style.font_size)))
    if style.font_weight is not None:
        attrs.append(("font-weight", style.font_weight))
    if getattr(style, "font_style", None) is not None:
        attrs.append(("font-style", style.font_style))
    return attrs


# -- primitives -----------------------------------------------------------


def _rect(prim: RectPrim, style: Style, w: _Writer) -> Shape:
    radius = prim.radius if prim.radius > 0 else (style.corner_radius or 0.0)
    attrs: Attrs = [
        ("x", w.n(-prim.width / 2)),
        ("y", w.n(-prim.height / 2)),
        ("width", w.n(prim.width)),
        ("height", w.n(prim.height)),
    ]
    if radius > 0:
        attrs.append(("rx", w.n(radius)))
    return "rect", attrs


def _ellipse(prim: EllipsePrim, w: _Writer) -> Shape:
    # A circle is an ellipse with one number instead of two, and one number is
    # what someone hand-editing the file would rather see.
    if prim.rx == prim.ry:
        return "circle", [("cx", "0"), ("cy", "0"), ("r", w.n(prim.rx))]
    return "ellipse", [("cx", "0"), ("cy", "0"),
                       ("rx", w.n(prim.rx)), ("ry", w.n(prim.ry))]


def _same(a, b) -> bool:
    """Two points the same to within a rounding of nothing."""
    return abs(a.x - b.x) <= _JOIN_EPS and abs(a.y - b.y) <= _JOIN_EPS


def _subpath_commands(sub: Subpath, w: _Writer) -> list[Command]:
    """One subpath as absolute commands in fixed point.

    Fixed point rather than text because the packed spelling subtracts these
    from one another, and it has to be able to do that exactly. See
    `render.pathdata`.
    """
    units = w.fixed.units
    if sub.curves:
        return _curve_commands(sub, units)
    if not sub.points:
        return []
    first, *rest = sub.points
    commands: list[Command] = [("M", (units(first.x), units(first.y)))]
    commands += [("L", (units(p.x), units(p.y))) for p in rest]
    if sub.closed:
        commands.append(("Z", ()))
    return commands


def _curve_commands(sub: Subpath, units) -> list[Command]:
    """Real cubics when the shaper kept them, so the file stays editable as
    curves rather than as the flattened polyline `points` carries for geometry."""
    start = sub.curves[0][0]
    commands: list[Command] = [("M", (units(start.x), units(start.y)))]
    cursor = start
    for p0, c1, c2, p3 in sub.curves:
        if abs(p0.x - cursor.x) > _JOIN_EPS or abs(p0.y - cursor.y) > _JOIN_EPS:
            commands.append(("L", (units(p0.x), units(p0.y))))
        if _same(c1, p0) and _same(c2, p3):
            # A straight segment of an otherwise curved contour, which is how
            # it has to arrive: `Subpath.curves` is all-or-nothing, so the
            # stem of a `b` comes through as a cubic with its controls sitting
            # on its endpoints. A line is a third of the numbers for the same
            # ink, and a glyph outline is mostly these.
            commands.append(("L", (units(p3.x), units(p3.y))))
        else:
            commands.append(("C", (units(c1.x), units(c1.y), units(c2.x),
                                   units(c2.y), units(p3.x), units(p3.y))))
        cursor = p3
    if sub.closed:
        commands.append(("Z", ()))
    return commands


def _path(prim: PathPrim, w: _Writer) -> Shape | None:
    """The whole prim as one `d`, spelled out or packed.

    Which spelling depends on how long the path is, not only on `compact`:
    the readable form exists so that a person can read it, and past a few
    dozen commands there is no person. `pathdata.spell_packed` is exact, so
    the choice costs nothing but the look of the file.
    """
    commands: list[Command] = []
    for sub in prim.subpaths:
        commands += _subpath_commands(sub, w)
    if not commands:
        return None
    data = (spell_packed(commands, w.fixed) if len(commands) > w.pack_above
            else spell_open(commands, w.fixed))
    attrs: Attrs = [("d", data)]
    if not prim.filled:
        attrs.append(("fill", "none"))
    elif getattr(prim, "fill_rule", "nonzero") != "nonzero":
        # Only on a filled path: a stroke has no interior for a rule to
        # decide, and SVG would inherit the attribute down to shapes that do.
        attrs.append(("fill-rule", prim.fill_rule))
    return "path", attrs


def _text_parts(prim: TextPrim):
    """Every string the `<text>` will contain, line by line and run by run."""
    for line in prim.lines:
        if line.runs:
            yield from (run.text for run in line.runs)
        else:
            yield line.text


def _collapse_safe(text: str) -> bool:
    """True when SVG's default whitespace handling would leave `text` alone.

    Without `xml:space="preserve"` a viewer turns tabs and newlines into
    spaces, collapses runs of them and drops the ones at the ends. A line with
    none of those reads the same either way.
    """
    return not (text[:1].isspace() or text[-1:].isspace()
                or "  " in text or "\t" in text or "\n" in text
                or "\r" in text)


def _family(family: str, path: str | None, index: int, w: _Writer) -> str:
    """What a `<text>` should call its face: the real family, or this
    document's name for the subset of it that travels inside the file."""
    if w.text_mode != "embed" or path is None:
        return family
    return w.faces.name(path, index, family)


def _face_attrs(run_path: str | None, run_index: int,
                block_path: str | None) -> str:
    """`font-weight` and `font-style` for a run set in a different face.

    `inklet.typeset` measures a bold or italic run against the bold or italic
    file and records only the path; a viewer handed nothing but a family name
    paints it in the regular face, so the line is measured in one weight and
    drawn in another. The face itself knows which it is -- OS/2 usWeightClass
    and the italic bit -- so the attributes are read off the file rather than
    guessed from the markup that asked for it.
    """
    if run_path is None or run_path == block_path:
        return ""
    face = load_face(run_path, run_index)
    block = load_face(block_path) if block_path else None
    out = ""
    if face.weight != (block.weight if block else 400):
        out += f' font-weight="{face.weight}"'
    if face.italic != (block.italic if block else False):
        out += f' font-style="{"italic" if face.italic else "normal"}"'
    return out


def _record_faces(prim: TextPrim, w: _Writer) -> None:
    """Note which characters each face in this block was asked to draw.

    Only the characters: the subset is built by codepoint and closed over
    layout by `fontTools`, so a ligature the viewer reshapes into comes along
    without this side having to know it exists. See `render.fontembed`.
    """
    for line in prim.lines:
        if not line.runs:
            w.faces.record(prim.font_path, 0, prim.font_family, line.text)
            continue
        for run in line.runs:
            if run.font_path is None:
                w.faces.record(prim.font_path, 0, prim.font_family, run.text)
            else:
                w.faces.record(run.font_path, run.font_index, run.font_family, run.text)


def _halo_attrs(style: Style, w: _Writer) -> Attrs:
    """The stroke that paints under a label, or nothing when none was asked for.

    `round` joins because a miter on a 0.4mm stroke around a 7pt `V` throws a
    spike twice the halo's width off the letter, which reads as a defect
    rather than as a halo.
    """
    width = getattr(style, "halo", None)
    if not width or width <= 0:
        return []
    return [("stroke", getattr(style, "halo_color", None) or w.paper),
            ("stroke-width", w.n(width)),
            ("stroke-linejoin", "round")]


def _text(prim: TextPrim, style: Style, w: _Writer) -> None:
    """Text stays text: no outlining, so the figure remains searchable,
    restyleable and small.

    `text-anchor` is deliberately not used. The lines arrived from `inklet.typeset`
    with exact shaped advances, so `line_offset` already knows where each line
    starts within the block; asking the SVG viewer to centre them again would
    hand the alignment back to whatever font it managed to find.
    """
    if not prim.lines:
        return
    if w.text_mode == "embed" and prim.font_path is not None:
        _record_faces(prim, w)
    attrs: Attrs = []
    # A single-line block is one element, not two: `x` and `y` are legal on
    # `<text>` itself, and a lone `<tspan>` that only carries them is a DOM
    # node per label doing nothing. Multi-line blocks still need one span per
    # baseline, so they keep the spans and `<text>` keeps no position.
    single = prim.lines[0] if len(prim.lines) == 1 and not prim.lines[0].runs else None
    if single is not None:
        attrs.append(("x", w.n(-prim.width / 2 + prim.line_offset(single))))
        attrs.append(("y", w.n(prim.first_baseline + single.baseline)))
        if single.word_spacing:
            attrs.append(("word-spacing", w.n(single.word_spacing)))
    # The family and the size are only worth restating when the group above
    # does not already say them; `inklet.typeset` resolved a face out of the
    # theme's chain, so usually it does not.
    family = _family(prim.font_family, prim.font_path, 0, w)
    if style.font_family != family:
        attrs.append(("font-family", family))
    if style.font_size is None or w.n(style.font_size) != w.n(prim.font_size):
        attrs.append(("font-size", w.n(prim.font_size)))
    if style.text_fill is not None:
        attrs.append(("fill", style.text_fill))
    # Glyphs are filled, never stroked -- unless the node asked for a halo,
    # which is the one stroke on a glyph that is not a mistake. Without the
    # `none`, text nested in a group that strokes its shapes -- a connector and
    # its label, say -- inherits that stroke and every letter is outlined,
    # which reads as a clumsy fake bold. Unconditional, though only an
    # inherited stroke can make it matter: an invariant a reader can check by
    # looking at one element is worth more than the fourteen bytes it costs on
    # the ones that were safe anyway.
    halo = _halo_attrs(style, w)
    if halo:
        # Stroke first, then fill, over the whole element -- see the module
        # docstring for why this and not a second `<text>` underneath.
        attrs.append(("paint-order", "stroke"))
        attrs += halo
    else:
        attrs.append(("stroke", "none"))
    # `xml:space="preserve"` only where the spacing needs it. A viewer without
    # it turns tabs and newlines into spaces, collapses runs of them and drops
    # the ones at the ends -- which for an ordinary caption is a description of
    # doing nothing, and the attribute is a fifth of the element.
    if not all(_collapse_safe(part) for part in _text_parts(prim)):
        attrs.append(("xml:space", "preserve"))
    if single is not None:
        w.text_element(attrs, _escape(single.text))
        return

    left = -prim.width / 2
    spans = []
    for line in prim.lines:
        start = left + prim.line_offset(line)
        y = w.n(prim.first_baseline + line.baseline)
        # `word-spacing` rather than `textLength`: the latter spreads the slack
        # over every glyph gap, which letter-spaces the words. This adds it to
        # the spaces only, which is what justification means.
        extra = (f' word-spacing="{w.n(line.word_spacing)}"'
                 if line.word_spacing else "")
        if not line.runs:
            spans.append(f'<tspan x="{w.n(start)}" y="{y}"{extra}>'
                         f'{_escape(line.text)}</tspan>')
            continue
        # Part of this line is set in a font the block does not name, because
        # the one it does name has no glyph for it. Each span carries its own
        # family and its own x: the advances were measured per run, so placing
        # them is arithmetic rather than a guess about what the viewer will do.
        pen = start
        for run in line.runs:
            script = ""
            if run.size is not None or run.shift:
                script = (f' font-size="{w.n(run.size or prim.font_size)}"'
                          f' y="{w.n(prim.first_baseline + line.baseline + run.shift)}"')
            else:
                script = f' y="{y}"'
            # A run's own colour beats the block's, and only the run's glyphs
            # take it -- which is the whole reason `TextRun.fill` exists rather
            # than the caller splitting the line into two text nodes and
            # placing them by hand.
            paint = (f' fill="{_escape(run.fill, quotes=True)}"'
                     if getattr(run, "fill", None) else "")
            run_family = _family(run.font_family,
                                 run.font_path or prim.font_path,
                                 run.font_index if run.font_path else 0, w)
            # Only when it is not what the block already says: inline markup
            # splits an ordinary caption into a dozen runs, and most of them
            # are in the very face the `<text>` names.
            named = (f' font-family="{run_family}"'
                     if run_family != family else "")
            weight = _face_attrs(run.font_path, run.font_index, prim.font_path)
            spans.append(
                f'<tspan x="{w.n(pen)}"{script}{named}{weight}'
                f'{paint}{extra}>{_escape(run.text)}</tspan>')
            pen += run.advance + run.text.count(" ") * line.word_spacing
    w.text_element(attrs, "".join(spans))


def _text_outlined(prim: TextPrim, style: Style, w: _Writer) -> None:
    """The same text as one `<use>` per glyph, pointing into `<defs>`.

    Outlining without this writes every occurrence of every letter out in
    full, which on a text-heavy page is five to seven times the named-font
    file. A page sets the same alphabet over and over, so one `<path>` per
    distinct (face, glyph, size) and a `<use>` per occurrence is most of that
    back -- and the ink is identical, because both spellings place the same
    cached contours at the same shaped pen positions.

    The wrapper `<g>` does what `<text>` did for itself: takes the colour from
    `text_fill`, and refuses the stroke a surrounding group might be setting
    on its shapes, which on a glyph reads as a clumsy fake bold.
    """
    glyphs = placed_glyphs(prim)
    if not glyphs:
        return
    attrs: Attrs = []
    if style.text_fill is not None:
        attrs.append(("fill", style.text_fill))
    attrs.append(("stroke", "none"))
    refs = [(glyph, w.glyphs.ref(glyph)) for glyph in glyphs]
    refs = [(glyph, name) for glyph, name in refs if name is not None]
    if not refs:
        return
    halo = _halo_attrs(style, w)
    if halo:
        # Every halo before every fill, in two passes over the same `<use>`s.
        # `paint-order` on the group would be one pass and would let each
        # letter's halo cut into the ink of the one before it, which at a 0.4mm
        # halo and a 7pt line is a visible bite out of the tight pairs.
        w.open("g", [("fill", "none")] + halo + [("stroke-linecap", "round")])
        for glyph, name in refs:
            w.empty("use", _use_attrs(glyph, name, w, colour=False))
        w.close("g")
    w.open("g", attrs)
    for glyph, name in refs:
        w.empty("use", _use_attrs(glyph, name, w))
    w.close("g")


def _use_attrs(glyph: PlacedGlyph, name: str, w: _Writer,
               colour: bool = True) -> Attrs:
    """One placed glyph as a reference into `<defs>`.

    `xlink:href` is the namespaced form, as with an image's href: a viewer that
    only knows SVG 1.1 drops a bare `href` on the floor, and here that means
    not one letter of the figure appears -- which is the exact failure
    outlining exists to prevent. Six bytes a glyph, 2% of the file.
    """
    attrs: Attrs = [("xlink:href", "#" + name)]
    if glyph.origin.x:
        attrs.append(("x", w.n(glyph.origin.x)))
    if glyph.origin.y:
        attrs.append(("y", w.n(glyph.origin.y)))
    if colour and glyph.fill:
        attrs.append(("fill", glyph.fill))
    return attrs


def _image(prim: ImagePrim, w: _Writer, kind: str | None = None) -> None:
    attrs: Attrs = [
        ("x", w.n(-prim.width / 2)),
        ("y", w.n(-prim.height / 2)),
        ("width", w.n(prim.width)),
        ("height", w.n(prim.height)),
        # The prim states a physical width *and* height and its envelope is
        # that box, so the raster fills it exactly rather than letterboxing
        # into geometry the layout has already committed to.
        ("preserveAspectRatio", "none"),
    ]
    if not _smooth(prim, kind):
        # A heatmap drawn as one pixel per cell is data, not a photograph:
        # bilinear resampling invents values between the cells and blurs the
        # boundary a reader is meant to be able to point at. `pixelated` is
        # the SVG 2 spelling and `crisp-edges` the SVG 1.1 one; viewers take
        # the first they understand, so both go out.
        attrs.append(("image-rendering", "pixelated"))
        attrs.append(("style", "image-rendering:crisp-edges"))
    payload = _data_uri(prim)
    if payload is None:
        # A missing file is a broken link, not a crash: emit the path and say so.
        w.line(_comment(f"image not embedded, file unreadable: {prim.source}"))
        attrs.append(("xlink:href", prim.source))
    else:
        import hashlib
        key=hashlib.sha256((payload+str(_smooth(prim,kind))).encode()).hexdigest()[:20]
        registry=getattr(w,'image_defs',None)
        if registry is None: registry=w.image_defs={}
        if key in registry:
            width,height=registry[key]
            w.empty('use',[('xlink:href','#inklet-image-'+key),
                           ('transform',f'scale({w.n(prim.width/width)} {w.n(prim.height/height)})')])
            return
        registry[key]=(prim.width,prim.height)
        attrs.append(('id','inklet-image-'+key))
        attrs.append(("xlink:href", payload))
    w.empty("image", attrs)


#: A node whose raster *is* the data -- `Panel.matrix(raster=True)` -- says so
#: with this kind, and gets nearest-neighbour sampling for it.
RASTER_KIND = "raster-matrix"


def _smooth(prim: ImagePrim, kind: str | None) -> bool:
    """Whether this raster may be resampled smoothly when it is scaled.

    `ImagePrim.smooth` is the per-primitive answer and wins where it is stated;
    its default is `None` -- no opinion -- and then the node's role decides,
    which is how a heatmap gets nearest-neighbour sampling without every panel
    having to remember to ask.
    """
    smooth = getattr(prim, "smooth", None)
    if smooth is not None:
        return bool(smooth)
    return kind != RASTER_KIND


#: PNG and JPEG, by the bytes every encoder has to start them with.
_MAGIC = ((b"\x89PNG\r\n\x1a\n", "image/png"), (b"\xff\xd8\xff", "image/jpeg"))


def _data_uri(prim: ImagePrim) -> str | None:
    """Embed the raster so the SVG is one self-contained file. `xlink:href`
    rather than SVG 2's bare `href` because Illustrator and older renderers
    still want the namespaced form and every current viewer accepts it.

    A prim carrying its own `data` -- a heatmap computed into an array, with
    no file behind it -- is embedded from those bytes and the filesystem is
    never touched; `source` is then a label rather than a path, so the type
    comes from the magic number instead of from the suffix.
    """
    raw = getattr(prim, "data", None)
    if raw is not None:
        mime = next((m for magic, m in _MAGIC if raw.startswith(magic)),
                    "application/octet-stream")
    else:
        try:
            with open(prim.source, "rb") as handle:
                raw = handle.read()
        except OSError:
            return None
        mime = mimetypes.guess_type(prim.source)[0] or "application/octet-stream"
    return f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"


def _shape(prim: Prim, style: Style, w: _Writer) -> Shape | None:
    """The single self-closing element a prim draws, or None.

    None covers three different things and the caller treats them alike: a
    prim that draws nothing (`PhantomPrim`), one that draws a compound element
    with children (`TextPrim`), and one that has side effects worth keeping in
    file order (`ImagePrim`'s broken-link comment).
    """
    from .brushes import PaintedPrim, svg_brush
    if isinstance(prim, PaintedPrim):
        key=svg_brush(prim.brush,w)
        shape=_shape(prim.shape,style,w)
        if shape is None: return None
        tag,attrs=shape
        return tag,[(k,v) for k,v in attrs if k!='fill']+[('fill',f'url(#{key})')]
    if isinstance(prim, RectPrim):
        return _rect(prim, style, w)
    if isinstance(prim, EllipsePrim):
        return _ellipse(prim, w)
    if isinstance(prim, PathPrim):
        return _path(prim, w)
    return None


def _emit_prim(prim: Prim, style: Style, w: _Writer,
               kind: str | None = None) -> None:
    if isinstance(prim, PhantomPrim):
        return  # Envelope only. It has no ink and must leave no trace in the file.
    shape = _shape(prim, style, w)
    if shape is not None:
        w.empty(*shape)
    elif isinstance(prim, (RectPrim, EllipsePrim, PathPrim)):
        return                          # an empty path: nothing to draw
    elif isinstance(prim, TextPrim):
        if w.text_mode == "outline" and prim.font_path is not None:
            _text_outlined(prim, style, w)
        else:
            _text(prim, style, w)
    elif isinstance(prim, ImagePrim):
        _image(prim, w, kind)
    else:
        raise NotImplementedError(f'the SVG backend cannot draw a {type(prim).__name__}')


# -- tree -----------------------------------------------------------------


def _emit_node(node: Diagram, inherited: Style, w: _Writer) -> None:
    resolved = node.style.over(inherited)
    style_attrs = _style_attrs(node.style, w)
    transform = node.transform

    attrs: Attrs = [("id", node.id)]
    if node.name:
        attrs.append(("data-name", node.name))
    if not transform.is_identity:
        attrs.append(("transform", _transform(transform, w)))
    attrs += style_attrs
    if node.kind == 'blend' and 'blend_mode' in node.notes:
        attrs.append(('style',f'mix-blend-mode:{node.notes["blend_mode"]};isolation:isolate'))

    if node.prim is not None and not node.children:
        shape = _shape(node.prim, resolved, w)
        if shape is not None:
            # A leaf and its wrapper are one element. Every presentation
            # attribute a `<g>` can carry is legal on the shape itself, and
            # with no siblings there is nothing else for the group to group --
            # so `<g fill=X><path d=.../></g>` is two DOM nodes doing one
            # node's work. On a shaded mesh that is *half the file*: a
            # protein cartoon is thousands of one-path groups, and both the
            # bytes and the time a viewer spends building the tree halve with
            # them. Where the shape sets an attribute itself -- an unfilled
            # path's `fill="none"` -- it wins, which is what the nesting said
            # too.
            tag, own = shape
            mine = {key for key, _ in own}
            w.empty(tag, [pair for pair in attrs if pair[0] not in mine] + own)
            return

    w.open("g", attrs)
    if node.prim is not None:
        # A node's own prim paints under its children.
        _emit_prim(node.prim, resolved, w, node.kind)
    for child in node.children:
        _emit_node(child, resolved, w)
    w.close("g")


def _transform(t: Affine, w: _Writer) -> str:
    """The shortest spelling of the same matrix.

    `matrix(1 0 0 1 4 9)` is what the general case reads as, and it is also
    what almost every node in a laid-out figure gets: layout places things by
    moving them. `translate(4 9)` is the same six numbers with four of them
    left implicit -- a third off the attribute, on every group in the file.
    """
    if t.b == 0.0 and t.c == 0.0:
        if t.a == 1.0 and t.d == 1.0:
            return (f"translate({w.n(t.e)})" if t.f == 0.0
                    else f"translate({w.nums((t.e, t.f))})")
        if t.e == 0.0 and t.f == 0.0:
            return (f"scale({w.n(t.a)})" if t.a == t.d
                    else f"scale({w.nums((t.a, t.d))})")
    return f"matrix({w.nums((t.a, t.b, t.c, t.d, t.e, t.f))})"


def _canvas(root: Diagram, width, height, margin: float) -> tuple[Rect, float, float]:
    """Content box (bbox plus margin) and the page size, both in mm."""
    try:
        box = root.bbox
    except DiagramError:
        box = Rect(0.0, 0.0, 0.0, 0.0)  # An empty tree still gets a margin-sized page.
    content = box.pad(margin)
    page_w = content.width if width is None else to_mm(width)
    page_h = content.height if height is None else to_mm(height)
    return content, page_w, page_h


# -- public API -----------------------------------------------------------


def to_svg(root: Diagram, *, width: float | str | None = None,
           height: float | str | None = None, margin: float = 0.0,
           background: str | None = None, precision: int = 3,
           title: str | None = None, compact: bool | str = "auto",
           text: str = "names") -> str:
    """Render a diagram tree to a self-contained SVG document.

    `width`/`height` accept mm numbers or unit strings (`"89mm"`, `"7pt"`);
    omitted, they follow `root.bbox` grown by `margin`. When given, the page
    takes that size and the content keeps its own bbox origin, so a figure
    built to 89 mm stays put inside a taller page instead of being recentred.

    `text` decides what the type in the file *is*, and the three answers trade
    off differently. `"names"`, the default, is live `<text>` naming a
    font-family chain: editable, searchable, smallest, and reshaped by
    whatever face the reader's machine resolves that chain to. `"outline"`
    turns every glyph into geometry, which depends on nothing and cannot be
    retyped or selected. `"embed"` keeps the text live and puts a subset of
    each face it was measured against inside the file, so it is both exact and
    still text; `render.fontembed` says what that costs.

    `background` is also what an unnamed `Style.halo` is painted in, a halo
    being paper showing through around the letters rather than an outline
    drawn on them; `Style.halo_color` overrides it where the type sits on
    something that is not the page.

    OpenType features belong to the block rather than to the backend: a block
    is shaped under the features it was *measured* with, which it carries
    itself as `TextPrim.features`. Pass them to `inklet.text` or
    `inklet.typeset.shape`, where the measurement happens.

    `compact` chooses how much of the file is spelled out for a reader. The
    default `"auto"` keeps the indentation and the structure but packs the
    data of any path past `pathdata.PACK_ABOVE` commands, on the grounds that
    the shapes people hand-edit -- a frame, an arrow, a callout leader -- are
    all far shorter than that and a shaded mesh is not read at all. `True`
    packs everything and drops the indentation; `False` spells out everything,
    which is the most readable file, the largest one, and the only one whose
    coordinates a renderer never has to add up: the packed spelling is relative,
    and a renderer carrying its pen in single precision lands a fraction of a
    device pixel from where the open one puts it. `render.pathdata` has the
    measurement.
    """
    mode = resolve_text_mode(text)
    paper = background or DEFAULT_PAPER
    w = _Writer(precision, compact, text=mode, paper=paper)
    content, page_w, page_h = _canvas(root, width, height, margin)

    # `<defs>` and `<style>` have to come before what refers to them, and what
    # goes in them is only known once the body has been walked. The default
    # mode needs neither, so it writes straight into the document and the
    # bytes of every existing figure are untouched.
    body = w
    if mode != "names":
        body = _Writer(precision, compact, text=mode, paper=paper)
        body.glyphs, body.faces = w.glyphs, w.faces
        body.depth = 1
        w.glyphs.reserve(root)
        _emit_node(root, EMPTY_STYLE, body)

    w.line('<?xml version="1.0" encoding="UTF-8"?>')
    w.line(_comment("generated by inklet; 1 user unit = 1 mm"))
    w.open("svg", [
        ("xmlns", SVG_NS),
        ("xmlns:xlink", XLINK_NS),
        ("version", "1.1"),
        ("width", f"{w.n(page_w)}mm"),
        ("height", f"{w.n(page_h)}mm"),
        ("viewBox", w.nums((content.x0, content.y0, page_w, page_h))),
    ])
    if title is not None:
        w.line(f"<title>{_escape(title)}</title>")
    if background is not None:
        w.empty("rect", [
            ("id", "inklet-background"),
            ("x", w.n(content.x0)), ("y", w.n(content.y0)),
            ("width", w.n(page_w)), ("height", w.n(page_h)),
            ("fill", background),
        ])
    if body is w:
        _emit_node(root, EMPTY_STYLE, w)
    else:
        w.glyphs.emit(w)
        w.faces.emit(w)
        w.lines += body.lines
    w.close("svg")
    return w.render()


def save_svg(root: Diagram, path: str, *, width: float | str | None = None,
             height: float | str | None = None, margin: float = 0.0,
             background: str | None = None, precision: int = 3,
             title: str | None = None, compact: bool | str = "auto",
             text: str = "names") -> None:
    """Write `root` to `path` as SVG. `to_svg` is the same thing as a string.

    `text` defaults to `"names"`: live `<text>` with the theme's font-family
    chain, so the file stays editable and searchable. The consequence is worth
    knowing: the geometry was measured against whichever font this machine
    resolved that chain to, and a renderer that resolves it differently will
    re-shape the type inside boxes that were sized for the original.
    `text="embed"` closes that off without giving up live text, and
    `text="outline"` gives up the text; `to_svg` says what each costs.
    """
    document = to_svg(root, width=width, height=height, margin=margin,
                      background=background, precision=precision, title=title,
                      compact=compact, text=text)
    # newline="" keeps the bytes identical on Windows, where determinism would
    # otherwise stop at the line endings.
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(document)
