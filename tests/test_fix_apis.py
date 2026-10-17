"""Grid contours, prebinned histograms, log whiskers to zero, colour bar titles
along the bar, and one axis name for a grid of cells (the apis fix group).

Geometry is measured on the drawn nodes, in page millimetres, not on pixels.
A node built with `draw_place` is centred on its own box unless it was given
`origin=`, so the extent of a drawn group is read from its children.
"""

import random

import pytest

import inklet
from inklet import use_theme
from inklet.core import DiagramError, Rect, Vec2
from inklet.draw.coords import plot_area
from inklet.plot import mass_levels
from inklet.plot.axis import AXIS_LABEL_KIND
from inklet.plot.marks import counted_bins
from inklet.plot.marks import errorbars as errorbar_node
from inklet.plot.scale import ScaleError


@pytest.fixture(autouse=True)
def _nature():
    use_theme("nature")


def _walk(node):
    yield node
    for child in node.children:
        yield from _walk(child)


def _notes(node, key):
    return [n.notes[key] for n in _walk(node) if key in n.notes]


def _union(boxes):
    out = boxes[0]
    for box in boxes[1:]:
        out = out.union(box)
    return out


def _children_box(node):
    """The extent of a drawn group, from its children, in the group's frame."""
    return _union([child.bbox for child in node.children])


def _grid(seed=3, n=12):
    rng = random.Random(seed)
    xs = [i + 0.5 for i in range(n)]
    ys = [j + 0.5 for j in range(n)]
    z = [[0.0] * n for _ in range(n)]
    for _ in range(600):
        i = min(n - 1, max(0, int(rng.gauss(n / 2, n / 6))))
        j = min(n - 1, max(0, int(rng.gauss(n / 2, n / 6))))
        z[j][i] += 1.0
    return xs, ys, z


# -- 1. contours of a gridded field --------------------------------------------


def test_contour_draws_a_ring_round_a_peak_in_data_units():
    xs = [0.0, 1.0, 2.0, 3.0, 4.0]
    ys = [0.0, 1.0, 2.0, 3.0, 4.0]
    z = [[0.0] * 5 for _ in range(5)]
    z[2][2] = 10.0
    p = inklet.panel(40, 40, x=(0, 4), y=(0, 4))
    p.contour(xs, ys, z, levels=[5.0])
    node = p.build()
    assert _notes(node, "contour")[0]["drawn"] == [5.0]
    # The ring is centred on the peak, which is at data (2, 2).
    contour = next(n for n in _walk(node) if n.kind == "contour")
    peak = p.point(2.0, 2.0)
    assert contour.bbox.center.x == pytest.approx(peak.x, abs=0.05)
    assert contour.bbox.center.y == pytest.approx(peak.y, abs=0.05)


def test_contour_rejects_a_bare_number_of_levels_and_names_hdr():
    xs, ys, z = _grid()
    p = inklet.panel(40, 40, x=(0, 12), y=(0, 12))
    with pytest.raises(DiagramError, match="hdr="):
        p.contour(xs, ys, z, levels=5)


def test_contour_needs_levels_or_hdr_but_not_both():
    xs, ys, z = _grid()
    p = inklet.panel(40, 40, x=(0, 12), y=(0, 12))
    with pytest.raises(DiagramError, match="needs levels="):
        p.contour(xs, ys, z)
    with pytest.raises(DiagramError, match="not both"):
        p.contour(xs, ys, z, levels=[1.0], hdr=(0.5,))


def test_contour_names_the_keyword_it_was_probably_meant_to_be():
    xs, ys, z = _grid()
    p = inklet.panel(40, 40, x=(0, 12), y=(0, 12))
    with pytest.raises(TypeError, match="did you mean hdr="):
        p.contour(xs, ys, z, mass=(0.683,))


def test_colorbar_names_label_for_a_title_turned_along_the_bar():
    q = inklet.panel(60, 50, x=(0, 1), y=(0, 1))
    q.matrix([[0.1, 0.5], [0.9, 0.2]], ramp=inklet.ramp("viridis"))
    with pytest.raises(TypeError, match="did you mean label="):
        q.colorbar(corner="se", length=24, title_rotation=90)


def test_doc_label_names_x_and_y_for_the_grid_axes():
    doc = _doc_grid()
    with pytest.raises(TypeError, match="did you mean x="):
        doc.label(xlabel="Month Year")


