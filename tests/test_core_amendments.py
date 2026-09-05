"""The core amendments M6-M18, one section each.

Written as behaviour: what a caller can now say, and what must not have moved
because of it. The envelope section is the important one -- it pins numerical
identity, not closeness, because the whole justification for caching a hull is
that the answer is the same float.
"""

from __future__ import annotations

import math
import random
import struct

import pytest

from inklet.core import (
    EAST, NORTH, ORIGIN, SOUTH, WEST,
    Affine, AnchorRef, Diagram, DiagramError, Envelope, ImagePrim, PathPrim,
    Rect, RectPrim, Style, StyleError, TextLine, TextPrim, TextRun, Vec2,
    flatten, pt, resolve, text_features, world_point,
)
from inklet.core.envelope import _hull


def bits(x: float) -> bytes:
    """A float compared as a float, not as a number: -0.0 and 0.0 differ."""
    return struct.pack("<d", x)


def directions(n: int = 64):
    return [Vec2(math.cos(a), math.sin(a))
            for a in (2 * math.pi * i / n for i in range(n))]


# -- M6: an image that is not a file --------------------------------------


def test_an_image_can_carry_its_own_bytes_instead_of_a_path():
    png = b"\x89PNG\r\n\x1a\n" + b"pretend this is a heatmap"
    prim = ImagePrim("heatmap", 40.0, 30.0, pixel_size=(400, 300), data=png)
    assert prim.data == png
    assert prim.source == "heatmap"          # a label, not a path
    assert prim.rect == Rect.from_size(40.0, 30.0)
    assert prim.effective_dpi() == pytest.approx(254.0)


def test_an_image_without_bytes_is_what_it_always_was():
    prim = ImagePrim("scan.png", 40.0, 30.0, pixel_size=(400, 300))
    assert prim.data is None
    assert prim.envelope().bbox() == Rect.from_size(40.0, 30.0)


def test_bytes_do_not_change_the_geometry_of_an_outlined_image():
    outline = (Vec2(-5, -2), Vec2(5, -2), Vec2(0, 6))
    plain = ImagePrim("x", 20.0, 20.0, outline=outline)
    with_data = ImagePrim("x", 20.0, 20.0, outline=outline, data=b"\x89PNG")
    assert plain.envelope().bbox() == with_data.envelope().bbox()
    assert plain.trace().exit(Vec2(0, 0), EAST) == \
        with_data.trace().exit(Vec2(0, 0), EAST)


def test_smoothing_is_unstated_until_someone_states_it():
    """The default must be `None`, not `True`: a backend that falls back to a
    node's kind when nothing is stated keeps doing so, and the caller that
    wants nearest-neighbour says False."""
    assert ImagePrim("scan.png", 10.0, 10.0).smooth is None
    assert ImagePrim("matrix", 10.0, 10.0, smooth=False).smooth is False
    assert ImagePrim("photo", 10.0, 10.0, smooth=True).smooth is True


def test_sampling_is_not_geometry():
    plain = ImagePrim("m", 12.0, 8.0, pixel_size=(6, 4))
    crisp = ImagePrim("m", 12.0, 8.0, pixel_size=(6, 4), smooth=False)
    assert plain.envelope().bbox() == crisp.envelope().bbox()
    assert plain.effective_dpi() == crisp.effective_dpi()


def test_data_keeps_its_position_after_smooth_was_added():
    """Positional construction is part of the shape of a frozen dataclass."""
    prim = ImagePrim("m", 10.0, 10.0, (8, 8), (), b"\x89PNG", False)
    assert prim.data == b"\x89PNG" and prim.smooth is False


# -- M7: a colour per run -------------------------------------------------


def coloured_line():
    return TextLine(
        "cells were red", 30.0, 0.0,
        runs=(TextRun("cells were ", "Inter", 22.0),
              TextRun("red", "Inter", 8.0, fill="#d55e00")),
    )


def test_a_run_can_carry_its_own_colour():
    runs = coloured_line().runs
    assert runs[0].fill is None                 # inherits the text node's fill
    assert runs[1].fill == "#d55e00"


def test_colouring_a_run_moves_no_measurement():
    plain = TextLine("cells were red", 30.0, 0.0)
    prim_plain = TextPrim((plain,), "Inter", 3.0, 2.2, 0.8)
    prim_coloured = TextPrim((coloured_line(),), "Inter", 3.0, 2.2, 0.8)
    assert prim_plain.width == prim_coloured.width
    assert prim_plain.height == prim_coloured.height
    assert prim_plain.envelope().bbox() == prim_coloured.envelope().bbox()


