"""The SVG backend, checked against the parsed tree rather than against strings.

Substring assertions pass on malformed XML and on attributes that landed on the
wrong element, so everything here goes through ElementTree and asserts on
structure, then compares the geometry it finds against what `resolve()` says
the same nodes should be at.
"""

from __future__ import annotations

import base64
import re
import xml.etree.ElementTree as ET

import pytest

from inklet.core import (
    Affine, Diagram, EllipsePrim, ImagePrim, PathPrim, PhantomPrim, Rect,
    RectPrim, Style, Subpath, TextLine, TextPrim, TextRun, Vec2, resolve,
)
from inklet.render import save_svg, to_svg

SVG = "{http://www.w3.org/2000/svg}"
XLINK = "{http://www.w3.org/1999/xlink}"
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"
DRAWABLE = {"rect", "circle", "ellipse", "path", "text", "image"}

_TRANSFORM = re.compile(r"(matrix|translate|scale)\(([^)]*)\)")


# -- helpers --------------------------------------------------------------


def parse(svg: str) -> ET.Element:
    return ET.fromstring(svg)


def tag(el: ET.Element) -> str:
    return el.tag.removeprefix(SVG)


def transform_of(el: ET.Element) -> Affine:
    """The element's transform, whichever of the three spellings it used.

    `matrix(1 0 0 1 x y)` and `translate(x y)` are the same six numbers; the
    renderer writes whichever is shorter, so a reader of the file has to
    understand both.
    """
    raw = el.get("transform")
    if raw is None:
        return Affine()
    match = _TRANSFORM.match(raw)
    assert match, f"expected a transform function, got {raw!r}"
    kind = match.group(1)
    values = [float(v) for v in match.group(2).replace(",", " ").split()]
    if kind == "matrix":
        return Affine(*values)
    if kind == "translate":
        return Affine.translation(values[0], values[1] if len(values) > 1 else 0.0)
    return Affine.scaling(values[0], values[1] if len(values) > 1 else None)


def placed_elements(root: ET.Element, world: Affine = Affine(), depth: int = 0):
    """Every element with its accumulated world transform and nesting depth."""
    for child in root:
        child_world = world @ transform_of(child)
        yield child, child_world, depth + 1
        yield from placed_elements(child, child_world, depth + 1)


def nodes_by_id(root: ET.Element) -> dict[str, tuple[ET.Element, Affine, int]]:
    """Where each `Diagram` node landed in the file, by its id.

    One element per node, not necessarily a `<g>`: a leaf and its wrapper are
    written as a single element, so a lone rectangle comes back as the `<rect>`
    that carries its id rather than as a group around one.
    """
    found = {}
    for el, world, depth in placed_elements(root):
        node_id = el.get("id")
        if node_id is not None and node_id != "inklet-background":
            found[node_id] = (el, world, depth)
    return found


def shape(el: ET.Element, name: str) -> ET.Element:
    """The element a node drew: itself when the leaf folded into one element,
    otherwise the child of its group."""
    return el if tag(el) == name else el.find(SVG + name)


def rect_hull(el: ET.Element, world: Affine) -> Rect:
    x, y = float(el.get("x")), float(el.get("y"))
    box = Rect(x, y, x + float(el.get("width")), y + float(el.get("height")))
    return box.transform(world)


def coords(rect: Rect) -> tuple[float, float, float, float]:
    return (rect.x0, rect.y0, rect.x1, rect.y1)


def approx(rect: Rect, tol: float = 1e-9):
    return pytest.approx(coords(rect), abs=tol)


def box(w=20.0, h=10.0, **kw) -> Diagram:
    return Diagram(prim=RectPrim(w, h), kind="box", **kw)


def three_levels() -> tuple[Diagram, Diagram, Diagram]:
    inner = box(10, 6, name="inner")
    middle = Diagram(children=(inner,), kind="grp", name="middle",
                     transform=Affine.translation(5, 0))
    outer = Diagram(children=(middle,), kind="grp", name="outer",
                    transform=Affine.translation(0, 8))
    return outer, middle, inner


# -- document ------------------------------------------------------------


