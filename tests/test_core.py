"""Core geometry, envelopes, traces and tree resolution.

These are the invariants every other module builds on, so they are pinned to
exact numbers rather than to whatever the implementation happens to return.
"""

from __future__ import annotations

import math

import pytest

import inklet

from inklet.core import (
    EAST, IDENTITY, NORTH, ORIGIN, SOUTH, WEST,
    Affine, Diagram, DiagramError, EllipsePrim, Envelope, PathPrim, PhantomPrim,
    Rect, RectPrim, Style, TextLine, TextPrim, Trace, Vec2,
    flatten, mm, pt, resolve, to_pt, world_point,
)

SQRT2 = math.sqrt(2.0)


def rect(w=20.0, h=10.0, **kw):
    return Diagram(prim=RectPrim(w, h), kind="box", **kw)


def circle(r=10.0, **kw):
    return Diagram(prim=EllipsePrim(r, r), kind="dot", **kw)


# -- units ----------------------------------------------------------------


def test_lengths_parse_to_millimetres():
    assert mm(12) == 12.0
    assert mm("12mm") == 12.0
    assert mm("1cm") == 10.0
    assert mm("1in") == 25.4
    assert mm("72pt") == pytest.approx(25.4)
    assert mm("  -3.5 mm ") == -3.5


def test_points_round_trip():
    assert to_pt(pt(7.0)) == pytest.approx(7.0)
    assert pt(7.0) == pytest.approx(2.4694, abs=1e-4)


def test_bad_length_is_rejected_by_name():
    with pytest.raises(ValueError, match="furlong"):
        mm("3 furlong")


# -- affine ---------------------------------------------------------------


def test_matmul_applies_the_right_operand_first():
    move = Affine.translation(10.0, 0.0)
    spin = Affine.rotation(90.0)
    # spin @ move: translate, then rotate about the origin.
    p = (spin @ move).apply(ORIGIN)
    assert (p.x, p.y) == pytest.approx((0.0, 10.0), abs=1e-9)
    # move @ spin: rotate first, so the origin stays put and then shifts.
    q = (move @ spin).apply(ORIGIN)
    assert (q.x, q.y) == pytest.approx((10.0, 0.0), abs=1e-9)


def test_inverse_round_trips():
    t = Affine.translation(3, -4) @ Affine.rotation(31.0) @ Affine.scaling(2.0, 0.5)
    p = Vec2(7.0, -2.0)
    back = t.inverse().apply(t.apply(p))
    assert (back.x, back.y) == pytest.approx((p.x, p.y), abs=1e-9)


def test_singular_transform_has_no_inverse():
    with pytest.raises(ValueError, match="singular"):
        Affine.scaling(0.0, 1.0).inverse()


# -- envelopes ------------------------------------------------------------


def test_envelope_of_a_circle_is_the_radius_in_every_direction():
    c = circle(10.0)
    for direction in (EAST, NORTH, Vec2(1, 1).normalized(), Vec2(-3, 7).normalized()):
        assert c.extent(direction) == pytest.approx(10.0, abs=1e-9)


def test_envelope_beats_bbox_where_they_disagree():
    """The point of the whole abstraction: a circle and its bounding square
    have identical boxes but different reach on the diagonal."""
    diagonal = Vec2(1, 1).normalized()
    assert circle(10.0).extent(diagonal) == pytest.approx(10.0)
    assert rect(20.0, 20.0).extent(diagonal) == pytest.approx(10.0 * SQRT2)


def test_envelope_survives_rotation_and_translation():
    spun = rect(20.0, 10.0).rotated(45.0)
    # Corner (10, 5) projects onto +x at (10 + 5) / sqrt(2).
    assert spun.extent(EAST) == pytest.approx(15.0 / SQRT2, abs=1e-9)
    shifted = spun.translated(100.0, 0.0)
    assert shifted.extent(EAST) == pytest.approx(100.0 + 15.0 / SQRT2, abs=1e-9)
    assert shifted.extent(WEST) == pytest.approx(15.0 / SQRT2 - 100.0, abs=1e-9)


