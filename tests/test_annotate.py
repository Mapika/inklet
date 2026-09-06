"""Labels that clear what they name, and the furniture that goes with them.

The numbers here are geometry, not implementation: how far a label sits off a
silhouette, which side it moved to when the first one was blocked, whether a
leader stops on the boundary or in the middle of the shape. Those are the
claims `inklet.annotate` makes, and they are the ones a figure is wrong without.
"""

from __future__ import annotations

import pytest

import inklet
from inklet import Rect, Vec2
from inklet.draw.annotate import (ANNOTATION_LABEL_KIND, LETTER_KIND,
                               annotation_side)
from inklet.links import CONNECTOR_KIND, LINK_KIND

TH = inklet.theme("nature")


def label_box(node: inklet.Diagram) -> Rect:
    """Where the annotation's label ended up, in the annotation's own frame."""
    placements = inklet.resolve(node)
    for child in node.walk():
        if child.kind == ANNOTATION_LABEL_KIND:
            return placements[child.id].bbox
    raise AssertionError("no annotation label in this tree")


def leader_of(node: inklet.Diagram):
    for child in node.walk():
        if child.kind == LINK_KIND:
            return child
    return None


def shaft_points(node: inklet.Diagram) -> list[Vec2]:
    placements = inklet.resolve(node)
    for child in node.walk():
        if child.kind == CONNECTOR_KIND:
            world = placements[child.id].world
            return [world.apply(p) for p in child.prim.subpaths[0].points]
    raise AssertionError("no leader shaft in this tree")


# -- clearance ------------------------------------------------------------


@pytest.mark.parametrize("side,axis,sign", [
    ("n", "y", -1.0), ("s", "y", 1.0), ("e", "x", 1.0), ("w", "x", -1.0),
])
def test_a_label_sits_the_asked_for_distance_off_its_target(side, axis, sign):
    box = inklet.box("sample")
    art = inklet.annotate(box, "here", side=side, clear=3.0)
    target = inklet.resolve(art)[box.id].bbox
    label = label_box(art)

    if axis == "x":
        gap = (label.x0 - target.x1) if sign > 0 else (target.x0 - label.x1)
    else:
        gap = (label.y0 - target.y1) if sign > 0 else (target.y0 - label.y1)
    assert gap == pytest.approx(3.0)


def test_clearance_is_measured_off_the_silhouette_not_the_corner():
    """An ellipse reaches less far on the diagonal than its box does.

    A bbox-based clearance would put a north-east label 3mm off an empty
    corner, which is 3mm plus however much the curve falls short -- 4.1mm here
    for a 20 x 10 ellipse. The support function is what makes the number mean
    what it says.
    """
    ellipse = inklet.circle(inklet.spacer(), width=20, height=10)
    art = inklet.annotate(ellipse, "x", side="ne", clear=3.0, leader=False)
    label = label_box(art)

    direction = Vec2(2.0 ** -0.5, -(2.0 ** -0.5))
    reach = inklet.resolve(art)[ellipse.id].envelope.extent(direction)
    # The label's own supporting line along -direction: its nearest corner.
    near = min(corner.dot(direction) for corner in label.corners)
    assert near - reach == pytest.approx(3.0, abs=1e-6)

    box = inklet.resolve(art)[ellipse.id].bbox
    assert reach < max(c.dot(direction) for c in box.corners) - 1.0


def test_the_leader_stops_on_the_boundary_of_the_shape():
    circle = inklet.circle(inklet.spacer(), width=20, height=20)
    art = inklet.annotate(circle, "cell", side="e", clear=4.0)
    start = shaft_points(art)[0]
    centre = inklet.resolve(art)[circle.id].bbox.center

    assert (start - centre).length == pytest.approx(10.0, abs=0.05)


def test_the_leader_stops_short_of_its_own_label():
    box = inklet.box("a")
    art = inklet.annotate(box, "name", side="e", clear=3.0)
    end = shaft_points(art)[-1]
    assert end.x < label_box(art).x0 - 1e-9