def test_root_is_svg_with_namespaces():
    root = parse(to_svg(box()))
    assert tag(root) == "svg"
    assert root.tag == SVG + "svg"
    assert 'xmlns:xlink="http://www.w3.org/1999/xlink"' in to_svg(box())


def test_canvas_follows_bbox_and_margin():
    svg = to_svg(box(20, 10).translated(30, 20), margin=2.0)
    root = parse(svg)
    assert root.get("width") == "24mm"
    assert root.get("height") == "14mm"
    # bbox is x 20..40, y 15..25; margin grows it by 2 on every side.
    assert root.get("viewBox") == "18 13 24 14"


def test_width_height_end_in_mm_and_match_viewbox():
    svg = to_svg(box(20, 10), width="89mm", height="4.2cm", margin=1.0)
    root = parse(svg)
    x0, y0, w, h = (float(v) for v in root.get("viewBox").split())
    assert root.get("width").endswith("mm") and root.get("height").endswith("mm")
    assert float(root.get("width")[:-2]) == w == 89.0
    assert float(root.get("height")[:-2]) == h == 42.0
    # Explicit sizes keep the content's own bbox origin rather than recentring.
    assert (x0, y0) == (-11.0, -6.0)


def test_title_and_background():
    svg = to_svg(box(), title="Figure 1", background="#ffffff", margin=1.0)
    root = parse(svg)
    assert tag(root[0]) == "title" and root[0].text == "Figure 1"
    bg = root[1]
    assert tag(bg) == "rect" and bg.get("fill") == "#ffffff"
    assert (bg.get("width"), bg.get("height")) == (root.get("width")[:-2],
                                                   root.get("height")[:-2])


def test_no_title_or_background_by_default():
    root = parse(to_svg(box()))
    assert [tag(el) for el in root] == ["rect"]


def test_save_svg_round_trips(tmp_path):
    path = tmp_path / "fig.svg"
    diagram = box()
    save_svg(diagram, str(path), margin=1.0)
    assert path.read_text(encoding="utf-8") == to_svg(diagram, margin=1.0)
    assert tag(ET.parse(path).getroot()) == "svg"


# -- tree shape ----------------------------------------------------------


def test_group_nesting_mirrors_the_diagram_tree():
    """One element per node, at the node's own depth.

    A wrapper is a `<g>`; a leaf *is* its shape, because a group around a
    single shape is a second DOM node doing the first one's work. Either way
    the element carries the node's id and sits where the node sits.
    """
    outer, middle, inner = three_levels()
    nodes = nodes_by_id(parse(to_svg(outer)))
    assert nodes[outer.id][2] == 1
    assert nodes[middle.id][2] == 2
    assert nodes[inner.id][2] == 3
    assert [tag(nodes[n.id][0]) for n in (outer, middle, inner)] \
        == ["g", "g", "rect"]
    # And the rect is inside the innermost wrapper, not on the root.
    assert [tag(el) for el in nodes[middle.id][0]] == ["rect"]


def test_every_node_id_appears_exactly_once():
    outer, _, _ = three_levels()
    ids = [el.get("id") for el, _, _ in placed_elements(parse(to_svg(outer)))
           if el.get("id") is not None]
    expected = [node.id for node in outer.walk()]
    assert sorted(ids) == sorted(expected)
    assert len(ids) == len(set(ids)) == len(expected)


def test_flat_output_would_not_pass_this():
    """Deeply stacked translations stay nested, one element per wrapper."""
    d = box().translated(1, 0).translated(0, 2).translated(3, 0)
    depths = {depth for el, _, depth in placed_elements(parse(to_svg(d)))}
    assert depths == {1, 2, 3, 4}


def test_name_becomes_data_name_and_is_omitted_otherwise():
    named, unnamed = box(name="hero"), box()
    root = parse(to_svg(Diagram(children=(named, unnamed))))
    groups = nodes_by_id(root)
    assert groups[named.id][0].get("data-name") == "hero"
    assert groups[unnamed.id][0].get("data-name") is None


def test_identity_transform_emits_no_transform_attribute():
    d = box()
    groups = nodes_by_id(parse(to_svg(d)))
    assert groups[d.id][0].get("transform") is None


