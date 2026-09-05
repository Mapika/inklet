"""Outlining shaped text into geometry.

The class of bug these guard: an outline that *measures* right and *draws*
wrong. The flattened `points` a `Subpath` carries are what every envelope, lint
and layout question is answered from, so a glyph can pass every geometric
assertion in the suite while the `d` attribute a viewer actually paints is
missing the stem of every `b`. So the assertions here are made against the path
data as emitted, not against the prim it came from.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

import pytest

import inklet
from inklet.core import Diagram, Rect, resolve
from inklet.core.diagram import flatten
from inklet.core.prims import PathPrim, PhantomPrim, TextPrim
from inklet.render import outline_text
from inklet.typeset import shape

SVG = "{http://www.w3.org/2000/svg}"
MICRON = 1e-3

_TOKEN = re.compile(r"[MLCZHVmlchvz]|-?(?:\d+\.?\d*|\.\d+)")

#: Coordinates each command takes, and the letter implied by a repeat of it.
_ARITY = {"m": 2, "l": 2, "h": 1, "v": 1, "c": 6, "z": 0}


def drawn_bbox(data: str) -> Rect:
    """Bounding box of the points an SVG path actually visits.

    A real reader rather than a regex over the numbers, because the backend
    picks its own spelling: absolute and spelled out for a short path, relative
    and elided for a long one, and a glyph outline is always the long one.
    Control points count -- this is the hull of what the file says, which is
    only ever larger than the ink.
    """
    tokens = _TOKEN.findall(data)
    points: list[tuple[float, float]] = []
    x = y = start_x = start_y = 0.0
    letter = ""
    index = 0
    while index < len(tokens):
        if tokens[index].isalpha():
            letter = tokens[index]
            index += 1
        absolute = letter.isupper()
        key = letter.lower()
        assert key in _ARITY, f"unhandled path command {letter!r} in {data!r}"
        numbers = [float(n) for n in tokens[index:index + _ARITY[key]]]
        index += _ARITY[key]

        if key == "z":
            x, y = start_x, start_y
        elif key == "h":
            x = numbers[0] if absolute else x + numbers[0]
        elif key == "v":
            y = numbers[0] if absolute else y + numbers[0]
        else:
            base_x, base_y = (0.0, 0.0) if absolute else (x, y)
            pairs = [(base_x + numbers[i], base_y + numbers[i + 1])
                     for i in range(0, len(numbers), 2)]
            points += pairs
            x, y = pairs[-1]
            if key == "m":
                start_x, start_y = x, y
                letter = "L" if absolute else "l"   # pairs after a moveto are lines
        points.append((x, y))
    assert points, f"no points in path data {data!r}"
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return Rect(min(xs), min(ys), max(xs), max(ys))


def only_path(node: Diagram) -> str:
    (path,) = ET.fromstring(inklet.to_svg(node)).iter(f"{SVG}path")
    return path.get("d")


def figure() -> inklet.Figure:
    fig = inklet.figure(width="89mm")
    top = inklet.box("Two-photon\nimaging")
    bottom = inklet.box("ROI extraction")
    fig.add(inklet.vstack([top, bottom], gap=6))
    fig.link(top, bottom, label="dF/F")
    return fig


# -- what the file ends up containing --------------------------------------


def test_outlining_replaces_every_text_element_with_glyphs():
    fig = figure()
    named = ET.fromstring(fig.to_svg())
    outlined = ET.fromstring(fig.to_svg(text="outline"))

    assert list(named.iter(f"{SVG}text"))            # the mode being replaced
    assert list(outlined.iter(f"{SVG}text")) == []
    # Every drawing is still there, and the letters arrived as `<use>` of a
    # `<path>` in `<defs>` -- one per distinct glyph, not one per occurrence.
    drawings = len(list(named.iter(f"{SVG}path")))
    defs = ET.fromstring(fig.to_svg(text="outline")).find(f"{SVG}defs")
    glyphs = len(list(defs.iter(f"{SVG}path")))
    assert len(list(outlined.iter(f"{SVG}path"))) == drawings + glyphs
    assert len(list(outlined.iter(f"{SVG}use"))) > glyphs


def test_outlining_is_deterministic():
    fig = figure()
    assert fig.to_svg(text="outline") == fig.to_svg(text="outline")


def test_an_unknown_text_mode_is_refused_at_the_call_site():
    with pytest.raises(ValueError, match="outlines"):
        figure().to_svg(text="outlines")


# -- the geometry, as emitted ----------------------------------------------


def test_a_mixed_glyph_keeps_its_straight_parts():
    """A `b` is a bowl and a stem: curves and lines in one contour. Since
    `Subpath.curves` is all-or-nothing, recording only the bowl loses the
    ascender, and every measurement still agrees because `points` is right."""
    prim = shape("b", size=inklet.pt(24))
    node = outline_text(Diagram(prim=prim))
    drawn = drawn_bbox(only_path(node))
    ink = node.prim.envelope().bbox()

    # The ascender is the whole point: a `b` without its stem is an `o`, and an
    # `o` is about half as tall.
    assert drawn.height == pytest.approx(ink.height, abs=0.05)
    assert drawn.width == pytest.approx(ink.width, abs=0.05)


@pytest.mark.parametrize("text", ["H", "o", "bd", "Wag", "0123456789"])
def test_emitted_outlines_cover_the_measured_ink(text):
    node = outline_text(Diagram(prim=shape(text, size=inklet.pt(12))))
    drawn = drawn_bbox(only_path(node))
    ink = node.prim.envelope().bbox()
    # Bezier control points can sit outside the curve, so the emitted hull may
    # be a shade larger -- never smaller.
    assert drawn.x0 <= ink.x0 + MICRON and drawn.x1 >= ink.x1 - MICRON
    assert drawn.y0 <= ink.y0 + MICRON and drawn.y1 >= ink.y1 - MICRON


def test_curve_chains_run_tip_to_tip():
    """`Subpath`'s invariant, restated as a test: a renderer draws from
    `curves` alone when it is non-empty, so a partial chain silently loses ink."""
    node = outline_text(Diagram(prim=shape("Bag 8", size=inklet.pt(12))))
    curved = [s for s in node.prim.subpaths if s.curves]
    assert curved, "no glyph in this sample has a curve, which cannot be right"
    for sub in curved:
        assert (sub.curves[0][0] - sub.points[0]).length < MICRON
        assert (sub.curves[-1][3] - sub.points[-1]).length < MICRON
        for (_, _, _, end), (start, *_) in zip(sub.curves, sub.curves[1:]):
            assert (end - start).length < MICRON


# -- what must not move ----------------------------------------------------


def test_the_page_and_every_node_stay_where_they_were():
    fig = figure()
    root, _ = fig.build()
    outlined = outline_text(root)

    assert outlined.bbox == root.bbox
    before, after = resolve(root), resolve(outlined)
    assert set(before) == set(after)
    for node_id, placement in before.items():
        assert after[node_id].world == placement.world
        assert after[node_id].diagram.kind == placement.diagram.kind
        assert after[node_id].diagram.name == placement.diagram.name


def test_a_text_block_keeps_the_envelope_it_was_stacked_by():
    """Glyph ink is narrower than the block -- no descender in `cue` -- so
    taking the paths' own extent would shrink every box in the figure."""
    node = Diagram(prim=shape("cue", size=inklet.pt(8)))
    assert outline_text(node).local_bbox == node.local_bbox