def test_a_label_pressed_against_its_target_gets_no_leader():
    """A 0.2mm stub is a speck of dirt, not a line."""
    box = inklet.box("a")
    art = inklet.annotate(box, "name", side="e", clear=0.2)
    assert leader_of(art) is None


def test_leader_can_be_switched_off():
    box = inklet.box("a")
    assert leader_of(inklet.annotate(box, "n", side="e", leader=False)) is None


# -- choosing a side ------------------------------------------------------


def test_a_blocked_side_moves_and_says_so():
    box = inklet.box("a")
    blocker = Rect(-30.0, -30.0, 30.0, -2.0)      # everything north of the box
    art = inklet.annotate(box, "name", side="n", clear=2.0, avoid=[blocker])

    assert annotation_side(art) != "n"
    assert label_box(art).overlap(blocker) is None


def test_the_side_search_is_deterministic_and_symmetric():
    """North blocked tries north-east before north-west, every time."""
    box = inklet.box("a")
    north = Rect(-3.0, -30.0, 3.0, -2.0)
    art = inklet.annotate(box, "x", side="n", clear=2.0, avoid=[north])
    assert annotation_side(art) == "ne"

    again = inklet.annotate(inklet.box("a"), "x", side="n", clear=2.0, avoid=[north])
    assert annotation_side(again) == "ne"


def test_an_unblocked_label_keeps_the_side_it_was_given():
    box = inklet.box("a")
    art = inklet.annotate(box, "name", side="sw", clear=2.0)
    assert annotation_side(art) == "sw"


def test_labels_placed_earlier_are_avoided_without_being_asked():
    left = inklet.box("L").named("L")
    right = inklet.box("R").named("R")
    row = inklet.hstack([left, right], gap=1.0)

    art = inklet.annotate(left, "a very long first label", side="n", within=row)
    art = inklet.annotate(right, "a very long second label", side="n", within=art)

    boxes = [inklet.resolve(art)[n.id].bbox for n in art.walk()
             if n.kind == ANNOTATION_LABEL_KIND]
    assert len(boxes) == 2
    assert boxes[0].overlap(boxes[1]) is None


# -- what it works on -----------------------------------------------------


def test_annotating_a_part_needs_the_frame_it_lives_in():
    inner = inklet.box("part").named("part")
    outer = inklet.hstack([inner, inklet.box("other")], gap=4)
    with pytest.raises(inklet.DiagramError):
        inklet.annotate(inner, "x", side="n", within=inklet.box("elsewhere"))

    art = inklet.annotate(outer.find("part"), "x", side="n", within=outer)
    assert label_box(art).y1 < inklet.resolve(art)[inner.id].bbox.y0


def test_an_anchor_ref_is_labelled_at_the_exact_spot():
    box = inklet.box("a")
    art = inklet.annotate(box.at("ne"), "corner", side="ne", clear=2.0)
    corner = inklet.resolve(art)[box.id].bbox
    label = label_box(art)
    assert label.x0 > corner.x1 - 1e-9 or label.y1 < corner.y0 + 1e-9


def test_the_caller_keeps_their_handle_on_the_target():
    box = inklet.box("a")
    art = inklet.annotate(box, "name", side="n")
    assert box.id in inklet.resolve(art)


def test_a_drawn_frame_keeps_its_origin_through_annotate():
    """`Panel.draw` and `place` both put a drawn node back where it was drawn."""
    frame = inklet.place([((10.0, 4.0), inklet.marker("circle", 2).named("dot"))],
                      origin=(0, 0))
    art = inklet.annotate(frame.find("dot"), "spot", side="n", within=frame)
    assert inklet.draw.ORIGIN_ANCHOR in art.anchors