def test_contour_level_outside_the_field_fails_clearly():
    xs, ys, z = _grid()
    p = inklet.panel(40, 40, x=(0, 12), y=(0, 12))
    with pytest.raises(DiagramError, match="no contour to draw"):
        p.contour(xs, ys, z, levels=[1e9])


def test_contour_z_must_match_the_axes():
    p = inklet.panel(40, 40, x=(0, 3), y=(0, 3))
    with pytest.raises(DiagramError, match="rows of"):
        p.contour([0, 1, 2], [0, 1], [[0, 0, 0]], levels=[0.5])


def test_hdr_levels_enclose_at_least_their_fraction_of_the_counts():
    xs, ys, z = _grid()
    total = sum(sum(row) for row in z)
    for fraction, level in zip((0.954, 0.683), mass_levels(z, (0.954, 0.683))):
        inside = sum(v for row in z for v in row if v >= level)
        assert inside / total >= fraction
        # And not by much more: the next lower count would overshoot.
        below = sum(v for row in z for v in row if v > level - 1e-9)
        assert below / total - fraction < 0.1
    p = inklet.panel(40, 40, x=(0, 12), y=(0, 12))
    p.contour(xs, ys, z, hdr=(0.683, 0.954), color="#ff0000")
    note = _notes(p.build(), "contour")[0]
    assert note["masses"] == [0.954, 0.683]
    assert note["levels"] == list(mass_levels(z, (0.954, 0.683)))


def test_mass_levels_takes_a_grid_and_skips_missing_cells():
    grid = [[1.0, None, 3.0], [float("nan"), 6.0, 0.0]]
    # Total 10 over the finite cells: 6 holds 0.6, and 6 with 3 holds 0.9.
    assert mass_levels(grid, (0.5, 0.9)) == (6.0, 3.0)
    with pytest.raises(DiagramError, match="between 0 and 1"):
        mass_levels(grid, (1.5,))
    with pytest.raises(DiagramError, match="zero or more"):
        mass_levels([[1.0, -2.0]], (0.5,))


def test_contour_missing_cells_are_outside_every_level():
    xs = [0.0, 1.0, 2.0, 3.0]
    ys = [0.0, 1.0, 2.0, 3.0]
    z = [[None, None, None, None],
         [None, 5.0, 5.0, None],
         [None, 5.0, 9.0, None],
         [None, None, None, None]]
    p = inklet.panel(40, 40, x=(0, 3), y=(0, 3))
    p.contour(xs, ys, z, levels=[7.0])
    contour = next(n for n in _walk(p.build()) if n.kind == "contour")
    # Only the 9 cell is above 7, and the missing cells do not pull the ring
    # outwards, so it stays within one cell's width of the peak.
    assert contour.bbox.width < p.point(2, 0).x - p.point(1, 0).x


# -- 2. prebinned histograms ---------------------------------------------------


def test_prebinned_hist_draws_the_counts_as_bar_heights():
    edges = [0.0, 0.25, 0.5, 0.75, 1.0]
    counts = [12, 40, 88, 61]
    p = inklet.panel(60, 34, x=(0, 1), y=(0, 100))
    counted = counted_bins(p, edges, counts)
    assert len(counted.children) == 4
    # The tallest bar reaches the count of 88 on the y scale.
    box = _children_box(counted)
    assert box.y0 == pytest.approx(p.y.map(88), abs=1e-9)
    assert box.y1 == pytest.approx(p.y.map(0), abs=1e-9)


def test_prebinned_hist_method_draws_the_same_bars():
    edges = [0.0, 0.25, 0.5, 0.75, 1.0]
    counts = [12, 40, 88, 61]
    p = inklet.panel(60, 34, x=(0, 1), y=(0, 100))
    p.hist(counts, bins=edges, prebinned=True)
    bars = [n for n in _walk(p.build()) if n.kind == "place" and n.children]
    assert bars, "the bars should be drawn"
    assert _children_box(counted_bins(p, edges, counts)).y0 == pytest.approx(
        p.y.map(88), abs=1e-9)


