"""Round 5: the alignment contract as an invariant rather than a convention.

Every panel in this library declares one rectangle -- where the axes stop and
the data starts -- and everything that lines panels up reads it. Until now the
rectangle survived a placement only where somebody had remembered to carry it
by hand, in two places, in two spellings, one of which was wrong by the
panel's own recentring offset. These tests hold the invariant: a note travels
with the node it was put on, whatever the tree does to it afterwards.

Written as measurements, not as assertions about which line of code ran. The
numbers in `test_the_mouse_figures_bottom_row_*` come off the real panels in
`figures/neural_activity.py`, which is read and not edited.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

import inklet
from inklet.core import Affine, Diagram, Rect, Vec2, note_through
from inklet.draw.coords import AREA_NOTE, as_drawn, plot_area
from inklet.layout.fit import _padded

ROOT = Path(__file__).resolve().parent.parent


def a_panel(width: float = 60.0, height: float = 40.0,
            y_label: str = "a deliberately wide y axis name") -> Diagram:
    """A built panel whose furniture is asymmetric, which is the whole point:
    a symmetric one agrees with its bounding box by accident and proves
    nothing about the frame the rectangle is in."""
    return (inklet.panel(width, height, x=(0.0, 2.0), y=(0.0, 1.0))
            .line([(0.0, 0.0), (1.0, 1.0), (2.0, 0.0)])
            .axes(x="time / s", y=y_label)
            .build())


def close(a: float, b: float, tol: float = 1e-9) -> bool:
    return abs(a - b) <= tol


def same_rect(a: Rect, b: Rect, tol: float = 1e-9) -> bool:
    return all(close(u, v, tol) for u, v in
               ((a.x0, b.x0), (a.y0, b.y0), (a.x1, b.x1), (a.y1, b.y1)))


# -- M19: a note travels with the node ------------------------------------


def test_a_translation_carries_the_plot_area_and_moves_it():
    """The bug the amendment is for: `plot_area` used to go to None the
    instant anything placed the panel, so every reader had to read the note
    before the move and carry the offset itself."""
    panel = a_panel()
    before = plot_area(panel)
    after = plot_area(panel.translated(5.0, -7.0))
    assert after is not None
    assert same_rect(after, Rect(before.x0 + 5.0, before.y0 - 7.0,
                                 before.x1 + 5.0, before.y1 - 7.0))


def test_a_scale_carries_the_plot_area_exactly():
    panel = a_panel()
    before = plot_area(panel)
    after = plot_area(panel.scaled(2.0, 0.5))
    assert same_rect(after, Rect(before.x0 * 2.0, before.y0 * 0.5,
                                 before.x1 * 2.0, before.y1 * 0.5))


def test_a_rotation_hands_back_the_upright_box_with_the_centre_exact():
    """A turned rectangle is not a rectangle, so the note comes back as the
    box around it: wider than the region, and centred on exactly the point
    the region's centre went to -- which is what `row` lines panels up on."""
    panel = a_panel()
    before = plot_area(panel)
    turned = plot_area(panel.rotated(30.0))
    moved = Affine.rotation(30.0).apply(before.center)
    assert close(turned.center.x, moved.x, 1e-9)
    assert close(turned.center.y, moved.y, 1e-9)
    assert turned.width > before.width          # the box over-reports, as told
    assert turned.height > before.height


def test_a_scalar_note_and_a_direction_note_ride_along_unchanged():
    """`gap_axis` is a *direction*; putting a Vec2 note through `apply()`
    would translate a unit vector, and `diagnostics` reads it back to decide
    which way a stack stacked. So only a Rect moves."""
    stack = inklet.hstack([inklet.box("a"), inklet.box("b")], gap=6.0)
    placed = stack.translated(11.0, 13.0)
    assert placed.notes["gap"] == stack.notes["gap"] == 6.0
    assert placed.notes["gap_axis"] == Vec2(1.0, 0.0)


def test_note_through_is_the_one_rule_and_leaves_what_it_cannot_place():
    at = Affine.translation(3.0, 4.0)
    assert note_through(at, Rect(0.0, 0.0, 1.0, 1.0)) == Rect(3.0, 4.0, 4.0, 5.0)
    assert note_through(at, 6.0) == 6.0
    assert note_through(at, Vec2(1.0, 0.0)) == Vec2(1.0, 0.0)
    assert note_through(at, "linear") == "linear"


def test_an_identity_placement_is_still_the_same_node():
    """`placed` short-circuits on the identity, so there is no wrapper to
    carry anything onto and the caller's handle is unchanged."""
    panel = a_panel()
    assert panel.placed(Affine()) is panel


def test_the_wrapper_gets_its_own_notes_dict():
    panel = a_panel()
    wrapper = panel.translated(1.0, 0.0)
    wrapper.note("mine", 1)
    assert "mine" not in panel.notes