def test_annotate_is_deterministic():
    """Same inputs, same geometry -- twice, from scratch."""
    def build():
        art = inklet.annotate(inklet.box("a"), "label", side="e", clear=3.0)
        return label_box(art), shaft_points(art)

    assert build() == build()


def test_an_unknown_side_is_refused():
    with pytest.raises(ValueError, match="unknown side"):
        inklet.annotate(inklet.box("a"), "x", side="up")


# -- brackets -------------------------------------------------------------


def test_a_bracket_spans_its_two_points_with_ticks_turned_inward():
    node = inklet.bracket((0.0, 0.0), (20.0, 0.0), side="n", tick=1.5)
    box = inklet.draw.as_drawn(node).bbox
    assert box.x0 == pytest.approx(0.0)
    assert box.x1 == pytest.approx(20.0)
    # The bar is on the line, the ticks hang below it towards the content.
    assert box.y1 == pytest.approx(1.5)


def test_a_bracket_carries_its_label_clear_of_the_bar():
    plain = inklet.draw.as_drawn(inklet.bracket((0, 0), (20, 0), side="n")).bbox
    marked = inklet.draw.as_drawn(
        inklet.bracket((0, 0), (20, 0), side="n", text="***")).bbox
    assert marked.y0 < plain.y0
    assert marked.x0 == pytest.approx(plain.x0)


def test_a_bracket_between_diagrams_spans_their_facing_edges():
    left = inklet.box("L").named("L")
    right = inklet.box("R").named("R")
    row = inklet.hstack([left, right], gap=8)
    node = inklet.draw.as_drawn(inklet.bracket(row.find("L"), row.find("R"),
                                         side="n", within=row))
    boxes = [inklet.resolve(row)[n.id].bbox for n in (left, right)]
    assert node.bbox.x0 == pytest.approx(boxes[0].center.x)
    assert node.bbox.x1 == pytest.approx(boxes[1].center.x)


def test_a_bracket_side_must_be_a_cardinal_point():
    with pytest.raises(ValueError, match="bracket side"):
        inklet.bracket((0, 0), (1, 0), side="ne")


# -- dimensions -----------------------------------------------------------


def test_a_dimension_line_is_offset_and_ticked_at_both_ends():
    node = inklet.draw.as_drawn(inklet.dimension((0, 0), (30, 0), offset=-5,
                                           tick=2.0))
    box = node.bbox
    assert box.x0 == pytest.approx(0.0)
    assert box.x1 == pytest.approx(30.0)
    # The line sits 5mm above; the ticks reach 1mm either side of it, and the
    # witness lines run all the way back down to the points being measured.
    assert box.y0 == pytest.approx(-6.0)
    assert box.y1 == pytest.approx(0.0)


def test_a_dimension_label_rides_on_the_line():
    node = inklet.draw.as_drawn(inklet.dimension((0, 0), (30, 0), "30 mm"))
    assert node.bbox.center.x == pytest.approx(15.0, abs=1e-6)


def test_dimension_witness_lines_accept_explicit_stroke_width():
    node=inklet.dimension((0,0),(30,0),'30',offset=5,stroke_width=.45)
    lines=[p for p in inklet.resolve(node).values()
           if p.diagram.kind=='dimension' and p.diagram.prim is not None]
    assert len(lines)==5
    assert all(p.style.stroke_width==.45 for p in lines)


def test_a_zero_length_dimension_is_refused():
    with pytest.raises(ValueError, match="two distinct points"):
        inklet.dimension((3, 3), (3, 3), "0")


# -- scale bars -----------------------------------------------------------


def test_a_scale_bar_in_a_panel_is_as_long_as_the_data_says():
    p = inklet.panel(60, 40, x=(0, 30), y=(0, 1))
    bar = inklet.scalebar(10, panel=p, corner="sw")
    # 10 of 30 data units across 60mm of area.
    assert bar.bbox.width == pytest.approx(20.0)