def test_empty_envelope_is_the_identity_for_union():
    empty = Envelope.empty()
    solid = Envelope.from_rect(Rect(-1, -1, 1, 1))
    assert empty.union(solid).bbox() == solid.bbox()
    assert solid.union(empty).bbox() == solid.bbox()
    assert empty.union(empty).is_empty


def test_padding_grows_uniformly():
    padded = Envelope.from_rect(Rect(-10, -5, 10, 5)).pad(2.0)
    assert padded.bbox() == Rect(-12, -7, 12, 7)
    assert padded.extent(Vec2(1, 1).normalized()) == pytest.approx(
        Envelope.from_rect(Rect(-10, -5, 10, 5)).extent(Vec2(1, 1).normalized()) + 2.0
    )


def test_bbox_is_exact_for_a_concave_union():
    left = Envelope.from_rect(Rect(-10, -1, -5, 1))
    right = Envelope.from_rect(Rect(5, -1, 10, 1))
    assert left.union(right).bbox() == Rect(-10, -1, 10, 1)


# -- traces ---------------------------------------------------------------


def test_ray_leaves_a_circle_at_the_radius():
    hit = circle(10.0).trace.boundary_point(ORIGIN, EAST)
    assert (hit.x, hit.y) == pytest.approx((10.0, 0.0), abs=1e-9)


def test_ray_leaves_a_rect_on_the_correct_edge():
    box = rect(20.0, 10.0)
    assert box.trace.boundary_point(ORIGIN, EAST).x == pytest.approx(10.0)
    assert box.trace.boundary_point(ORIGIN, SOUTH).y == pytest.approx(5.0)
    corner = box.trace.boundary_point(ORIGIN, Vec2(1, 1).normalized())
    assert (corner.x, corner.y) == pytest.approx((5.0, 5.0), abs=1e-9)


def test_a_ray_crosses_every_sibling_in_a_wide_group():
    """Unioning traces pairwise down a fold nested one closure per sibling, and
    re-sorted the hit list at every level. Both are gone; the answer is not."""
    row = Diagram(children=tuple(
        circle(1.0).translated(float(i) * 10.0, 0.0) for i in range(800)))

    hits = row.trace.hits(Vec2(-50.0, 0.0), EAST)

    assert len(hits) == 1600                      # in and out of each circle
    assert list(hits) == sorted(hits)
    assert hits[0] == pytest.approx(49.0)         # near edge of the first
    assert hits[-1] == pytest.approx(50.0 + 799 * 10.0 + 1.0)


def test_trace_follows_a_transformed_shape():
    moved = rect(20.0, 10.0).translated(50.0, 0.0)
    hit = moved.trace.boundary_point(Vec2(50.0, 0.0), WEST)
    assert (hit.x, hit.y) == pytest.approx((40.0, 0.0), abs=1e-9)


def test_exit_takes_the_far_crossing_of_a_concave_outline():
    """Two disjoint boxes on one axis: a ray from the origin must leave through
    the far side of the far box, not the near side of the near one."""
    outline = Trace.from_polygon(Rect(-2, -1, 2, 1).corners).union(
        Trace.from_polygon(Rect(6, -1, 10, 1).corners)
    )
    assert outline.exit(ORIGIN, EAST) == pytest.approx(10.0)
    assert outline.enter(ORIGIN, EAST) == pytest.approx(2.0)


def test_a_ray_that_misses_reports_nothing():
    assert circle(10.0).trace.boundary_point(Vec2(0, 100), EAST) is None


def test_phantom_occupies_space_but_catches_no_rays():
    ghost = Diagram(prim=PhantomPrim(Rect(-5, -5, 5, 5)))
    assert ghost.bbox == Rect(-5, -5, 5, 5)
    assert ghost.trace.is_empty
    assert ghost.trace.boundary_point(ORIGIN, EAST) is None


# -- the tree -------------------------------------------------------------