def test_prim_paints_before_children():
    """A node with both a prim and children keeps its group: the prim paints
    first, then the children over it. Only a leaf folds."""
    child = box(4, 4)
    parent = Diagram(prim=RectPrim(20, 10), children=(child,), kind="box")
    nodes = nodes_by_id(parse(to_svg(parent)))
    assert [tag(el) for el in nodes[parent.id][0]] == ["rect", "rect"]
    assert nodes[child.id][0].get("width") == "4"


# -- geometry ------------------------------------------------------------


def test_translated_rect_lands_where_resolve_says():
    rect_node = box(20, 10)
    root = rect_node.translated(30, 20)
    placements = resolve(root)

    groups = nodes_by_id(parse(to_svg(root)))
    el, world, _ = groups[rect_node.id]
    drawn = shape(el, "rect")
    assert coords(rect_hull(drawn, world)) == approx(placements[rect_node.id].bbox)
    assert coords(rect_hull(drawn, world)) == approx(Rect(20.0, 15.0, 40.0, 25.0))


def test_rotated_and_scaled_rect_matches_resolve():
    """Also pins the matrix() argument order: a b c d e f, outermost last."""
    rect_node = box(20, 10)
    root = rect_node.rotated(30).scaled(2.0).translated(5, -3)
    placements = resolve(root)

    groups = nodes_by_id(parse(to_svg(root, precision=9)))
    el, world, _ = groups[rect_node.id]
    drawn = shape(el, "rect")
    assert coords(rect_hull(drawn, world)) == approx(placements[rect_node.id].bbox, 1e-6)


def test_default_precision_places_shapes_within_a_micron():
    rect_node = box(20, 10)
    root = rect_node.rotated(30).translated(5.00047, -3.00051)
    placements = resolve(root)

    el, world, _ = nodes_by_id(parse(to_svg(root)))[rect_node.id]
    drawn = shape(el, "rect")
    assert coords(rect_hull(drawn, world)) == approx(placements[rect_node.id].bbox, 2e-3)


def test_rect_is_centred_on_its_local_origin():
    drawn = parse(to_svg(box(20, 10))).find(f"{SVG}rect")
    assert (drawn.get("x"), drawn.get("y")) == ("-10", "-5")
    assert (drawn.get("width"), drawn.get("height")) == ("20", "10")
    assert drawn.get("rx") is None


def test_rect_radius_becomes_rx():
    drawn = parse(to_svg(Diagram(prim=RectPrim(20, 10, 1.5)))).find(f"{SVG}rect")
    assert drawn.get("rx") == "1.5"


def test_style_corner_radius_applies_when_the_prim_has_none():
    d = Diagram(prim=RectPrim(20, 10)).styled(corner_radius=2.0)
    drawn = parse(to_svg(d)).find(f"{SVG}rect")
    assert drawn.get("rx") == "2"
    # It is not a presentation attribute; it must not leak onto the group.
    assert parse(to_svg(d))[0].get("corner-radius") is None


def test_equal_radii_emit_a_circle():
    drawn = parse(to_svg(Diagram(prim=EllipsePrim(6, 6))))[0]
    assert tag(drawn) == "circle"
    assert (drawn.get("cx"), drawn.get("cy"), drawn.get("r")) == ("0", "0", "6")


def test_unequal_radii_emit_an_ellipse():
    drawn = parse(to_svg(Diagram(prim=EllipsePrim(6, 3))))[0]
    assert tag(drawn) == "ellipse"
    assert (drawn.get("rx"), drawn.get("ry")) == ("6", "3")


# -- paths ---------------------------------------------------------------


def test_polyline_path_data_and_no_fill():
    d = Diagram(prim=PathPrim.polyline([Vec2(0, 0), Vec2(10, 0), Vec2(10, 5)]))
    drawn = parse(to_svg(d))[0]
    assert tag(drawn) == "path"
    assert drawn.get("d") == "M 0 0 L 10 0 L 10 5"
    assert drawn.get("fill") == "none"


def test_closed_filled_path():
    sub = Subpath((Vec2(0, 0), Vec2(10, 0), Vec2(5, 8)), closed=True)
    drawn = parse(to_svg(Diagram(prim=PathPrim((sub,), filled=True))))[0]
    assert drawn.get("d").endswith(" Z")
    assert drawn.get("fill") is None  # filled means "use the inherited fill"


