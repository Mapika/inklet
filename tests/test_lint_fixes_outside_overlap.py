"""Three lint gaps: data drawn outside its axes, two labels set on one point,
and a run of crowded tick labels reported once per pair.

Each test builds the smallest figure that shows the fault (or the case that
must stay quiet) and reads the diagnostics back the way an agent does.
"""

from __future__ import annotations

import inklet as i


def codes(diags, code):
    return [d for d in diags if d.code == code]


def _plot(**ranges):
    p = i.plot_spec(**ranges)
    return p


def _compiled(spec):
    doc = i.publication("single-column").document()
    doc.add("a", spec)
    return doc.compile()


# -- DATA_OUTSIDE -----------------------------------------------------------


def test_a_line_running_above_the_axes_is_a_warning_with_the_range_to_set():
    p = _plot(x=(0, 4), y=(0, 2))
    p.line([(1, 1), (2, 3), (3, 2), (4, 4)])
    p.axes(x="x", y="y")
    found = codes(_compiled(p).lint(), "DATA_OUTSIDE")

    assert len(found) == 1, found
    finding = found[0]
    assert finding.severity == "warning"
    assert "past the top" in finding.message
    assert "y = 4" in finding.message and "stops at 2" in finding.message
    assert "widen the y range to (0, 4)" in finding.hint
    assert "clip=True" in finding.hint


def test_clip_true_silences_it():
    p = _plot(x=(0, 4), y=(0, 2))
    p.line([(1, 1), (2, 3), (3, 2), (4, 4)], clip=True)
    p.axes(x="x", y="y")
    assert codes(_compiled(p).lint(), "DATA_OUTSIDE") == []


def test_a_range_that_holds_the_data_is_clean():
    p = _plot(x=(0, 4), y=(0, 4))
    p.line([(1, 1), (2, 3), (3, 2), (4, 4)])
    p.axes(x="x", y="y")
    assert codes(_compiled(p).lint(), "DATA_OUTSIDE") == []


def test_markers_and_error_caps_on_the_axis_edge_are_where_they_belong():
    """A marker centred on the edge has half its disc outside the box, and a
    cap on the first category sticks out by half its width. Neither is data
    outside the axes."""
    p = i.panel(50, 35, x=(0, 4), y=(0, 10))
    p.scatter([(0, 0), (4, 10), (0, 10), (4, 0)], size=3)
    p.errorbars([(0, 5), (4, 5)], yerr=[1, 1])
    p.axes()
    node = p.build()
    assert codes(i.lint(node, page=node.bbox), "DATA_OUTSIDE") == []


def test_one_finding_per_panel_however_many_marks_leave_it():
    p = i.panel(50, 35, x=(0, 4), y=(-1, 1))
    p.scatter([(0, -1), (5, 1), (6, 0)])
    p.line([(0, 0), (4, 3)])
    p.axes()
    node = p.build()
    found = codes(i.lint(node, page=node.bbox), "DATA_OUTSIDE")

    assert len(found) == 1, found
    # two markers past the right, one line past the top: one finding
    assert "3 marks reach" in found[0].message
    assert "past the top" in found[0].message and "past the right" in found[0].message
    assert len(found[0].targets) == 3


def test_keys_outside_the_box_are_not_data():
    p = i.panel(50, 35, x=(0, 4), y=(-1, 1))
    p.line([(0, 0), (4, 0.5)], name="a").line([(0, 0.2), (4, -0.5)], name="b")
    p.axes().legend(side="right")
    node = p.build()
    assert codes(i.lint(node, page=node.bbox), "DATA_OUTSIDE") == []


def test_matrix_cells_bleeding_past_the_edge_by_design_are_quiet():
    """`matrix` grows every cell 6% past its pitch to bury the seams, and the
    outer cells carry that past the box edge."""
    p = i.panel(80, 35, x=(0, 2), y=(0, 2)).matrix([[1, 2], [3, 4]]).axes()
    node = p.build()
    assert codes(i.lint(node, page=node.bbox), "DATA_OUTSIDE") == []