def test_placement_wraps_so_the_caller_keeps_a_live_handle():
    inner = rect()
    outer = Diagram(children=(inner.translated(30.0, 5.0),))
    places = resolve(outer)
    assert inner.id in places
    assert (places[inner.id].point().x, places[inner.id].point().y) == pytest.approx(
        (30.0, 5.0)
    )


def test_transforms_accumulate_down_the_tree():
    leaf = rect()
    tree = Diagram(children=(Diagram(children=(leaf.translated(10, 0),)).translated(5, 3),))
    where = resolve(tree)[leaf.id].point()
    assert (where.x, where.y) == pytest.approx((15.0, 3.0))


def test_placing_one_diagram_twice_is_an_error_not_a_silent_win():
    shared = rect()
    tree = Diagram(children=(shared.translated(0, 0), shared.translated(50, 0)))
    with pytest.raises(DiagramError, match="more than once"):
        resolve(tree)
    # The documented escape hatch works.
    resolve(Diagram(children=(shared.translated(0, 0), shared.copy().translated(50, 0))))


def test_a_copy_keeps_its_attachments_inside_itself():
    """A panel holds its shapes and the links clipped to them in one subtree.
    Copying it onto a page renumbers both, and an arrow left pointing at the
    original is an arrow the linter no longer believes touches anything."""
    a, b = rect(), rect().translated(40.0, 0.0)
    link = Diagram(kind="link", attached_to=(a.id, b.id))
    panel = Diagram(children=(a, b, link), kind="panel")

    clone = panel.copy()
    ids = {node.id for node in clone.walk()}
    copied_link = next(n for n in clone.walk() if n.kind == "link")

    assert set(copied_link.attached_to) <= ids
    assert copied_link.attached_to != link.attached_to


def test_a_copy_leaves_attachments_pointing_out_of_itself_alone():
    """Two placements of one connector still touch the shape it names: an id
    from outside the subtree was not renumbered, so it still means what it
    said."""
    outside = rect()
    link = Diagram(kind="link", attached_to=(outside.id,))

    assert link.copy().attached_to == (outside.id,)


def test_compass_anchors_respect_a_downward_y_axis():
    box = rect(20.0, 10.0)
    assert box.anchor_point("n") == Vec2(0.0, -5.0)
    assert box.anchor_point("s") == Vec2(0.0, 5.0)
    assert box.anchor_point("ne") == Vec2(10.0, -5.0)
    assert box.anchor_point("center") == ORIGIN


def test_fractional_anchors_are_measured_from_the_top_left():
    box = rect(20.0, 10.0).anchor("ear", (0.25, 0.0))
    ear = box.anchor_point("ear")
    # A quarter across a 20mm-wide box starting at x = -10, and flush to the top.
    assert (ear.x, ear.y) == pytest.approx((-5.0, -5.0))


def test_unknown_anchor_lists_what_is_available():
    with pytest.raises(DiagramError, match="no anchor 'snout'"):
        rect().anchor_point("snout")


def test_anchor_resolves_to_world_space_after_layout():
    mouse = rect(20.0, 10.0).anchor("ear", (0.25, 0.0))
    figure = Diagram(children=(mouse.translated(100.0, 100.0),))
    p = world_point(mouse.at("ear"), resolve(figure))
    assert (p.x, p.y) == pytest.approx((95.0, 95.0))


def test_linking_to_something_outside_the_figure_says_so():
    with pytest.raises(DiagramError, match="not part of this figure"):
        world_point(rect().at("n"), resolve(Diagram(children=(rect(),))))


def test_style_inherits_downward_and_the_child_wins():
    leaf = rect().styled(stroke="#f00")
    tree = Diagram(children=(leaf,)).styled(stroke="#00f", fill="#eee")
    style = resolve(tree)[leaf.id].style
    assert style.stroke == "#f00"
    assert style.fill == "#eee"


def test_flatten_paints_a_node_before_its_children():
    parent = Diagram(prim=RectPrim(30, 30), children=(rect(),), kind="frame")
    order = [item.prim for item in flatten(parent)]
    assert isinstance(order[0], RectPrim) and order[0].width == 30
    assert len(order) == 2