def test_curves_emit_real_cubics():
    curves = ((Vec2(0, 0), Vec2(2, -4), Vec2(8, -4), Vec2(10, 0)),
              (Vec2(10, 0), Vec2(12, 4), Vec2(18, 4), Vec2(20, 0)))
    flattened = (Vec2(0, 0), Vec2(5, -3), Vec2(10, 0), Vec2(15, 3), Vec2(20, 0))
    sub = Subpath(flattened, closed=False, curves=curves)
    drawn = parse(to_svg(Diagram(prim=PathPrim((sub,)))))[0]
    assert drawn.get("d") == ("M 0 0 C 2 -4 8 -4 10 0 C 12 4 18 4 20 0")


def test_disjoint_curve_segments_get_an_explicit_lineto():
    curves = ((Vec2(0, 0), Vec2(1, 0), Vec2(2, 0), Vec2(3, 0)),
              (Vec2(5, 0), Vec2(6, 0), Vec2(7, 0), Vec2(8, 0)))
    sub = Subpath((Vec2(0, 0), Vec2(8, 0)), curves=curves)
    drawn = parse(to_svg(Diagram(prim=PathPrim((sub,)))))[0]
    assert "L 5 0" in drawn.get("d")


def test_multiple_subpaths_share_one_path_element():
    subs = (Subpath((Vec2(0, 0), Vec2(4, 0))), Subpath((Vec2(0, 4), Vec2(4, 4))))
    drawn = parse(to_svg(Diagram(prim=PathPrim(subs))))[0]
    assert drawn.get("d") == "M 0 0 L 4 0 M 0 4 L 4 4"


# -- text ----------------------------------------------------------------


def text_prim(lines=(("Hello", 12.0, 0.0), ("world", 8.0, 3.5)), align="center"):
    return TextPrim(
        lines=tuple(TextLine(t, adv, base) for t, adv, base in lines),
        font_family="Inter", font_size=2.8, ascent=2.0, descent=0.6, align=align,
    )


def test_text_is_one_element_with_absolutely_positioned_tspans():
    prim = text_prim()
    el = parse(to_svg(Diagram(prim=prim)))[0][0]
    assert tag(el) == "text"
    assert el.get("font-family") == "Inter"
    assert el.get("font-size") == "2.8"
    # The document says `xml:space="preserve"` once, on the root; a block
    # whose lines survive whitespace collapsing does not restate it.
    assert el.get(XML_SPACE) is None
    assert el.get("text-anchor") is None  # advances are exact; we place lines ourselves

    spans = list(el)
    assert [tag(s) for s in spans] == ["tspan", "tspan"]
    # height 6.1 -> first baseline -1.05; block is 12 wide, centred on the origin.
    assert [s.get("y") for s in spans] == ["-1.05", "2.45"]
    assert [s.get("x") for s in spans] == ["-6", "-4"]
    assert [s.text for s in spans] == ["Hello", "world"]


def test_a_line_set_in_two_fonts_becomes_one_tspan_each():
    """Part of a line can be set in a font the block does not name, because the
    one it names has no glyph for it. Each span carries its own x -- the
    advances were measured per run, so the position is arithmetic rather than a
    guess about what the viewer will fall back to -- and its own family only
    when that is not the one the `<text>` already names."""
    line = TextLine("ab CJK", 12.0, 0.0, 0.0, (
        TextRun("ab ", "Inter", 4.0),
        TextRun("CJK", "WenQuanYi Zen Hei", 8.0),
    ))
    prim = TextPrim(lines=(line,), font_family="Inter", font_size=2.8,
                    ascent=2.0, descent=0.6, align="start")
    el = parse(to_svg(Diagram(prim=prim)))[0][0]

    assert el.get("font-family") == "Inter"
    spans = list(el)
    assert [s.text for s in spans] == ["ab ", "CJK"]
    assert [s.get("font-family") for s in spans] == [None, "WenQuanYi Zen Hei"]
    # The block is 12 wide and centred, so it starts at -6; the second run
    # starts one first-run advance further along.
    assert [s.get("x") for s in spans] == ["-6", "-2"]


