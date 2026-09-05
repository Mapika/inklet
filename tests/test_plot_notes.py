"""inklet.plot: writing on a plot in the plot's own coordinates."""

from __future__ import annotations

import math

import pytest

from inklet.core import Rect, resolve
from inklet.draw import annotation_side
from inklet.draw.coords import as_drawn
from inklet.plot import panel
from inklet.plot.notes import ANNOTATION_TARGET_KIND

CURVE = [(t, math.sin(t / 3.0) * 10 + 20) for t in range(20)]


def text_boxes(node, content: str) -> list[Rect]:
    out = []
    for placed in resolve(as_drawn(node)).values():
        prim = placed.diagram.prim
        if prim is not None and getattr(prim, "text", None) == content:
            out.append(placed.bbox)
    return out


def one_box(node, content: str) -> Rect:
    (box,) = text_boxes(node, content)
    return box


# --- text --------------------------------------------------------------------


def test_a_label_lands_on_its_data_point() -> None:
    p = panel(40, 30, x=(0, 10), y=(0, 10))
    p.text(5, 5, "here")
    assert one_box(p.build(), "here").center.x == pytest.approx(0.0, abs=0.1)


def test_the_anchor_is_a_compass_point_on_the_label() -> None:
    east = panel(40, 30, x=(0, 10), y=(0, 10)).text(5, 5, "here", anchor="w")
    west = panel(40, 30, x=(0, 10), y=(0, 10)).text(5, 5, "here", anchor="e")
    assert one_box(east.build(), "here").x0 == pytest.approx(0.0, abs=0.1)
    assert one_box(west.build(), "here").x1 == pytest.approx(0.0, abs=0.1)


def test_an_offset_is_millimetres_because_it_is_a_clearance() -> None:
    plain = panel(40, 30, x=(0, 10), y=(0, 10)).text(5, 5, "here")
    moved = panel(40, 30, x=(0, 10), y=(0, 10)).text(5, 5, "here", offset=(3, 0))
    shift = (one_box(moved.build(), "here").center.x
             - one_box(plain.build(), "here").center.x)
    assert shift == pytest.approx(3.0)


def test_a_label_moves_with_the_scale_not_with_the_page() -> None:
    wide = panel(80, 30, x=(0, 10), y=(0, 10)).text(10, 5, "end")
    narrow = panel(40, 30, x=(0, 10), y=(0, 10)).text(10, 5, "end")
    assert (one_box(wide.build(), "end").center.x
            > one_box(narrow.build(), "end").center.x)


def test_text_can_be_put_under_the_data() -> None:
    p = panel(40, 30, x=(0, 10), y=(0, 10))
    p.text(5, 5, "watermark", front=False)
    assert p._under and not p._over


# --- arrows ------------------------------------------------------------------


def test_an_arrow_runs_between_two_data_points() -> None:
    p = panel(40, 30, x=(0, 10), y=(0, 10))
    p.arrow((1, 1), (9, 9))
    box = p.build().bbox
    assert box.width > 20 and box.height > 15


def test_an_arrow_ends_on_its_coordinates_exactly() -> None:
    """The ends are anchors, not shapes, so nothing is clipped back."""
    p = panel(40, 30, x=(0, 10), y=(0, 10))
    start, end = p.point(2, 2), p.point(8, 8)
    p.arrow((2, 2), (8, 8), head=None)
    box = p.build().bbox
    assert box.x0 == pytest.approx(min(start.x, end.x), abs=0.3)
    assert box.x1 == pytest.approx(max(start.x, end.x), abs=0.3)


def test_an_arrow_takes_a_label() -> None:
    p = panel(40, 30, x=(0, 10), y=(0, 10))
    p.arrow((1, 1), (9, 9), label="rise")
    assert text_boxes(p.build(), "rise")