def test_phantom_and_empty_nodes_survive_resolution():
    tree = Diagram(children=(Diagram(), Diagram(prim=PhantomPrim(Rect(0, 0, 1, 1)))))
    assert len(resolve(tree)) == 3


def test_empty_diagram_reports_a_useful_error_for_its_bbox():
    with pytest.raises(DiagramError, match="empty"):
        Diagram().bbox


# -- text prims (constructed by hand; inklet.typeset owns real shaping) ---------


def test_text_block_is_centred_on_its_origin():
    prim = TextPrim(
        lines=(TextLine("one", 12.0, 0.0), TextLine("two", 8.0, 3.0)),
        font_family="sans", font_size=2.5, ascent=2.0, descent=0.6,
    )
    assert prim.width == 12.0
    assert prim.height == pytest.approx(2.0 + 3.0 + 0.6)
    box = prim.envelope().bbox()
    assert box.center.x == pytest.approx(0.0)
    assert box.center.y == pytest.approx(0.0)
    assert prim.first_baseline == pytest.approx(-prim.height / 2 + 2.0)


def test_centred_alignment_indents_short_lines_by_half_the_slack():
    prim = TextPrim(
        lines=(TextLine("wide", 12.0, 0.0), TextLine("s", 4.0, 3.0)),
        font_family="sans", font_size=2.5, ascent=2.0, descent=0.6, align="center",
    )
    assert prim.line_offset(prim.lines[0]) == pytest.approx(0.0)
    assert prim.line_offset(prim.lines[1]) == pytest.approx(4.0)


# -- determinism ----------------------------------------------------------


def test_identical_construction_gives_identical_geometry():
    def build():
        a, b = rect(), circle()
        return Diagram(children=(a.translated(0, 0), b.translated(40, 0)))

    first = [(p.bbox.x0, p.bbox.y0, p.bbox.x1, p.bbox.y1)
             for p in resolve(build()).values() if p.bbox]
    second = [(p.bbox.x0, p.bbox.y0, p.bbox.x1, p.bbox.y1)
              for p in resolve(build()).values() if p.bbox]
    assert first == second


# -- style validation ------------------------------------------------------


def test_style_coerces_dash_strings_and_sequences():
    from inklet import Style
    assert Style(stroke_dash="2,1").stroke_dash == (2.0, 1.0)
    assert Style(stroke_dash="2 1").stroke_dash == (2.0, 1.0)
    assert Style(stroke_dash=[1, 2]).stroke_dash == (1.0, 2.0)
    assert Style(stroke_dash=("1mm", "1pt")).stroke_dash[0] == 1.0
    assert Style(stroke_width="1pt").stroke_width == inklet.pt(1)


def test_style_refuses_unusable_values_at_construction():
    from inklet import Style, StyleError
    for bad in (dict(stroke_dash="dashed"), dict(stroke_dash=3),
                dict(stroke_dash=(1, -1)), dict(stroke_dash=()),
                dict(opacity="half"), dict(stroke_width="thick"),
                dict(line_height=True)):
        with pytest.raises(StyleError):
            Style(**bad)


def test_merging_styles_keeps_the_coerced_values():
    # `over` skips validation because both sides were checked when built; the
    # invariant it relies on is that a merge cannot introduce a raw value.
    from inklet import Style
    merged = Style(stroke_dash="2,1").over(Style(stroke_width="1pt"))
    assert merged.stroke_dash == (2.0, 1.0)
    assert merged.stroke_width == inklet.pt(1)
    assert merged == Style(stroke_dash=(2.0, 1.0), stroke_width=inklet.pt(1))


def test_dash_string_survives_to_svg():
    # The failure this guards against: a clean lint, then a crash in the writer.
    a, b = inklet.box("a"), inklet.box("b")
    fig = inklet.figure(width=60)
    fig.add(inklet.hstack([a, b], gap=10))
    fig.link(a, b, stroke_dash="1.2,0.8")
    assert fig.lint() == []
    assert 'stroke-dasharray="1.2,0.8"' in fig.to_svg()