def test_run_positions_carry_the_justified_space_stretch():
    """`word-spacing` is applied by the viewer, so a run following one has to
    be pushed along by it too or the two disagree about where the line is."""
    line = TextLine("a b CJK", 14.0, 0.0, 0.5, (
        TextRun("a b ", "Inter", 4.0),
        TextRun("CJK", "WenQuanYi Zen Hei", 8.0),
    ))
    prim = TextPrim(lines=(line,), font_family="Inter", font_size=2.8,
                    ascent=2.0, descent=0.6, align="start")
    spans = list(parse(to_svg(Diagram(prim=prim)))[0][0])

    assert all(s.get("word-spacing") == "0.5" for s in spans)
    # 4.0 of advance plus two spaces stretched by 0.5 each.
    assert [s.get("x") for s in spans] == ["-7", "-2"]


def test_a_single_font_line_stays_a_single_tspan():
    """The ordinary case must not grow an attribute; nothing about a plain
    Latin line changed."""
    el = parse(to_svg(Diagram(prim=text_prim())))[0][0]
    assert all(s.get("font-family") is None for s in el)


def test_text_alignment_uses_line_offset():
    for align, xs in (("start", ["-6", "-6"]), ("end", ["-6", "-2"])):
        el = parse(to_svg(Diagram(prim=text_prim(align=align))))[0][0]
        assert [s.get("x") for s in el] == xs


def test_text_stays_text():
    svg = to_svg(Diagram(prim=text_prim()))
    assert parse(svg).find(f"{SVG}g/{SVG}text") is not None
    assert svg.count("<path") == 0


def test_markup_characters_round_trip():
    raw = 'a & b < c > d "quoted" é'
    prim = text_prim(lines=((raw, 20.0, 0.0),))
    el = parse(to_svg(Diagram(prim=prim)))[0][0]
    assert el.text == raw          # one line, so no tspan to hold it


def test_markup_characters_in_names_and_families_are_escaped():
    d = box(name='q"&<').styled(font_family='My "Font" & Co')
    root = parse(to_svg(d))
    assert root[0].get("data-name") == 'q"&<'
    assert root[0].get("font-family") == 'My "Font" & Co'


def test_text_fill_lands_on_the_text_not_the_group():
    d = Diagram(prim=text_prim()).styled(fill="#eeeeee", text_fill="#111111")
    group = parse(to_svg(d))[0]
    assert group.get("fill") == "#eeeeee"
    assert group.get("text-fill") is None
    assert group[0].get("fill") == "#111111"


def test_empty_text_emits_nothing():
    prim = TextPrim(lines=(), font_family="Inter", font_size=2.8,
                    ascent=2.0, descent=0.6)
    d = Diagram(children=(box(), Diagram(prim=prim)))
    assert parse(to_svg(d)).findall(f".//{SVG}text") == []


# -- style ---------------------------------------------------------------


def test_unset_style_fields_are_omitted_entirely():
    """No defaults are invented: an unstyled node carries no presentation
    attribute at all, only its id and whatever geometry its shape needs."""
    d = box()
    drawn = parse(to_svg(d))[0]
    assert set(drawn.keys()) == {"id", "x", "y", "width", "height"}


def test_style_lands_on_the_group_and_children_inherit():
    child = box(4, 4)
    parent = Diagram(children=(child,)).styled(
        fill="#eef", stroke="#123456", stroke_width=0.25,
        stroke_dash=(1.0, 0.5), stroke_linecap="round", stroke_linejoin="bevel",
        opacity=0.5, font_weight="bold",
    )
    root = parse(to_svg(parent))
    group = root[0]
    assert group.get("fill") == "#eef"
    assert group.get("stroke-width") == "0.25"
    assert group.get("stroke-dasharray") == "1,0.5"
    assert group.get("stroke-linecap") == "round"
    assert group.get("stroke-linejoin") == "bevel"
    assert group.get("opacity") == "0.5"
    assert group.get("font-weight") == "bold"
    # Inheritance is SVG's job: the child repeats nothing.
    assert set(nodes_by_id(root)[child.id][0].keys()) \
        == {"id", "x", "y", "width", "height"}


