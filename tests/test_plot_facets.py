"""inklet.plot: twin axes and facet grids.

Both features are about *registration* -- one rectangle read against two
scales, or several rectangles that must line up on their plot areas and not on
their labels -- so almost every assertion here is a coordinate comparison after
`resolve()`.
"""

from __future__ import annotations

import pytest

from inklet.core import Rect, resolve
from inklet.diagnostics import lint
from inklet.draw.coords import ORIGIN_ANCHOR, as_drawn
from inklet.plot import facets, panel
from inklet.plot.axis import AXIS_LABEL_KIND, SPINE_KIND, TICK_KIND, TICK_LABEL_KIND
from inklet import use_theme


def placements(node, kind: str):
    return [p for p in resolve(as_drawn(node)).values() if p.diagram.kind == kind]


def label_of(placed) -> str:
    """The words a placed text node carries, joined."""
    prim = placed.diagram.prim
    return "".join(line.text for line in getattr(prim, "lines", ()))


def texts(node) -> list[str]:
    return [label_of(p) for p in placements(node, TICK_LABEL_KIND)]


def boxes(node, kind: str) -> list[Rect]:
    return [p.bbox for p in placements(node, kind)]


# --- twin axes ---------------------------------------------------------------


def test_a_twin_maps_the_same_area_through_a_second_scale() -> None:
    p = panel(60, 40, x=(0, 10), y=(0, 10))
    other = p.twin_y((0, 100), axis=False)

    assert other.point(5, 50) == p.point(5, 5)
    assert other.point(0, 0) == p.point(0, 0)


def test_a_twin_draws_into_the_panel_it_came_from() -> None:
    p = panel(60, 40, x=(0, 10), y=(0, 10))
    other = p.twin_y((0, 100), axis=False)
    other.line([(0, 0), (10, 100)])

    assert placements(p.build(), "path")


def test_a_twin_axis_hangs_on_the_side_it_was_asked_for() -> None:
    p = panel(60, 40, x=(0, 10), y=(0, 10))
    p.axis("left")
    p.twin_y((0, 100))

    left, right = sorted(boxes(p.build(), SPINE_KIND), key=lambda b: b.x0)
    assert left.x1 <= p.area.x0 + 1e-9
    assert right.x0 >= p.area.x1 - 1e-9


def test_a_twin_axis_shows_the_twins_numbers() -> None:
    p = panel(60, 40, x=(0, 10), y=(0, 10))
    p.twin_y((0, 1000))

    assert "1000" in texts(p.build())


def test_a_tinted_twin_colours_its_own_furniture_only() -> None:
    p = panel(60, 40, x=(0, 10), y=(0, 10))
    p.axis("left")
    p.twin_y((0, 100), color="#ff0000")

    strokes = {q.diagram.style.stroke
               for q in resolve(as_drawn(p.build())).values()
               if q.diagram.kind == "axis"}
    assert "#ff0000" in strokes
    assert len(strokes) == 2                # the parent's axis is still ink


def test_a_twin_x_runs_along_the_top() -> None:
    p = panel(60, 40, x=(0, 10), y=(0, 10))
    top = p.twin_x((0, 1))

    assert top.point(0.5, 0) == p.point(5, 0)
    assert boxes(p.build(), SPINE_KIND)[0].y1 <= p.area.y0 + 1e-9


def test_a_twin_invalidates_the_parents_cache() -> None:
    """The twin shares the lists, so the parent must not serve a stale build."""
    p = panel(60, 40, x=(0, 10), y=(0, 10))
    p.background()
    before = p.build().bbox
    p.twin_y((0, 100), axis=False).line([(0, 0), (10, 200)])

    assert p.build().bbox != before


def test_a_twin_is_on_one_of_two_sides() -> None:
    p = panel(60, 40, x=(0, 10), y=(0, 10))
    with pytest.raises(ValueError):
        p.twin_y(side="top")
    with pytest.raises(ValueError):
        p.twin_x(side="left")


# --- facets ------------------------------------------------------------------


def grid(count: int, **kwargs):
    made = []
    for i in range(count):
        p = panel(30, 20, x=(0, 10), y=(0, 10 * (i + 1)))
        p.background().line([(0, 0), (10, 10 * (i + 1))])
        made.append(p)
    return made, facets(made, **kwargs)


def test_facets_lays_panels_out_in_rows() -> None:
    _, node = grid(4, cols=2)

    spines = boxes(node, SPINE_KIND)
    assert len(spines) == 8                 # two per panel