def test_a_note_already_on_the_wrapper_wins():
    """`_lay_out` and `facets` declare the group's own area first; inheriting
    a member's on top of that would replace the union with one panel's."""
    child = Diagram(kind="g").note("plot_area", Rect(0.0, 0.0, 1.0, 1.0))
    wrapper = Diagram(children=(child,), kind="g")
    wrapper.note("plot_area", Rect(-9.0, -9.0, 9.0, 9.0))
    wrapper.carry_notes(child)
    assert wrapper.notes["plot_area"] == Rect(-9.0, -9.0, 9.0, 9.0)


def test_a_stack_of_panels_inherits_no_ones_area():
    """The reason `registered_point` refuses the same question: five panels
    have five plot areas and no shared one."""
    stack = inklet.hstack([a_panel(), a_panel()], gap=4.0)
    assert plot_area(stack) is None


def test_padding_a_panel_keeps_its_area_in_the_padded_frame():
    """`layout.pad` is a wrapper round one child, so it inherits."""
    panel = a_panel()
    before = plot_area(panel)
    padded = inklet.pad(panel, 3.0, 5.0)
    assert same_rect(plot_area(padded), before)


def test_framing_a_panel_keeps_its_area():
    panel = a_panel()
    before = plot_area(panel)
    assert same_rect(plot_area(inklet.frame(panel, pad=2.0)), before)


# -- the hand-carry that was wrong ----------------------------------------


def test_a_fitted_panel_reports_its_area_where_the_area_is():
    """The `_padded` hand-carry copied the note and the anchors *verbatim*,
    so a fitted panel put its plot area and its origin at the coordinates
    they had before the panel was recentred -- a couple of millimetres from
    where they are, and exactly the misalignment the rectangle exists to
    remove. `fit` is what a panel goes through on the way into a row.
    """
    panel = a_panel()
    offset = panel.transform.apply(Vec2(0.0, 0.0))
    assert not close(offset.x, 0.0)            # the recentring is real
    padded = _padded(panel, "width", 10.0)
    assert same_rect(plot_area(padded), plot_area(panel))
    assert close(padded.transform.apply(padded.anchors["origin"]).x,
                 panel.transform.apply(panel.anchors["origin"]).x)


def test_fit_hands_a_row_a_panel_it_can_line_up():
    built = inklet.fit(lambda h: a_panel(60.0, h), height=60.0)
    area = plot_area(built)
    assert area is not None
    assert inklet.row([built, a_panel()]) is not None


# -- row / column align ---------------------------------------------------


def a_row_of(heights, **kwargs) -> Diagram:
    panels = [inklet.panel(30.0, h, x=(0.0, 1.0), y=(0.0, 1.0))
              .line([(0.0, 0.0), (1.0, 1.0)]) for h in heights]
    return inklet.row(panels, gap=4.0, **kwargs)


def member_areas(node: Diagram) -> list[Rect]:
    return [area for area in (plot_area(child) for child in node.children)
            if area is not None]


def test_a_row_centres_the_areas_by_default():
    areas = member_areas(a_row_of([20.0, 30.0]))
    assert close(areas[0].center.y, areas[1].center.y)


def test_a_row_aligned_top_puts_the_area_tops_on_one_line():
    areas = member_areas(a_row_of([20.0, 30.0], align="top"))
    assert close(areas[0].y0, areas[1].y0)
    assert not close(areas[0].y1, areas[1].y1)      # the ragged edge is below


def test_a_row_aligned_bottom_puts_the_area_bottoms_on_one_line():
    areas = member_areas(a_row_of([20.0, 30.0], align="bottom"))
    assert close(areas[0].y1, areas[1].y1)


def test_a_column_aligns_on_the_left_edge_of_the_areas():
    panels = [inklet.panel(w, 20.0, x=(0.0, 1.0), y=(0.0, 1.0))
              .line([(0.0, 0.0), (1.0, 1.0)]) for w in (30.0, 50.0)]
    areas = member_areas(inklet.column(panels, gap=4.0, align="left"))
    assert close(areas[0].x0, areas[1].x0)


def test_centre_is_spelled_both_ways():
    a = member_areas(a_row_of([20.0, 30.0], align="center"))
    b = member_areas(a_row_of([20.0, 30.0], align="centre"))
    assert [r.center.y for r in a] == [r.center.y for r in b]


def test_a_row_refuses_a_column_alignment_by_name():
    with pytest.raises(ValueError, match="not an alignment for a row"):
        a_row_of([20.0], align="left")
    with pytest.raises(ValueError, match="not an alignment for a column"):
        inklet.column([inklet.panel(10.0, 10.0, x=(0, 1), y=(0, 1))], align="top")