def test_prebinned_hist_runs_across_the_page_when_horizontal():
    edges = [0.0, 0.25, 0.5, 0.75, 1.0]
    counts = [12, 40, 88, 61]
    p = inklet.panel(60, 34, x=(0, 100), y=(0, 1))
    box = _children_box(counted_bins(p, edges, counts, orient="h"))
    assert box.x1 == pytest.approx(p.x.map(88), abs=1e-9)
    assert box.x0 == pytest.approx(p.x.map(0), abs=1e-9)
    # The four bins stack from top to bottom of the whole height.
    assert box.height == pytest.approx(abs(p.y.map(1.0) - p.y.map(0.0)), abs=1e-9)


def test_prebinned_hist_density_integrates_to_one():
    edges = [0.0, 0.2, 0.5, 1.0]
    counts = [10, 30, 60]
    p = inklet.panel(60, 34, x=(0, 1), y=(0, 3))
    box = _children_box(counted_bins(p, edges, counts, density=True))
    # Density is count / (total * width): 60 / (100 * 0.5) = 1.2 is the tallest.
    assert box.y0 == pytest.approx(p.y.map(1.2), abs=1e-9)
    heights = [c / (100 * (b - a)) for c, a, b in zip(counts, edges, edges[1:])]
    area = sum(h * (b - a) for h, a, b in zip(heights, edges, edges[1:]))
    assert area == pytest.approx(1.0)


@pytest.mark.parametrize("bins, values, message", [
    ([0, 1, 2], [1, 2, 3], "one more edge"),
    ([0, 2, 1, 3], [1, 2, 3], "strictly increase"),
    ([0, 1, 2, 3], [1, -1, 2], "zero or more"),
])
def test_prebinned_hist_refuses_bad_edges_and_counts(bins, values, message):
    p = inklet.panel(60, 34, x=(0, 3), y=(0, 3))
    with pytest.raises(DiagramError, match=message):
        p.hist(values, bins=bins, prebinned=True)


def test_prebinned_hist_needs_edges_not_a_bin_count():
    p = inklet.panel(60, 34, x=(0, 1), y=(0, 3))
    with pytest.raises(DiagramError, match="bin edges in bins="):
        p.hist([1, 2, 3], bins=3, prebinned=True)


# -- 4. log whiskers that reach zero -------------------------------------------


def _log_panel():
    return inklet.panel(60, 30, x=(0.05, 300), y=inklet.log((1e-4, 1)))


def test_a_log_whisker_to_zero_runs_to_the_axis_floor():
    p = _log_panel()
    node = errorbar_node(p, [(0.6, 8e-5)], yerr=[(8e-5, 7e-3)], cap=0.7)
    floor = p.point(0.6, 1e-4).y
    # The lower end of the whisker lies on the floor of the axis, and nothing
    # in the drawing goes below it.
    assert _children_box(node).y1 == pytest.approx(floor, abs=1e-6)


def test_the_floor_end_is_an_open_arrow_by_default_and_bare_when_asked():
    arrow = errorbar_node(_log_panel(), [(0.6, 8e-5)], yerr=[(8e-5, 7e-3)], cap=0.7)
    bare = errorbar_node(_log_panel(), [(0.6, 8e-5)], yerr=[(8e-5, 7e-3)], cap=0.7,
                         floor="none")
    # The whisker, the cap at the top end, and an arrowhead of two strokes.
    assert len(arrow.children) == 3
    assert len(bare.children) == 2


def test_a_point_at_zero_on_a_log_axis_still_refuses():
    with pytest.raises(ScaleError, match="undefined at or below zero"):
        errorbar_node(_log_panel(), [(0.6, 0.0)], yerr=[(1e-5, 1e-5)])


def test_errorbars_floor_takes_arrow_or_none():
    with pytest.raises(DiagramError, match='"arrow" or "none"'):
        errorbar_node(_log_panel(), [(0.6, 1e-3)], yerr=[(1e-4, 1e-4)], floor="open")


def test_the_log_scale_error_says_whiskers_go_to_the_floor_not_symlog():
    with pytest.raises(ScaleError) as info:
        inklet.log((1e-4, 1)).map(0.0)
    message = str(info.value)
    assert "errorbars()" in message
    assert "loses the log scale" in message


# -- 5. a colour bar title along the bar ---------------------------------------


def _nodes_of_kind(node, kind):
    return [n for n in _walk(node) if n.kind == kind]