# -- M8: the hull, and the memo -------------------------------------------


def test_the_hull_drops_the_points_that_can_never_be_furthest():
    square = [Vec2(0, 0), Vec2(10, 0), Vec2(10, 10), Vec2(0, 10)]
    inside = [Vec2(3, 4), Vec2(5, 5), Vec2(7, 2)]
    hull = _hull(tuple(square + inside))
    assert sorted(hull) == sorted((p.x, p.y) for p in square)


def test_a_straight_run_of_points_hulls_to_its_two_ends():
    line = tuple(Vec2(i, 2 * i) for i in range(9))
    assert _hull(line) == ((0.0, 0.0), (8.0, 16.0))


def test_the_hull_answers_with_the_same_float_as_the_whole_cloud():
    """The gate for M8: identical bits, not just identical to a tolerance."""
    rng = random.Random(20260823)
    for _ in range(40):
        cloud = tuple(Vec2(rng.uniform(-50, 50), rng.uniform(-30, 30))
                      for _ in range(120))
        hull = _hull(cloud)
        for v in directions():
            over_hull = max(x * v.x + y * v.y for x, y in hull)
            over_cloud = max(p.dot(v) for p in cloud)
            assert bits(over_hull) == bits(over_cloud)


def test_a_concave_outline_still_reports_its_true_extremes():
    # An L: the hull is not the shape, but a support function never claimed
    # to describe one -- only how far it reaches.
    ell = [Vec2(0, 0), Vec2(10, 0), Vec2(10, 4), Vec2(4, 4),
           Vec2(4, 10), Vec2(0, 10)]
    env = Envelope.from_points(ell)
    assert env.bbox() == Rect(0.0, 0.0, 10.0, 10.0)
    assert env.extent(Vec2(1, 1).normalized()) == pytest.approx(9.899, abs=1e-3)


def test_one_point_is_its_own_envelope():
    env = Envelope.from_points([Vec2(3, -4)])
    assert env.bbox() == Rect(3.0, -4.0, 3.0, -4.0)
    assert env.extent(EAST) == 3.0


def test_asking_twice_gives_the_identical_answer():
    env = Envelope.from_points([Vec2(0, 0), Vec2(7, 3), Vec2(-2, 9)])
    first = [env.extent(v) for v in directions(16)]
    second = [env.extent(v) for v in directions(16)]
    assert [bits(x) for x in first] == [bits(x) for x in second]
    assert env.bbox() == env.bbox()


def test_the_memo_survives_being_wrapped_in_a_transform():
    """`transform` reads the inner envelope through its memo, so the inner
    answer a parent gets must be the one an unwrapped query gets."""
    env = Envelope.from_points([Vec2(-4, -1), Vec2(6, -1), Vec2(6, 5)])
    moved = env.transform(Affine.translation(3.0, 2.0))
    assert bits(moved.extent(EAST)) == bits(env.extent(EAST) + 3.0)
    assert moved.bbox() == Rect(-1.0, 1.0, 9.0, 7.0)


def test_an_envelope_is_still_hashable_and_compares_on_its_support():
    env = Envelope.from_points([Vec2(0, 0), Vec2(1, 1)])
    env.bbox()                                   # populates the cache
    assert env == Envelope(env.support)          # the cache is not identity
    assert hash(env) == hash(Envelope(env.support))


def test_a_padded_envelope_still_sweeps_a_disc():
    env = Envelope.from_rect(Rect(-5, -5, 5, 5)).pad(2.0)
    assert env.extent(EAST) == pytest.approx(7.0)
    assert env.extent(Vec2(1, 1).normalized()) == pytest.approx(5 * math.sqrt(2) + 2)


# -- M9: reprs that name a node instead of dumping it ---------------------


def test_a_node_reprs_as_one_line():
    leaf = Diagram(prim=RectPrim(4, 2), kind="box", name="laser")
    text = repr(leaf)
    assert text.startswith("Diagram(box 'laser' box")
    assert text.endswith(", RectPrim)")
    assert "\n" not in text


def test_a_parent_reports_how_many_children_it_has_not_what_they_are():
    kids = tuple(Diagram(prim=RectPrim(1, 1), kind="box") for _ in range(3))
    parent = Diagram(children=kids, kind="stack")
    assert repr(parent).endswith(", 3 children)")
    assert "RectPrim" not in repr(parent)
    assert len(repr(parent)) < 60


def test_one_child_is_singular():
    parent = Diagram(children=(Diagram(kind="box"),), kind="place")
    assert repr(parent).endswith(", 1 child)")