def test_a_scale_bar_on_a_log_axis_measures_where_it_sits():
    p = inklet.panel(60, 40, x=inklet.log((1, 1000)), y=(0, 1))
    decade = inklet.scalebar(9, panel=p)          # 1 -> 10, one decade
    assert decade.bbox.width == pytest.approx(20.0)


def test_a_scale_bar_lands_in_the_corner_it_was_given():
    p = inklet.panel(60, 40, x=(0, 30), y=(0, 1))
    bar = inklet.scalebar(10, "10 s", panel=p, corner="se", pad=2.0)
    box = bar.bbox
    assert box.x1 == pytest.approx(p.area.x1 - 2.0)
    assert box.y1 == pytest.approx(p.area.y1 - 2.0)


def test_a_scale_bar_over_an_image_keeps_the_image():
    picture = inklet.box(inklet.spacer(), width=40, height=30).named("pic")
    over = inklet.scalebar(8, "8 µm", over=picture, corner="sw")
    assert picture.id in inklet.resolve(over)
    assert over.bbox.width == pytest.approx(40.0, abs=0.5)


# -- panel letters --------------------------------------------------------


def test_letters_run_from_the_start_letter():
    items = [inklet.box("one"), inklet.box("two"), inklet.box("three")]
    tagged = inklet.letters(items, start="c")
    texts = [n.prim.lines[0].text for node in tagged for n in node.walk()
             if n.kind == LETTER_KIND]
    assert texts == ["c", "d", "e"]


def test_paren_style_writes_the_brackets():
    tagged = inklet.letters([inklet.box("x")], style="paren")
    texts = [n.prim.lines[0].text for n in tagged[0].walk()
             if n.kind == LETTER_KIND]
    assert texts == ["(a)"]


def test_a_letter_sits_outside_the_panel_it_names():
    """A y-axis label reaches the top-left corner; the letter must clear it."""
    p = inklet.panel(40, 25, x=(0, 1), y=(0, 1)).axes(x="t", y="v")
    built = p.build()
    tagged = inklet.letters([built], pad=1.5)[0]

    box = inklet.resolve(tagged)[built.id].bbox
    mark = [n for n in tagged.walk() if n.kind == LETTER_KIND][0]
    spot = inklet.resolve(tagged)[mark.id].bbox
    assert spot.x1 <= box.x0 + 1e-9
    assert spot.overlap(box) is None


def test_letters_keep_the_caller_s_handles():
    body = inklet.box("panel")
    tagged = inklet.letters([body])[0]
    assert body.id in inklet.resolve(tagged)


def test_letters_take_panels_directly():
    panels = [inklet.panel(20, 12, x=(0, 1), y=(0, 1)).outline()
              for _ in range(2)]
    tagged = inklet.letters(panels)
    assert len(tagged) == 2 and all(isinstance(t, inklet.Diagram) for t in tagged)


def test_an_unknown_letter_style_is_refused():
    with pytest.raises(ValueError, match="unknown letter style"):
        inklet.letters([inklet.box("x")], style="roman")


# -- the whole thing on a page --------------------------------------------


def test_an_annotated_figure_lints_clean():
    rig = inklet.hstack([inklet.box("laser").named("laser"),
                      inklet.box("detector").named("detector")], gap=10)
    art = inklet.annotate(rig.find("laser"), "source", side="n", within=rig)
    art = inklet.annotate(rig.find("detector"), "readout", side="s", within=art)

    fig = inklet.figure(width=90)
    fig.add(art)
    assert [d for d in fig.lint() if d.severity != "info"] == []


def test_a_leader_is_styled_by_the_theme_not_by_the_caller():
    fig = inklet.figure(width=60)
    fig.add(inklet.annotate(inklet.box("a"), "name", side="e", clear=4.0))
    root, placements = fig.build()
    shaft = [n for n in root.walk() if n.kind == CONNECTOR_KIND][0]
    assert placements[shaft.id].style.stroke == TH.ink
