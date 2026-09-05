"""`OFF_PANEL` -- a label that leaves through the wall of its own plot box.

The shape is `figures/structure.py` panel (d): a y domain that runs past the
top tick, a curve that reaches most of the way there, and a label lifted a
fixed number of data units above that curve. Written from the shape rather
than from the figure, which is another agent's and takes eight seconds to
render; the numbers below are its numbers.
"""

from __future__ import annotations

import inklet

# panel (d)'s own: 84 x 40mm, y from -6 to 42 with the axis marked to 40, and
# a wild-type curve that tops out at 36 response units.
BOX = (84.0, 40.0)
X_RANGE = (-18.0, 660.0)
Y_RANGE = (-6.0, 42.0)
TOP_OF_CURVE = 36.0


def titration(lift: float, *, outline: bool = True) -> inklet.Diagram:
    """One curve and one label `lift` response units above its top."""
    p = inklet.panel(*BOX, x=X_RANGE, y=Y_RANGE)
    p.line([(0.0, 0.0), (200.0, 12.0), (400.0, 30.0), (660.0, TOP_OF_CURVE)],
           name="wild type")
    p.text(400.0, TOP_OF_CURVE + lift, "40 nM", anchor="s",
           size=1.4, kind="label")
    p.axis("bottom", ticks=[0, 300, 600], label="time (s)")
    p.axis("left", ticks=[0, 20, 40], label="response (RU)")
    if outline:
        p.outline()
    return p.build()


def off_panel(node: inklet.Diagram) -> list[str]:
    fig = inklet.figure(width="96mm")
    fig.add(node)
    return [d.message for d in fig.lint() if d.code == "OFF_PANEL"]


def test_a_label_lifted_out_of_the_plot_box_is_reported():
    """Five units above 36 is 41, in a box that stops at 42, and the type is
    1.4mm tall. Half of it is outside the frame and nothing said so."""
    found = off_panel(titration(lift=5.0))

    assert len(found) == 1, found
    assert "40 nM" in found[0]
    assert "leaves" in found[0] and "on the top" in found[0]


def test_the_clamp_the_figure_had_to_compute_for_itself_silences_it():
    """`lift = min(5.0, D_TOP - 0.6 - tall - level)` is what
    `figures/structure.py` writes to keep the label under the roof. With the
    clamp there is nothing to report -- which is the check that the rule is
    measuring the wall and not the lift."""
    assert off_panel(titration(lift=1.5)) == []


def test_the_grade_is_info_because_the_ink_is_still_on_the_page():
    fig = inklet.figure(width="96mm")
    fig.add(titration(lift=5.0))
    grades = {d.severity for d in fig.lint() if d.code == "OFF_PANEL"}

    assert grades == {"info"}


def test_axis_furniture_outside_the_box_is_not_a_finding():
    """Every tick label and both axis titles sit outside the plot area on
    purpose. A rule that reported them would report every panel ever built."""
    p = inklet.panel(*BOX, x=X_RANGE, y=Y_RANGE)
    p.line([(0.0, 0.0), (660.0, 20.0)], name="wild type")
    p.axis("bottom", ticks=[0, 300, 600], label="time (s)")
    p.axis("left", ticks=[0, 20, 40], label="response (RU)")
    p.outline()

    assert off_panel(p.build()) == []


def test_a_panel_with_no_frame_drawn_is_still_measured():
    """The frame is what makes the clipping *visible*, not what makes it
    wrong: the label has left the region the axes are a scale for either way,
    and a panel outlined later would clip it then."""
    assert len(off_panel(titration(lift=5.0, outline=False))) == 1


def test_a_lettered_panel_reports_once_and_not_twice():
    """`letters` carries the `plot_area` note onto the two-child wrapper it
    puts round the panel, so a label inside one has two ancestors declaring
    the same rectangle. The nearest is the one that answers."""
    found = off_panel(inklet.letters([titration(lift=5.0)])[0])

    assert len(found) == 1, found


def test_a_diagram_that_is_not_a_panel_says_nothing():
    """Nothing outside the plot layer declares a plot box, and a rule that
    guessed one from a bounding box would fire on every label in the library.
    """
    fig = inklet.figure(width="60mm")
    fig.add(inklet.vstack([inklet.box("a"), inklet.text("a caption")], gap=2))

    assert [d for d in fig.lint() if d.code == "OFF_PANEL"] == []


def test_a_legend_the_plot_layer_put_above_the_frame_is_not_a_finding():
    """`side="top"` puts the legend above the plot box, and its entry text
    dips a couple of tenths of a millimetre back inside the frame -- enough to
    overlap, so the geometric exemption that covers tick labels does not cover
    this. Without the structural one, every panel with a legend on it earns a
    line in the report."""
    p = inklet.panel(*BOX, x=X_RANGE, y=Y_RANGE)
    p.line([(0.0, 0.0), (660.0, 20.0)], name="wild type")
    p.legend(side="top")
    p.axis("bottom", ticks=[0, 300, 600], label="time (s)")
    p.axis("left", ticks=[0, 20, 40], label="response (RU)")
    p.outline()

    assert off_panel(p.build()) == []


def test_the_label_is_still_reported_on_a_panel_that_has_a_legend():
    """The exemption is the furniture, not the panel it is on."""
    p = inklet.panel(*BOX, x=X_RANGE, y=Y_RANGE)
    p.line([(0.0, 0.0), (660.0, TOP_OF_CURVE)], name="wild type")
    p.text(400.0, TOP_OF_CURVE + 5.0, "40 nM", anchor="s", size=1.4,
           kind="label")
    p.legend(side="top")
    p.outline()

    found = off_panel(p.build())
    assert len(found) == 1 and "40 nM" in found[0], found