def test_an_anchor_ref_names_its_node_rather_than_printing_it():
    deep = Diagram(prim=RectPrim(4, 2), kind="box", name="laser")
    for _ in range(6):
        deep = Diagram(children=(deep,), kind="place")
    ref = AnchorRef(deep, "n")
    assert repr(ref) == f"AnchorRef(place {deep.id}, 1 child, 'n')"
    assert len(repr(ref)) < 60


# -- M10: the compass of a rotated node -----------------------------------


def test_the_north_of_a_rotated_node_is_the_north_of_the_box_you_can_see():
    label = Diagram(prim=RectPrim(40, 10), kind="box")
    turned = label.rotated(30)
    box = turned.bbox
    north = world_point(turned.at("n"), resolve(turned))
    assert north.y == pytest.approx(box.y0)
    assert north.x == pytest.approx(box.center.x)


def test_a_registered_anchor_still_travels_with_the_shape():
    photo = Diagram(prim=RectPrim(40, 10), kind="img")
    photo.anchor("ear", Vec2(20, -5))            # its own top-right corner
    turned = photo.rotated(90)
    where = world_point(AnchorRef(photo, "ear"), resolve(turned))
    # A quarter turn clockwise on a downward y: (20, -5) -> (5, 20).
    assert (where.x, where.y) == pytest.approx((5.0, 20.0))


def test_an_upright_node_answers_exactly_as_it_always_did():
    node = Diagram(prim=RectPrim(40, 10), kind="box").translated(7.0, 3.0)
    places = resolve(node)
    for anchor in ("center", "n", "s", "e", "w", "ne", "nw", "se", "sw"):
        placed = places[node.id]
        expected = placed.world.apply(node.anchor_point(anchor))
        got = placed.point(anchor)
        assert bits(got.x) == bits(expected.x)
        assert bits(got.y) == bits(expected.y)


def test_anchor_point_itself_is_still_local():
    turned = Diagram(prim=RectPrim(40, 10), kind="box").rotated(30)
    assert turned.anchor_point("n") == Vec2(0.0, -5.0)


def test_an_unknown_compass_name_still_lists_what_there_is():
    node = Diagram(prim=RectPrim(4, 2), kind="box")
    places = resolve(node)
    with pytest.raises(DiagramError, match="no anchor 'up'"):
        places[node.id].point("up")


# -- M11: the documented rules, exercised ---------------------------------

# The rules M11 wrote down are exercised by the sections around it: the
# fill-rule pin that lived here has been replaced by M14, which grants the
# field it was watching for.


# -- M13: the features a block was shaped with ----------------------------


def test_a_text_prim_records_no_features_by_default():
    prim = TextPrim((TextLine("hi", 8.0, 0.0),), "Sans", 3.0, 2.2, 0.7)
    assert prim.features == ()


def test_features_arrive_as_sorted_immutable_pairs():
    """Sorted, and `True` narrowed to the 1 an OpenType value actually is --
    the same bytes `typeset.feature_key` produces, not merely the same `==`."""
    assert text_features({"tnum": True, "liga": False}) == (
        ("liga", 0), ("tnum", 1))
    assert repr(text_features({"tnum": True})) == "(('tnum', 1),)"
    assert text_features([("tnum", 1)]) == (("tnum", 1),)
    assert text_features(None) == () and text_features({}) == ()


def test_two_callers_asking_for_the_same_features_build_equal_prims():
    """A dict keeps the order it was typed in; a shaper does not care."""
    one = TextPrim((), "Sans", 3.0, 2.2, 0.7,
                   features=text_features({"tnum": True, "kern": True}))
    other = TextPrim((), "Sans", 3.0, 2.2, 0.7,
                     features=text_features({"kern": True, "tnum": True}))
    assert one == other


def test_inklet_text_records_what_it_shaped_with():
    import inklet

    prim = inklet.text("0123456789", size=10, features={"tnum": True}).prim
    assert prim.features == (("tnum", True),)


def test_the_recorded_features_reshape_to_the_same_advance():
    """The 2.8mm drift this field exists to prevent, measured both ways.

    Ten tabular digits shaped with `tnum` and re-shaped from what the prim
    remembers must come out the same width; re-shaped with the shaper's
    defaults they need not, and on most families they do not.
    """
    import inklet

    prim = inklet.text("0123456789", size=10, features={"tnum": True}).prim
    again = inklet.shape("0123456789", size=10, features=dict(prim.features))
    assert again.width == prim.width