def test_child_style_overrides_only_what_it_sets():
    child = box(4, 4).styled(fill="#f00")
    parent = Diagram(children=(child,)).styled(fill="#eef", stroke="#000")
    group = nodes_by_id(parse(to_svg(parent)))[child.id][0]
    assert group.get("fill") == "#f00"
    assert group.get("stroke") is None


def test_attribute_order_is_fixed():
    d = box(name="n").styled(fill="#eee", stroke="#000", stroke_width=0.2)
    svg = to_svg(Diagram(children=(d,), transform=Affine.translation(1, 1)))
    line = next(ln for ln in svg.splitlines() if f'id="{d.id}"' in ln)
    keys = re.findall(r'([a-zA-Z:-]+)="', line)
    # The node's own attributes first, in a fixed order; the shape's geometry
    # after them, because the leaf and its wrapper are one element.
    assert keys[:5] == ["id", "data-name", "fill", "stroke", "stroke-width"]
    assert keys[5:] == ["x", "y", "width", "height"]


# -- compact -------------------------------------------------------------


_ARITY = {"M": 2, "L": 2, "C": 6, "Z": 0, "H": 1, "V": 1}


def path_commands(data: str) -> list[tuple[str, list[float]]]:
    """Path data read back as absolute commands, with every elision expanded.

    A real reader, small enough to trust: an omitted letter repeats the last
    one, except after a moveto where it becomes a lineto; a lower-case letter
    means the numbers are offsets from where the pen is; `h` and `v` are
    linetos with one of the two left out; and `z` puts the pen back on the
    subpath's first point. Comparing this against the spelled-out form is what
    proves the packed spelling is the same curve rather than merely the same
    digits in the same order.
    """
    tokens = re.findall(r"[A-Za-z]|-?\d*\.\d+|-?\d+", data)
    out: list[tuple[str, list[float]]] = []
    letter, at = "", 0
    x = y = start_x = start_y = 0.0
    while at < len(tokens):
        if tokens[at].isalpha():
            letter, at = tokens[at], at + 1
        elif letter in ("M", "m"):
            letter = "L" if letter == "M" else "l"
        upper = letter.upper()
        assert upper in _ARITY, f"unreadable path data at {tokens[at]!r}"
        take = _ARITY[upper]
        values = [float(v) for v in tokens[at:at + take]]
        at += take
        relative = letter.islower()
        if upper == "Z":
            out.append(("Z", []))
            x, y = start_x, start_y
            continue
        if upper == "H":
            x = x + values[0] if relative else values[0]
            out.append(("L", [x, y]))
            continue
        if upper == "V":
            y = y + values[0] if relative else values[0]
            out.append(("L", [x, y]))
            continue
        points = []
        for index in range(0, take, 2):
            points += [values[index] + (x if relative else 0.0),
                       values[index + 1] + (y if relative else 0.0)]
        if upper == "M":
            start_x, start_y = points[0], points[1]
        x, y = points[-2], points[-1]
        out.append((upper, points))
    return out


def _same_document(a: ET.Element, b: ET.Element) -> None:
    """Two SVG trees that draw the same thing, whatever the spelling."""
    assert a.tag == b.tag
    left, right = dict(a.attrib), dict(b.attrib)
    assert path_commands(left.pop("d", "")) == path_commands(right.pop("d", ""))
    assert left == right
    assert (a.text or "").strip() == (b.text or "").strip()
    assert len(a) == len(b)
    for mine, theirs in zip(a, b):
        _same_document(mine, theirs)