def test_align_does_not_change_how_tall_the_row_is():
    """Alignment moves the members across the run; the run's own extent is
    the same block of ink either way."""
    heights = [20.0, 30.0, 24.0]
    boxes = [a_row_of(heights, align=a).bbox
             for a in ("center", "top", "bottom")]
    assert len({round(b.height, 9) for b in boxes}) == 1


# -- the mouse figure's own bottom row ------------------------------------


@pytest.fixture(scope="module")
def mouse():
    sys.path.insert(0, str(ROOT / "figures"))
    try:
        return importlib.import_module("neural_activity")
    finally:
        sys.path.remove(str(ROOT / "figures"))


def mouse_bottom_row(mouse, **kwargs) -> Diagram:
    """`figures/neural_activity.py`'s (c) (d) (e), composed here rather than
    there -- the figure is read-only for this round."""
    parts = [mouse.panel_c(47.0, height=34.0), mouse.panel_d(55.0),
             mouse.panel_e(29.0, height=34.0)]
    return inklet.row(inklet.letters(parts), gap=mouse.GAP, **kwargs)


def test_the_mouse_figures_bottom_row_is_unlevelled_by_centring(mouse):
    """The BACKLOG reproduction, to the tenth of a millimetre: (d) is a
    column of two panels, so its area is 44.1mm tall against its neighbours'
    34.0, and centring lifts it by half the difference."""
    tops = [area.y0 for area in member_areas(mouse_bottom_row(mouse))]
    assert close(max(tops) - min(tops), (44.108 - 34.0) / 2.0, 5e-3)


def test_the_mouse_figures_bottom_row_levels_under_align_top(mouse):
    tops = [area.y0 for area in
            member_areas(mouse_bottom_row(mouse, align="top"))]
    assert close(max(tops) - min(tops), 0.0)


def test_align_top_matches_the_hstack_the_figure_settled_for(mouse):
    """Every panel there carries the same 3.844mm of letter slack above its
    area, which is why top-aligning the boxes happened to align the areas.
    `row(align="top")` gets there by asking for it."""
    parts = [mouse.panel_c(47.0, height=34.0), mouse.panel_d(55.0),
             mouse.panel_e(29.0, height=34.0)]
    letters = inklet.letters(parts)
    by_hand = inklet.hstack(letters, gap=mouse.GAP, align="top")
    assert close(max(a.y0 for a in member_areas(by_hand))
                 - min(a.y0 for a in member_areas(by_hand)), 0.0)


# -- facets declares its area ---------------------------------------------


def four_panels():
    return [inklet.panel(30.0, 20.0, x=(0.0, 1.0), y=(0.0, 1.0))
            .line([(0.0, 0.0), (1.0, 1.0)]) for _ in range(4)]


def test_a_facets_grid_declares_the_block_of_areas_it_aligned_on():
    grid = inklet.facets(four_panels(), cols=2, x_label="t / s", y_label="dF/F")
    area = plot_area(grid)
    assert area is not None
    # Two 30x20 areas across with the theme's large gap between them, and the
    # same down: the block is the areas, not the labels round them.
    assert close(area.width, 2 * 30.0 + (area.width - 60.0))
    assert area.width < grid.bbox.width and area.height < grid.bbox.height
    assert close(area.height, 2 * 20.0 + (area.height - 40.0))


def test_the_declared_area_is_the_rectangle_the_axis_names_are_centred_on():
    """One rectangle answers both questions, which is why one function
    computes it."""
    plain = inklet.facets(four_panels(), cols=2)
    named = inklet.facets(four_panels(), cols=2, x_label="t / s")
    assert close(plot_area(plain).width, plot_area(named).width)
    assert close(plot_area(plain).height, plot_area(named).height)


def test_a_lettered_panel_blocks_out_its_area_and_not_its_box():
    """`_Cell.area` used to fall through to the bounding box for anything
    that was not a `Panel`, and `inklet.letters` returns `Diagram`s -- so
    `examples/gallery.py`, which hands `facets` sixteen lettered panels,
    aligned on the areas and then blocked out its region on the boxes."""
    panels = [inklet.panel(30.0, 20.0, x=(0.0, 1.0), y=(0.0, 1.0))
              .line([(0.0, 0.0), (1.0, 1.0)]).axes(x="t / s", y="dF/F")
              for _ in range(4)]
    lettered = inklet.letters(panels)
    assert not isinstance(lettered[0], inklet.Panel)
    grid = inklet.facets(lettered, cols=2)
    area = plot_area(grid)
    # Two 30x20 data regions across and down, however much letter and
    # furniture is round them.
    assert area.width < grid.bbox.width - 10.0
    assert area.height < grid.bbox.height - 10.0
    members = [plot_area(child) for child in grid.children]
    across = [m for m in members if m is not None]
    assert close(area.width, max(m.x1 for m in across)
                 - min(m.x0 for m in across), 1e-6)
    assert close(area.height, max(m.y1 for m in across)
                 - min(m.y0 for m in across), 1e-6)