def test_glyphs_land_inside_the_block_they_replaced():
    prim = shape("Spike deconvolution", size=inklet.pt(7))
    ink = outline_text(Diagram(prim=prim)).prim.envelope().bbox()
    block = prim.envelope().bbox()
    assert block.x0 - MICRON <= ink.x0 and ink.x1 <= block.x1 + MICRON
    assert block.y0 - MICRON <= ink.y0 and ink.y1 <= block.y1 + MICRON


def test_whitespace_becomes_a_phantom_rather_than_disappearing():
    node = outline_text(Diagram(prim=shape("   ", size=inklet.pt(8))))
    assert isinstance(node.prim, PhantomPrim)
    assert f"{SVG}path" not in inklet.to_svg(node)
    assert node.local_bbox.width > 0


# -- style -----------------------------------------------------------------


def test_the_text_colour_survives_as_a_fill():
    """`text_fill` paints `<text>` and nothing else; a path has only `fill`.
    Getting this wrong turns white-on-dark labels into invisible ones."""
    node = Diagram(children=(Diagram(prim=shape("label", size=inklet.pt(7))),),
                   ).styled(fill="#123456", text_fill="#ffffff")
    (path,) = ET.fromstring(inklet.to_svg(outline_text(node))).iter(f"{SVG}path")
    assert path.get("fill") == "#ffffff"


def test_outlined_text_is_never_stroked():
    """Nested in a group that strokes its shapes, live text is exempted by the
    SVG backend. A path is not, and inheriting that stroke is a fake bold."""
    node = Diagram(children=(Diagram(prim=shape("x", size=inklet.pt(7))),),
                   ).styled(stroke="#000000", stroke_width=0.5)
    (path,) = ET.fromstring(inklet.to_svg(outline_text(node))).iter(f"{SVG}path")
    assert path.get("stroke") == "none"


# -- runs ------------------------------------------------------------------