def test_compact_is_the_same_document_with_less_of_it():
    """Same elements, same attributes, same numbers, fewer bytes.

    The packed path grammar is the part worth pinning: a repeated command
    letter may be dropped, the pairs after a moveto are implicit linetos, and
    no separator is needed before a minus sign. Get any of those wrong and the
    picture changes silently, which is why this compares the parsed numbers
    rather than the strings.
    """
    d = Diagram(children=(
        box(20, 10, name="a").translated(-3, 2).styled(fill="#eef"),
        Diagram(prim=PathPrim((Subpath((Vec2(-1, -2), Vec2(3, -4), Vec2(5, 6)),
                                       closed=True),), filled=True)),
        Diagram(prim=PathPrim((Subpath((), closed=False, curves=(
            (Vec2(0, 0), Vec2(1, 1), Vec2(2, 1), Vec2(3, 0)),
            (Vec2(3, 0), Vec2(4, -1), Vec2(5, -1), Vec2(6, 0)),
        )),))),
    ))
    plain = to_svg(d, margin=1.0, compact=False)
    packed = to_svg(d, margin=1.0, compact=True)
    _same_document(parse(plain), parse(packed))
    assert len(packed) < len(plain)
    assert "\n  " not in packed                     # no indentation left
    assert 'd="m-1-2 4-2 2 10z"' in packed           # relative implicit linetos
    # One `c` for two cubics: the letter is written once and the second
    # command's six numbers simply follow the first's.
    assert 'd="m0 0c1 1 2 1 3 0 1-1 2-1 3 0"' in packed


# -- phantoms and images -------------------------------------------------


def test_phantom_draws_nothing():
    phantom = Diagram(prim=PhantomPrim(Rect(-5, -5, 5, 5)), kind="pad")
    root = parse(to_svg(Diagram(children=(phantom, box()))))
    drawables = [tag(el) for el, _, _ in placed_elements(root) if tag(el) in DRAWABLE]
    assert drawables == ["rect"]
    # Its group still exists, so the tree keeps its shape; it is simply empty.
    assert list(nodes_by_id(root)[phantom.id][0]) == []


def test_phantom_still_contributes_to_the_canvas():
    phantom = Diagram(prim=PhantomPrim(Rect(-30, -5, 30, 5)))
    root = parse(to_svg(Diagram(children=(phantom, box(4, 4)))))
    assert root.get("width") == "60mm"


def test_image_is_embedded_as_a_data_uri(tmp_path):
    payload = b"\x89PNG\r\n\x1a\n-not-a-real-png"
    source = tmp_path / "photo.png"
    source.write_bytes(payload)
    d = Diagram(prim=ImagePrim(str(source), 40.0, 30.0, pixel_size=(400, 300)))
    el = parse(to_svg(d))[0][0]
    assert tag(el) == "image"
    assert (el.get("x"), el.get("y")) == ("-20", "-15")
    assert (el.get("width"), el.get("height")) == ("40", "30")
    href = el.get(XLINK + "href")
    assert href.startswith("data:image/png;base64,")
    assert base64.b64decode(href.split(",", 1)[1]) == payload


def test_a_prim_carrying_its_own_bytes_never_touches_the_filesystem():
    """A heatmap computed into an array has no file behind it, and writing one
    out only so the backend can read it back makes the figure depend on a
    temporary file. `source` is then a label, so the type comes from the magic
    number rather than from the suffix."""
    payload = b"\x89PNG\r\n\x1a\n-generated"
    prim = ImagePrim("panel c matrix", 40.0, 30.0, data=payload)
    svg = to_svg(Diagram(prim=prim))
    href = parse(svg)[0][0].get(XLINK + "href")
    assert href.startswith("data:image/png;base64,")
    assert base64.b64decode(href.split(",", 1)[1]) == payload
    assert "not embedded" not in svg


def test_generated_jpeg_bytes_are_recognised_by_their_magic_number():
    prim = ImagePrim("label", 4.0, 3.0, data=b"\xff\xd8\xff-generated")
    href = parse(to_svg(Diagram(prim=prim)))[0][0].get(XLINK + "href")
    assert href.startswith("data:image/jpeg;base64,")


def test_carried_bytes_win_over_a_file_of_the_same_name(tmp_path):
    source = tmp_path / "photo.png"
    source.write_bytes(b"\x89PNG\r\n\x1a\n-on-disk")
    prim = ImagePrim(str(source), 4.0, 3.0, data=b"\x89PNG\r\n\x1a\n-in-memory")
    href = parse(to_svg(Diagram(prim=prim)))[0][0].get(XLINK + "href")
    assert b"in-memory" in base64.b64decode(href.split(",", 1)[1])