def test_an_unruled_panel_has_no_axes_to_be_outside_of():
    p = i.panel(50, 35, x=(0, 1), y=(0, 1))
    p.line([(0, 0), (3, 3)])
    node = p.build()
    assert codes(i.lint(node, page=node.bbox), "DATA_OUTSIDE") == []


def test_a_twin_axis_gives_no_number_rather_than_a_wrong_one():
    p = i.panel(50, 35, x=(0, 4), y=(0, 2))
    p.line([(0, 0), (4, 3)])
    p.axes()
    p.twin_y((10, 30)).line([(0, 12), (4, 20)])
    node = p.build()
    found = codes(i.lint(node, page=node.bbox), "DATA_OUTSIDE")

    assert len(found) == 1, found
    assert "widen the y range at the top" in found[0].hint


def test_line_end_labels_are_set_beside_the_box_on_purpose():
    d = {"t": [0, 1, 2, 3] * 3, "v": [1, 2, 3, 4, 2, 3, 3, 5, 1, 1, 2, 2],
         "g": ["wild type"] * 4 + ["knockout"] * 4 + ["rescue"] * 4}
    diags = i.line(d, x="t", y="v", color="g", legend="direct").compile().lint()
    assert codes(diags, "OFF_PANEL") == []
    assert codes(diags, "DATA_OUTSIDE") == []


# -- OVERLAP: two labels on one point ----------------------------------------


def test_two_labels_set_on_the_same_point_overlap():
    c = i.chart(xlim=(0, 1), ylim=(0, 1))
    c.spec.text(0.5, 0.5, "first label")
    c.spec.text(0.5, 0.5, "second label")
    found = codes(c.compile().lint(), "OVERLAP")

    assert len(found) == 1, found
    assert found[0].severity == "error"
    assert "'first label'" in found[0].message
    assert "'second label'" in found[0].message


def test_the_same_words_drawn_twice_in_one_place_read_as_one_label():
    c = i.chart(xlim=(0, 1), ylim=(0, 1))
    c.spec.text(0.5, 0.5, "same")
    c.spec.text(0.5, 0.5, "same")
    assert codes(c.compile().lint(), "OVERLAP") == []


# -- grouping a run of pairwise collisions -----------------------------------


LONG = [f"a very long category label number {k}" for k in range(8)]


def _crowded_bars():
    return i.bar({"c": LONG, "v": list(range(8))}, x="c", y="v").axes(x="c", y="v")


def test_crowded_tick_labels_are_one_finding_not_one_per_pair():
    diags = _crowded_bars().compile().lint()
    found = [d for d in diags if d.code in ("OVERLAP", "CROWDING")]

    assert len(found) == 1, [d.message for d in found]
    finding = found[0]
    assert finding.code == "OVERLAP" and finding.severity == "error"
    assert finding.message.startswith("8 x-axis tick labels")
    assert len(finding.targets) == 8
    assert "rotate" in finding.hint and "x_options" in finding.hint


def test_the_grouped_message_still_quotes_the_labels_for_quick():
    """`inklet.quick` decides to turn category labels by finding two quoted
    category names in one OVERLAP or CROWDING message."""
    from inklet.quick import _labels_collide

    figure = _crowded_bars().compile()
    assert _labels_collide(figure, LONG)


def test_the_hint_it_gives_fixes_it():
    rotated = i.bar({"c": LONG, "v": list(range(8))}, x="c", y="v").axes(
        x="c", y="v", x_options={"rotate": 45})
    diags = rotated.compile().lint()
    assert [d for d in diags if d.code in ("OVERLAP", "CROWDING")] == []


def test_an_isolated_pair_keeps_its_own_line():
    c = i.chart(xlim=(0, 1), ylim=(0, 1))
    c.spec.text(0.2, 0.2, "first label")
    c.spec.text(0.2, 0.2, "second label")
    c.spec.text(0.8, 0.8, "third label")
    c.spec.text(0.8, 0.8, "fourth label")
    found = codes(c.compile().lint(), "OVERLAP")

    assert len(found) == 2, [d.message for d in found]
    assert all(len(d.targets) == 2 for d in found)