def _placed_boxes(node, kind):
    """Figure-space boxes of the drawn nodes of one kind, rotations included."""
    return [placed.bbox for placed in inklet.core.resolve(node).values()
            if placed.diagram.kind == kind]


def test_a_corner_colorbar_label_runs_along_the_bar():
    q = inklet.panel(60, 50, x=(0, 1), y=(0, 1))
    q.matrix([[0.1, 0.5], [0.9, 0.2]], ramp=inklet.ramp("viridis"))
    q.colorbar(corner="se", length=24, label="Normalized entries")
    boxes = _placed_boxes(q.build(), AXIS_LABEL_KIND)
    assert boxes, "the label should be drawn as an axis-name node"
    # Turned to run along a vertical bar: tall and thin, not a line across it.
    assert any(b.height > 3 * b.width for b in boxes)


def test_a_colorbar_title_stays_above_the_bar():
    q = inklet.panel(60, 50, x=(0, 1), y=(0, 1))
    q.matrix([[0.1, 0.5], [0.9, 0.2]], ramp=inklet.ramp("viridis"))
    q.colorbar(corner="se", length=24, title="Normalized entries")
    boxes = _placed_boxes(q.build(), "label")
    assert boxes
    # Set across the page, as the title always was: wide and not tall.
    assert all(b.width > b.height for b in boxes)


# -- 3. one axis name for a grid of panels -------------------------------------


def _doc_grid(**options):
    doc = inklet.preset("scientific.nature", format="single-column").document(
        columns=2, **options)
    for k in range(8):
        p = inklet.plot_spec(38, 22, x=(0, 12), y=(0, 100))
        p.line([(m, 20 + 5 * k + 3 * m) for m in range(12)], name="a")
        p.axes(x_options=dict(ticks=[0, 6, 12]), y_options=dict(ticks=[0, 50, 100]))
        doc.add(f"c{k}", p, row=k // 2, column=k % 2)
    return doc


def _figure_boxes(compiled):
    """Figure-space boxes of the axis names and the cells, and the plot areas
    of the cells, each mapped out of its cell's own frame."""
    _, placements = compiled.build()
    names, cells, areas = [], [], []
    for placed in placements.values():
        kind = placed.diagram.kind
        if kind == AXIS_LABEL_KIND:
            names.append(placed.bbox)
        elif kind == "document-cell":
            cells.append(placed.bbox)
            for child in placed.diagram.children:
                area = plot_area(child)
                if area is None:
                    continue
                corners = [placed.world.apply(Vec2(x, y))
                           for x, y in ((area.x0, area.y0), (area.x1, area.y1))]
                areas.append(Rect(min(c.x for c in corners), min(c.y for c in corners),
                                  max(c.x for c in corners), max(c.y for c in corners)))
    return names, cells, areas


def test_a_document_label_names_the_grid_once_under_and_beside_it():
    doc = _doc_grid()
    doc.label(x="Month Year", y="P-score (%)")
    names, cells, areas = _figure_boxes(doc.compile())
    assert len(names) == 2
    assert len(cells) == 8 and len(areas) == 8
    ink = _union(cells)
    region = _union(areas)
    upright = next(b for b in names if b.width > b.height)
    turned = next(b for b in names if b.height > b.width)
    # The x name is centred on the plot areas, and under every cell.
    assert upright.center.x == pytest.approx(region.center.x, abs=1e-6)
    assert upright.y0 >= ink.y1
    # The y name is turned, centred on the plot areas, and left of every cell.
    assert turned.center.y == pytest.approx(region.center.y, abs=1e-6)
    assert turned.x1 <= ink.x0


def test_a_document_label_keeps_a_fixed_page_height_and_the_page_edge():
    doc = _doc_grid(height=120)
    doc.label(x="Month Year", y="P-score (%)")
    compiled = doc.compile()
    assert compiled.metadata["height_mm"] == pytest.approx(120)
    names, _, _ = _figure_boxes(compiled)
    assert max(b.y1 for b in names) <= 120 + 1e-6
    assert min(b.x0 for b in names) >= 0


def test_a_document_label_must_be_a_string():
    doc = _doc_grid()
    with pytest.raises(TypeError, match="is a string"):
        doc.label(x=3)


def test_a_document_without_labels_has_no_axis_names():
    names, _, _ = _figure_boxes(_doc_grid().compile())
    assert names == []