def test_recording_features_moves_nothing_that_measures():
    lines = (TextLine("hi", 8.0, 0.0),)
    plain = TextPrim(lines, "Sans", 3.0, 2.2, 0.7)
    tabular = TextPrim(lines, "Sans", 3.0, 2.2, 0.7, features=(("tnum", True),))
    assert tabular.width == plain.width and tabular.height == plain.height
    assert tabular.envelope().bbox() == plain.envelope().bbox()


# -- M14: a fill rule for a path ------------------------------------------


def test_a_path_fills_nonzero_unless_it_says_otherwise():
    assert PathPrim(()).fill_rule == "nonzero"
    assert PathPrim((), True, "evenodd").fill_rule == "evenodd"


def test_an_unknown_fill_rule_is_refused_where_it_is_written():
    with pytest.raises(ValueError, match="nonzero, evenodd"):
        PathPrim((), True, "even-odd")


def test_the_fill_rule_is_not_geometry():
    square = (Vec2(-1, -1), Vec2(1, -1), Vec2(1, 1), Vec2(-1, 1))
    plain = PathPrim.polyline(square, closed=True, filled=True)
    holed = PathPrim.polyline(square, closed=True, filled=True,
                              fill_rule="evenodd")
    assert plain.envelope().bbox() == holed.envelope().bbox()
    for d in directions(16):
        assert (bits(plain.trace().boundary_point(ORIGIN, d).x)
                == bits(holed.trace().boundary_point(ORIGIN, d).x))


def test_flatten_hands_the_rule_through_untouched():
    prim = PathPrim.polyline((Vec2(0, 0), Vec2(2, 0), Vec2(1, 2)),
                             closed=True, filled=True, fill_rule="evenodd")
    item, = flatten(Diagram(prim=prim, kind="path").translated(5, 0))
    assert item.prim is prim and item.prim.fill_rule == "evenodd"


# -- M15: the four holes in Style -----------------------------------------


def test_the_new_style_fields_default_to_inheriting():
    style = Style()
    assert style.fill_opacity is None and style.stroke_opacity is None
    assert style.font_style is None
    assert style.halo is None and style.halo_color is None
    assert style.is_empty


def test_a_band_can_be_a_soft_fill_under_a_solid_stroke():
    band = Style(fill="#4c72b0", fill_opacity=0.2, stroke_opacity=1.0)
    assert band.fill_opacity == 0.2 and band.stroke_opacity == 1.0
    assert band.opacity is None


def test_a_halo_is_a_length_like_every_other_length():
    assert Style(halo="0.4mm").halo == 0.4
    assert Style(halo=pt(1)).halo == pytest.approx(0.3528, abs=1e-4)
    with pytest.raises(StyleError, match="halo must be a length"):
        Style(halo="thick")


def test_font_style_takes_the_two_answers_there_are():
    assert Style(font_style="italic").font_style == "italic"
    assert Style(font_style="normal").font_style == "normal"
    with pytest.raises(StyleError, match="font_style must be one of"):
        Style(font_style="oblique")


def test_an_opacity_that_is_not_a_number_is_refused_at_the_door():
    with pytest.raises(StyleError, match="fill_opacity must be a number"):
        Style(fill_opacity="20%")


def test_the_new_fields_inherit_by_the_same_rule_as_the_old_ones():
    base = Style(fill_opacity=0.2, font_style="italic", halo=0.4,
                 halo_color="#fff")
    mine = Style(fill="red", halo=0.8)
    merged = mine.over(base)
    assert merged.fill == "red"
    assert merged.halo == 0.8            # self wins where set
    assert merged.halo_color == "#fff"   # base fills the rest
    assert merged.fill_opacity == 0.2 and merged.font_style == "italic"


# -- M16: an anchor that survives being turned ----------------------------


def turned_marker() -> tuple[Diagram, Diagram]:
    """A shape with a registered tip, and that shape rotated a quarter turn."""
    node = Diagram(prim=RectPrim(20, 6), kind="mark")
    node.anchor("tip", Vec2(10, 0))
    return node, node.rotated(90)


def test_a_tip_travels_through_the_wrapper_a_rotation_leaves_behind():
    """`anchor_point` is local, so the turn shows one frame out.

    A wrapper's own transform is not applied to its own answer -- that is what
    local means, and it is why `turned.anchor_point` reads the same as the
    node's. Put anything above it and the rotation is in the answer.
    """
    node, turned = turned_marker()
    assert node.anchor_point("tip") == Vec2(10.0, 0.0)
    got = turned.translated(0, 5).anchor_point("tip")
    assert got.x == pytest.approx(0.0, abs=1e-9)
    assert got.y == pytest.approx(10.0)