def test_facets_defaults_to_a_square_ish_grid() -> None:
    _, three = grid(3)
    _, four = grid(4)

    assert three.bbox.width == pytest.approx(four.bbox.width, abs=6.0)


def test_shared_x_writes_the_numbers_only_under_the_bottom_row() -> None:
    _, shared = grid(4, cols=2, share_x=True, share_y=False)
    _, loose = grid(4, cols=2, share_x=False, share_y=False)

    assert len(texts(shared)) < len(texts(loose))


def test_an_inner_panel_keeps_its_spine_and_its_ticks() -> None:
    _, node = grid(4, cols=2)

    assert len(boxes(node, SPINE_KIND)) == 8
    assert len(boxes(node, TICK_KIND)) == len(boxes(grid(4, cols=2,
                                                        share_x=False,
                                                        share_y=False)[1],
                                                   TICK_KIND))


def test_the_bottom_panel_of_a_ragged_column_keeps_its_numbers() -> None:
    """Three panels in two columns: the top-right one has nothing under it."""
    _, node = grid(3, cols=2, share_x=True, share_y=False)

    # Panels 1 (top right) and 2 (bottom left) are both bottom-most.
    labelled = [b for b in boxes(node, TICK_LABEL_KIND)]
    rows = {round(b.y0, 3) for b in labelled}
    assert len(rows) >= 2


def test_facets_line_up_the_plot_areas_not_the_bounding_boxes() -> None:
    left = panel(30, 20, x=(0, 10), y=(0, 1))
    right = panel(30, 20, x=(0, 10), y=(0, 1000000))
    left.background().line([(0, 0), (10, 1)])
    right.background().line([(0, 0), (10, 1000000)])
    node = facets([left, right], cols=2, share_y=False)

    a, b = sorted(boxes(node, "plot-area"), key=lambda r: r.x0)
    assert a.y0 == pytest.approx(b.y0)
    assert a.y1 == pytest.approx(b.y1)
    assert a.width == pytest.approx(b.width)


def test_a_shared_name_is_centred_on_the_data_not_on_the_labels() -> None:
    panels, node = grid(2, cols=2, x_label="time / s")

    name = [p for p in placements(node, AXIS_LABEL_KIND)
            if label_of(p) == "time / s"][0]
    areas = boxes(node, "plot-area")
    middle = (min(a.x0 for a in areas) + max(a.x1 for a in areas)) / 2
    assert name.bbox.center.x == pytest.approx(middle, abs=0.01)


def test_a_shared_y_name_is_turned_on_its_side() -> None:
    _, node = grid(2, cols=1, y_label="signal")

    name = [p for p in placements(node, AXIS_LABEL_KIND)
            if label_of(p) == "signal"][0]
    assert name.bbox.height > name.bbox.width


def test_the_shared_name_sits_clear_of_every_panel() -> None:
    _, node = grid(4, cols=2, x_label="time / s", y_label="signal")

    below = [p for p in placements(node, AXIS_LABEL_KIND)
             if label_of(p) == "time / s"][0]
    assert below.bbox.y0 >= max(b.y1 for b in boxes(node, "plot-area"))


def test_facets_pass_their_axis_options_to_every_panel() -> None:
    _, plain = grid(2, cols=2, share_x=False, share_y=False)
    _, dense = grid(2, cols=2, share_x=False, share_y=False, minor=True)

    assert len(boxes(dense, TICK_KIND)) > len(boxes(plain, TICK_KIND))


def test_facets_can_leave_the_furniture_alone() -> None:
    made = [panel(30, 20, x=(0, 10), y=(0, 10)) for _ in range(2)]
    for p in made:
        p.line([(0, 0), (10, 10)])
    node = facets(made, cols=2, axes=False)

    assert not boxes(node, SPINE_KIND)


def test_facets_want_a_panel() -> None:
    with pytest.raises(ValueError):
        facets([])
    with pytest.raises(ValueError):
        facets([panel(10, 10)], cols=0)


def test_a_facet_grid_lints_clean() -> None:
    use_theme("nature")
    _, node = grid(4, cols=2, x_label="time / s", y_label="signal")

    assert not [d for d in lint(node) if d.severity == "error"]


def test_facets_keep_the_origin_anchor_a_figure_needs() -> None:
    _, node = grid(2, cols=2)

    assert node.anchor_point(ORIGIN_ANCHOR) is not None


def test_facets_are_deterministic() -> None:
    def build() -> str:
        _, node = grid(4, cols=2, x_label="t", y_label="y")
        return repr(sorted((b.x0, b.y0, b.x1, b.y1)
                           for b in boxes(node, SPINE_KIND)))

    assert build() == build()