def test_a_facets_grid_in_a_row_is_placed_by_its_areas():
    """Before this, a `facets` grid beside a `column` was placed by its box
    while the column was placed by its area -- the same asymmetry the column
    item was filed for, one level up."""
    grid = inklet.facets(four_panels(), cols=2, y_label="dF/F")
    beside = inklet.panel(30.0, 46.0, x=(0.0, 1.0), y=(0.0, 1.0)).line(
        [(0.0, 0.0), (1.0, 1.0)])
    areas = member_areas(inklet.row([grid, beside], gap=6.0))
    assert len(areas) == 2
    assert close(areas[0].center.y, areas[1].center.y, 1e-6)


# -- inklet.plot_area is public ----------------------------------------------


def test_plot_area_is_exported_and_answers_none_off_a_panel():
    assert inklet.plot_area is plot_area
    assert "plot_area" in inklet.__all__
    assert inklet.plot_area(inklet.text("not a panel")) is None


def test_plot_area_is_in_the_frame_the_bbox_is_in():
    """The trap the docstring names: the raw note and the box disagree for
    any panel whose furniture is asymmetric."""
    panel = a_panel()
    raw = panel.notes[AREA_NOTE]
    area = inklet.plot_area(panel)
    box = panel.bbox
    assert not same_rect(raw, area)
    assert box.x0 <= area.x0 and area.x1 <= box.x1
    assert box.y0 <= area.y0 and area.y1 <= box.y1


# -- a box's name is what the reader sees ---------------------------------


def test_a_boxs_name_has_the_markup_taken_out_of_it():
    assert inklet.box("**(a)** Cell").name == "(a) Cell"
    assert inklet.box("H_{2}O and {accent|light}").name == "H2O and light"
    assert inklet.circle("//tilted//").name == "tilted"


def test_an_escaped_delimiter_stays_in_the_name():
    assert inklet.box("6 \\**stars").name == "6 **stars"


def test_naming_a_diagram_is_still_markup_ignorant():
    """`named()` is core's and does not learn what markup is; the stripping
    is `inklet.box`'s, at the one call site that turns a string into a name."""
    assert inklet.text("hi").named("**raw**").name == "**raw**"
    assert inklet.box(inklet.text("**bold**")).name is None


# -- grid notes for the diagnostics rule ----------------------------------


def test_a_grid_records_its_shape_its_cells_and_both_gaps():
    node = inklet.grid([inklet.box(str(i)) for i in range(5)], cols=3,
                    col_gap=8.0, row_gap=2.0)
    assert node.notes["grid_shape"] == (2, 3)
    assert node.notes["grid_cells"] == ((0, 0), (0, 1), (0, 2), (1, 0), (1, 1))
    assert node.notes["col_gap"] == 8.0
    assert node.notes["row_gap"] == 2.0
    assert node.notes["gap"] == 2.0             # the smaller, as before


def test_the_cell_indices_line_up_with_the_children():
    """The note is read by position, so the claim to hold is that cells the
    note calls one row really are on one line."""
    node = inklet.grid([inklet.box(str(i)) for i in range(6)], cols=3, gap=3.0)
    cells = node.notes["grid_cells"]
    assert len(cells) == len(node.children)
    rows: dict[int, list[float]] = {}
    cols: dict[int, list[float]] = {}
    for child, (row, col) in zip(node.children, cells):
        rows.setdefault(row, []).append(child.bbox.center.y)
        cols.setdefault(col, []).append(child.bbox.center.x)
    assert len(rows) == 2 and len(cols) == 3
    for line in (*rows.values(), *cols.values()):
        assert max(line) - min(line) < 1e-9


def test_the_grid_notes_survive_being_placed():
    node = inklet.grid([inklet.box(str(i)) for i in range(4)], cols=2, gap=3.0)
    moved = node.translated(10.0, 0.0)
    assert moved.notes["grid_cells"] == node.notes["grid_cells"]
    assert moved.notes["col_gap"] == node.notes["col_gap"]


def test_one_gap_still_means_both():
    node = inklet.grid([inklet.box(str(i)) for i in range(4)], cols=2, gap=5.0)
    assert node.notes["col_gap"] == node.notes["row_gap"] == 5.0


# -- as_drawn is deliberately not part of any of this ---------------------


def test_as_drawn_still_reads_only_its_own_origin():
    """M16's limit, unchanged: notes look through a wrapper now, anchors do
    not, because a wrapper round a drawn shape is a placement someone meant.
    """
    node = inklet.polyline([(0.0, 0.0), (10.0, 5.0)])
    moved = node.translated(4.0, 4.0)
    assert as_drawn(moved) is moved