def test_subscripts_and_superscripts_outline_at_their_own_size():
    plain = outline_text(Diagram(prim=shape("Ca2+", size=inklet.pt(10))))
    script = outline_text(Diagram(prim=shape("Ca^{2+}", size=inklet.pt(10))))
    assert script.prim.envelope().bbox().y0 < plain.prim.envelope().bbox().y0
    assert "_{" not in inklet.to_svg(script) and "^{" not in inklet.to_svg(script)


def test_outlining_needs_a_shaped_prim():
    naked = TextPrim(lines=shape("x").lines, font_family="sans",
                     font_size=inklet.pt(7), ascent=1.0, descent=0.3)
    with pytest.raises(ValueError, match="font_path"):
        outline_text(Diagram(prim=naked))


def test_nothing_but_text_is_touched():
    """A tree with no text comes back as the very same object, so outlining a
    figure that does not need it costs nothing and keeps every handle valid."""
    node = inklet.polyline([(0, 0), (10, 5)])
    assert outline_text(node) is node
    assert isinstance(inklet.marker("circle", 2).prim, type(inklet.marker("circle", 2).prim))
    assert isinstance(outline_text(Diagram(prim=PathPrim(()))).prim, PathPrim)


# -- per-run fills ---------------------------------------------------------
#
# `{fill|text}` travels as a colour on a `TextRun`, and a filled `PathPrim`
# carries exactly one fill. The tree transform is the only route that has to
# split the block up; `to_svg(text="outline")` and PDF go through
# `render.glyphs`, which keeps the fill per glyph and never merged anything.


def test_a_recoloured_run_reaches_the_outlined_tree():
    """The reproduction from the backlog: all three spellings of an outlined
    figure must paint `{accent|...}` in the accent, not in the block's ink."""
    node = inklet.text("{accent|x}")
    assert "#0072b2" in inklet.to_svg(outline_text(node))
    assert "#0072b2" in inklet.to_svg(node, text="outline")
    assert "#0072b2" in inklet.to_svg(node)


def test_an_uncoloured_block_stays_one_leaf():
    """The structure the whole corpus renders through: one text node in, one
    path leaf out, no children grown underneath it."""
    node = outline_text(Diagram(prim=shape("plain words", size=inklet.pt(7))))
    assert isinstance(node.prim, PathPrim)
    assert node.children == ()
    assert node.style.fill is None


def test_a_block_of_one_colour_keeps_its_colour_on_the_node():
    node = outline_text(Diagram(prim=shape("{#c1121f|all of it}", size=inklet.pt(7))))
    assert isinstance(node.prim, PathPrim)
    assert node.children == ()
    assert node.style.fill == "#c1121f"


def test_a_block_of_several_colours_becomes_a_child_per_colour():
    prim = shape("ink {#c1121f|red} ink {#0072b2|blue}", size=inklet.pt(7))
    node = outline_text(Diagram(prim=prim))

    assert node.prim is None
    assert [child.style.fill for child in node.children] == [None, "#c1121f", "#0072b2"]
    assert all(isinstance(child.prim, PathPrim) for child in node.children)
    # Every glyph is drawn exactly once: the groups partition the block's ink.
    total = sum(len(child.prim.subpaths) for child in node.children)
    single = outline_text(Diagram(prim=shape("ink red ink blue", size=inklet.pt(7))))
    assert total == len(single.prim.subpaths)


def test_a_multicoloured_block_keeps_its_id_and_the_space_it_claimed():
    """A caller's handle and a link's `attached_to` are keyed on the id, and
    the box around a caption was sized from the block, not from the ink."""
    node = Diagram(prim=shape("a {accent|b} c", size=inklet.pt(8)), name="caption")
    outlined = outline_text(node)
    assert outlined.id == node.id and outlined.name == "caption"
    assert outlined.local_bbox == node.local_bbox


def test_the_uncoloured_glyphs_of_a_mixed_block_still_take_the_text_colour():
    """A group of glyphs with no fill of its own inherits the node's, which is
    where the resolved `text_fill` has just been put -- otherwise a white-on-dark
    caption with one coloured word loses every other word."""
    node = Diagram(children=(inklet.text("a {#c1121f|b}", size=inklet.pt(7)),),
                   ).styled(text_fill="#ffffff")
    painted = [item.style.fill for item in flatten(outline_text(node))]
    assert painted == ["#ffffff", "#c1121f"]


def test_a_mixed_block_draws_the_ink_the_glyph_backend_draws():
    """The two outlining routes must agree on colour as well as on geometry."""
    node = inklet.text("one {#c1121f|two} three")
    assert "#c1121f" in inklet.to_svg(outline_text(node))
    assert "#c1121f" in inklet.to_svg(node, text="outline")
    # The tree transform says it once for the group of glyphs that share the
    # colour; the glyph backend says it on each `<use>`. Same picture.
    assert inklet.to_svg(outline_text(node)).count("#c1121f") == 1