def test_a_raster_that_is_data_is_sampled_nearest_neighbour():
    """A heatmap drawn one pixel per cell is data, not a photograph: bilinear
    resampling invents values between the cells and blurs a boundary the
    reader is meant to be able to point at."""
    prim = ImagePrim("matrix", 40.0, 30.0, data=b"\x89PNG\r\n\x1a\n-x")
    node = Diagram(prim=prim, kind="raster-matrix")
    el = parse(to_svg(node))[0][0]
    assert el.get("image-rendering") == "pixelated"
    assert "crisp-edges" in el.get("style")


def test_a_prim_can_overrule_the_role_it_was_placed_under():
    """`smooth` defaults to `None` -- no opinion, the kind decides -- so that
    a field nobody sets cannot silently start smoothing every heatmap. Stated,
    it wins in both directions."""
    raw = b"\x89PNG\r\n\x1a\n-x"
    photo = Diagram(prim=ImagePrim("m", 4.0, 3.0, data=raw, smooth=True),
                    kind="raster-matrix")
    assert parse(to_svg(photo))[0][0].get("image-rendering") is None
    cells = Diagram(prim=ImagePrim("m", 4.0, 3.0, data=raw, smooth=False))
    assert parse(to_svg(cells))[0][0].get("image-rendering") == "pixelated"


def test_an_ordinary_photograph_is_left_to_the_viewer():
    prim = ImagePrim("photo", 40.0, 30.0, data=b"\x89PNG\r\n\x1a\n-x")
    el = parse(to_svg(Diagram(prim=prim)))[0][0]
    assert el.get("image-rendering") is None


def test_missing_image_falls_back_to_a_link(tmp_path):
    missing = str(tmp_path / "gone.png")
    svg = to_svg(Diagram(prim=ImagePrim(missing, 10.0, 10.0)))
    el = parse(svg)[0][0]
    assert el.get(XLINK + "href") == missing
    assert "image not embedded" in svg


# -- numbers and determinism ---------------------------------------------


def test_negative_zero_never_appears():
    d = Diagram(prim=RectPrim(20, 10), transform=Affine.rotation(-180.0))
    d = d.translated(-0.0001, -0.0)
    svg = to_svg(d, margin=0.0004)
    assert "-0" not in svg
    assert "e-" not in svg  # and no scientific notation, which SVG cannot read


def test_precision_is_honoured():
    d = box(1 / 3, 1 / 7)
    assert parse(to_svg(d, precision=2))[0].get("width") == "0.33"
    assert parse(to_svg(d, precision=5))[0].get("width") == "0.33333"
    assert parse(to_svg(d, precision=0))[0].get("width") == "0"


def test_trailing_zeros_are_stripped():
    drawn = parse(to_svg(box(20.0, 10.500)))[0]
    assert (drawn.get("width"), drawn.get("height")) == ("20", "10.5")


def test_non_finite_numbers_are_refused():
    with pytest.raises(ValueError):
        to_svg(box(float("nan"), 10))


def test_same_tree_renders_byte_identically():
    outer, _, _ = three_levels()
    outer = outer.styled(fill="#eee", stroke_dash=(1.0, 0.5))
    assert to_svg(outer, margin=2, title="t", background="#fff") == \
        to_svg(outer, margin=2, title="t", background="#fff")


def test_rebuilt_tree_differs_only_in_ids():
    def render():
        outer, _, _ = three_levels()
        return to_svg(outer.styled(fill="#eee"), margin=2)

    first, second = render(), render()
    assert first != second  # ids really are fresh, so the check below has teeth
    strip = lambda s: re.sub(r'(id="[a-z]+)\d+"', r'\1"', s)
    assert strip(first) == strip(second)


def test_output_is_pure_ascii_lines():
    svg = to_svg(box(), margin=1)
    assert "\r" not in svg
    assert svg.endswith("\n")
    assert svg.startswith('<?xml version="1.0" encoding="UTF-8"?>\n')


# -- degenerate input ----------------------------------------------------


def test_empty_diagram_still_renders():
    root = parse(to_svg(Diagram(), margin=3.0))
    assert root.get("width") == "6mm"
    assert [tag(el) for el in root] == ["g"]