def test_the_carrier_stays_in_the_tree() -> None:
    """A connector naming an endpoint outside the tree has lost the
    provenance the linter reads."""
    p = panel(40, 30, x=(0, 10), y=(0, 10))
    p.arrow((1, 1), (9, 9))
    kinds = [n.diagram.kind for n in resolve(as_drawn(p.build())).values()]
    assert "arrow-ends" in kinds


def test_an_arrow_does_not_lint_as_an_empty_node() -> None:
    """The carrier has to stay in the tree, so it has to be worth having:
    a node with no prim and no children is exactly what EMPTY_DIAGRAM is for.
    """
    import inklet

    p = panel(40, 30, x=(0, 10), y=(0, 10))
    p.line(CURVE).arrow((1, 25), (6, 28))
    assert [d for d in inklet.lint(p.build())
            if d.code == "EMPTY_DIAGRAM"] == []


def test_the_carrier_claims_no_space_the_arrow_did_not() -> None:
    plain = panel(40, 30, x=(0, 10), y=(0, 10))
    plain.line(CURVE)
    with_arrow = panel(40, 30, x=(0, 10), y=(0, 10))
    with_arrow.line(CURVE).arrow((2, 5), (8, 25), head=None)
    box = with_arrow.build().bbox
    assert box.width == pytest.approx(plain.build().bbox.width, abs=0.3)


# --- callouts ----------------------------------------------------------------


def test_a_callout_puts_a_label_near_its_point() -> None:
    p = panel(40, 30, x=(0, 10), y=(0, 10))
    p.annotate(5, 5, "peak")
    box = one_box(p.build(), "peak")
    assert abs(box.center.x) < 6 and abs(box.center.y) < 12


def test_a_callout_asks_for_a_side_and_says_where_it_went() -> None:
    p = panel(40, 30, x=(0, 10), y=(0, 10))
    p.annotate(5, 5, "peak", side="n")
    assert annotation_side(p._over[-1]) in ("n", "ne", "nw", "e", "w", "s",
                                            "se", "sw")


def test_a_callout_at_the_top_is_kept_inside_the_panel() -> None:
    """An outward search wants to go over the spine; a caption above the axis
    reads as belonging to the panel above it."""
    p = panel(40, 30, x=(0, 10), y=(0, 10))
    p.annotate(5, 10, "top", side="n")
    assert one_box(p.build(), "top").y0 >= p.area.y0 - 0.5


def test_the_boundary_can_be_switched_off() -> None:
    p = panel(40, 30, x=(0, 10), y=(0, 10))
    p.annotate(5, 10, "top", side="n", inside=False)
    assert one_box(p.build(), "top").y0 < p.area.y0


def test_a_callout_carries_an_invisible_datum_by_default() -> None:
    p = panel(40, 30, x=(0, 10), y=(0, 10))
    p.annotate(5, 5, "peak")
    found = [n for n in resolve(as_drawn(p.build())).values()
             if n.diagram.kind == ANNOTATION_TARGET_KIND]
    assert len(found) == 1
    assert found[0].style.fill in (None, "none")


def test_the_datum_can_be_made_visible() -> None:
    p = panel(40, 30, x=(0, 10), y=(0, 10))
    p.annotate(5, 5, "peak", dot=True)
    found = [n for n in resolve(as_drawn(p.build())).values()
             if n.diagram.kind == ANNOTATION_TARGET_KIND]
    assert found[0].style.fill not in (None, "none")


def test_a_callout_can_be_told_what_to_miss() -> None:
    p = panel(40, 30, x=(0, 10), y=(0, 10))
    p.line(CURVE)
    north = p.annotate(5, 5, "a", side="n")._over[-1]
    blocked = panel(40, 30, x=(0, 10), y=(0, 10))
    blocked.annotate(5, 5, "a", side="n",
                     avoid=[Rect(-20, -15, 20, 0)])
    assert (one_box(blocked.build(), "a").center.y
            > one_box(north, "a").center.y)