def test_it_travels_through_nested_wrappers_too():
    node, turned = turned_marker()
    got = turned.translated(5, 1).scaled(2).anchor_point("tip")
    assert got.x == pytest.approx(5.0, abs=1e-9)
    assert got.y == pytest.approx(11.0)


def test_a_placement_finds_the_tip_of_a_rotated_child():
    node, turned = turned_marker()
    tree = Diagram(children=(turned.translated(30, 30),), kind="page")
    places = resolve(tree)
    assert world_point(turned.at("tip"), places).y == pytest.approx(40.0)


def test_a_compass_name_is_never_looked_up_in_a_child():
    """A side of a box is not a point of a shape, so it is answered here."""
    node = Diagram(prim=RectPrim(20, 6), kind="mark")
    node.anchor("e", Vec2(0, 99))
    assert node.translated(4, 0).anchor_point("e") == Vec2(10.0, 0.0)


def test_a_group_of_many_children_answers_for_none_of_them():
    """Five drawn shapes in a stack have five origins and no shared one."""
    left = Diagram(prim=RectPrim(4, 4), kind="a")
    left.anchor("origin", Vec2(1, 1))
    right = Diagram(prim=RectPrim(4, 4), kind="b").translated(10)
    group = Diagram(children=(left, right), kind="row")
    with pytest.raises(DiagramError, match="no anchor 'origin'"):
        group.anchor_point("origin")


def test_the_error_lists_the_names_a_wrapper_would_have_found():
    node, turned = turned_marker()
    with pytest.raises(DiagramError, match="tip"):
        turned.anchor_point("nose")


def test_as_drawn_still_asks_the_node_it_was_handed():
    """The wrapper is a placement someone meant; undoing it would move the page.

    Reaching through it moved `stress/electro_figure.py` 6.5mm when the
    look-through first landed, which is why `as_drawn` reads `anchors`.
    """
    from inklet.draw import as_drawn

    inner = Diagram(prim=RectPrim(4, 4), kind="mark")
    inner.anchor("origin", Vec2(2, 2))
    wrapper = inner.translated(30, 0)
    assert as_drawn(wrapper) is wrapper
    assert as_drawn(inner).transform.e == -2.0


# -- M17: a place to put what core has no opinion on ----------------------


def test_a_note_reads_back_and_chains():
    node = Diagram(prim=RectPrim(4, 2), kind="stack").note("gap", 6.0)
    assert node.notes["gap"] == 6.0
    assert node.note("axis", "x") is node


def test_a_note_is_not_part_of_what_makes_two_nodes_equal():
    plain = Diagram(prim=RectPrim(4, 2), kind="stack")
    noted = Diagram(prim=RectPrim(4, 2), kind="stack").note("gap", 6.0)
    assert plain == noted


def test_notes_follow_a_node_through_styling_naming_and_copying():
    node = Diagram(prim=RectPrim(4, 2), kind="stack").note("gap", 6.0)
    for derived in (node.styled(fill="red"), node.named("row"), node.copy()):
        assert derived.notes["gap"] == 6.0
    node.styled(fill="red").note("gap", 99.0)
    assert node.notes["gap"] == 6.0, "a derived node keeps its own notes"


def test_a_note_survives_the_replace_that_apply_theme_is_built_on():
    """The point of a field rather than an attribute: no name to special-case."""
    from dataclasses import replace as dc_replace

    node = Diagram(prim=RectPrim(4, 2), kind="stack").note("gap", 6.0)
    assert dc_replace(node, kind="row").notes["gap"] == 6.0


def test_a_note_survives_a_figure_being_built():
    import inklet

    inner = inklet.box("a").note("gap", 6.0)
    fig = inklet.figure(width="89mm")
    fig.add(inklet.hstack([inner, inklet.box("b")], gap=6))
    built, _ = fig.build()
    carrying = [n for n in built.walk() if n.notes.get("gap") is not None]
    # Three nodes carry it, and each for its own reason: the box, which is
    # where the note was written; the `hstack`, which writes one for the gap
    # it was given (layout's round-3 change); and the `place` wrapper the
    # figure puts round the stack, which gets a copy because M19 makes a note
    # travel with the node through `placed`. What the test is about is that
    # none of the three overwrote the box's own.
    assert [n.kind for n in carrying] == ["place", "stack", "framed"]
    assert all(n.notes["gap"] == 6.0 for n in carrying)
    assert built.find("a").notes["gap"] == 6.0
