"""Lint fixes for the fonts, clipping, blank cells, strokes, acknowledged
findings, inset type size and label clearance, found while recreating six
published figures.

Each test builds the smallest figure that shows the fault, or the case that
must stay quiet, and reads the diagnostics back the way an agent does.
"""

from __future__ import annotations

import numpy as np
import pytest

import inklet as i


def codes(diags, code):
    return [d for d in diags if d.code == code]


def _compiled(spec, preset=None):
    doc = (i.preset(preset, format="single-column").document() if preset
           else i.document(width=80))
    doc.add("a", spec)
    return doc.compile()


def _nature_figure():
    """A small Nature-profile figure, set in whatever font the machine has."""
    p = i.plot_spec(60, 30, x=(0, 1), y=(0, 1))
    p.line(np.c_[np.linspace(0, 1, 5), np.linspace(0, 1, 5)], name="a")
    p.axes(x="Time", y="Value")
    return _compiled(p, preset="scientific.nature")


# -- FONT_SUBSTITUTED ---------------------------------------------------------


def test_a_metric_clone_of_arial_is_information_not_a_warning():
    found = codes(_nature_figure().lint(), "FONT_SUBSTITUTED")

    assert len(found) == 1, found
    assert found[0].severity == "info"
    assert "same metrics as 'Arial'" in found[0].message
    assert "will not shift" in found[0].message
    assert "not the journal's named font" in found[0].message


def test_a_substitute_that_is_not_a_clone_stays_a_warning():
    p = i.plot_spec(60, 30, x=(0, 1), y=(0, 1))
    p.line([(0, 0), (1, 1)], name="a")
    p.axes(x="Time", y="Value")
    diags = _compiled(p, preset="scientific.nature").lint(
        expected_fonts=("Times New Roman",))

    found = codes(diags, "FONT_SUBSTITUTED")
    assert len(found) == 1, found
    assert found[0].severity == "warning"


def test_arimo_and_tinos_are_clones_of_the_fonts_they_stand_in_for():
    from inklet.diagnostics.rules import _clone_of

    assert _clone_of("Arimo", ("Arial", "Helvetica")) == "Arial"
    assert _clone_of("Liberation Serif", ("Times New Roman",)) == "Times New Roman"
    assert _clone_of("Tinos", ("Times",)) == "Times"
    assert _clone_of("Cousine", ("Courier New",)) == "Courier New"
    assert _clone_of("Liberation Mono", ("Arial",)) is None
    assert _clone_of("DejaVu Sans", ("Arial",)) is None


def test_one_font_pair_is_one_finding_however_many_texts_it_reaches():
    p = i.plot_spec(60, 40, x=(0, 1), y=(0, 1))
    p.line(np.c_[np.linspace(0, 1, 5), np.linspace(0, 1, 5)], name="a")
    for k in range(12):
        p.text(0.1 + 0.07 * k, 0.5, f"note {k}", font_size=1.2)
    p.axes(x="Time", y="Value")
    found = codes(_compiled(p, preset="scientific.nature").lint(),
                  "FONT_SUBSTITUTED")

    assert len(found) == 1, found
    assert "+" in found[0].message  # the first few are named, the rest counted


# -- DATA_CLIPPED and MARKER_CUT ----------------------------------------------


def test_points_hidden_by_clip_true_are_counted_per_named_series():
    p = i.plot_spec(40, 30, x=(0, 1), y=(0, 5), clip=True)
    p.line([(0, 1), (0.5, 9), (1, 1)], name="spike")
    p.axes()
    found = codes(_compiled(p).lint(), "DATA_CLIPPED")

    assert len(found) == 1, found
    assert found[0].severity == "info"
    assert "'spike'" in found[0].message
    assert "1 point" in found[0].message


def test_a_line_clipped_at_the_edge_does_not_warn():
    p = i.plot_spec(40, 30, x=(0, 1), y=(0, 5), clip=True)
    p.line([(0, 1), (0.5, 9), (1, 1)], name="spike")
    p.axes()
    diags = _compiled(p).lint()

    assert not codes(diags, "MARKER_CUT")
    assert not codes(diags, "DATA_OUTSIDE")


def test_markers_straddling_the_clip_edge_warn():
    p = i.plot_spec(30, 25, x=(0, 1), y=(0, 1), clip=True)
    p.scatter([(0.3, 1.3), (0.6, 1.0), (0.8, 0.5)], size=1.5, name="points")
    p.axes()
    diags = _compiled(p).lint()

    hidden = codes(diags, "DATA_CLIPPED")
    cut = codes(diags, "MARKER_CUT")
    assert len(hidden) == 1 and "'points'" in hidden[0].message, hidden
    assert len(cut) == 1 and cut[0].severity == "warning", cut
    assert "'points'" in cut[0].message


def test_markers_inside_the_range_are_quiet_with_clip_true():
    p = i.plot_spec(30, 25, x=(0, 1), y=(0, 1), clip=True)
    p.scatter([(0.3, 0.3), (0.6, 0.5), (0.8, 0.5)], size=1.5, name="points")
    p.axes()
    diags = _compiled(p).lint()

    assert not codes(diags, "DATA_CLIPPED")
    assert not codes(diags, "MARKER_CUT")


def test_a_packed_scatter_reports_its_hidden_points_too():
    rng = np.random.default_rng(1)
    pts = rng.uniform(0, 1, size=(300, 2))
    pts[:5, 1] = 1.4     # wholly above the axes: hidden
    p = i.plot_spec(40, 30, x=(0, 1), y=(0, 1), clip=True)
    p.scatter(pts, size=1.5, name="many")
    p.axes()
    diags = _compiled(p).lint()

    found = codes(diags, "DATA_CLIPPED")
    assert len(found) == 1 and "5 points" in found[0].message, found
    assert "'many'" in found[0].message


# -- blank matrix cells -------------------------------------------------------


def _heatmap_under_label(missing=None, value=0.0, vector="cells", label_on=None):
    vals = [[value] * 10 for _ in range(10)]
    vals[5][5] = 1.0
    if label_on is not None:
        vals[label_on[0]][label_on[1]] = label_on[2]
    r = i.plot_spec(50, 50, x=(0, 10), y=(0, 10))
    kwargs = {} if missing is None else {"missing": missing}
    r.matrix(vals, ramp=i.ramp("viridis"), vector=vector, **kwargs)
    r.text(2, 2, "label over the bins")
    return _compiled(r, preset="scientific.nature").lint()


def test_a_label_over_blank_cells_is_not_an_overlap():
    vals = [[None] * 10 for _ in range(10)]
    vals[5][5] = 1.0
    r = i.plot_spec(50, 50, x=(0, 10), y=(0, 10))
    r.matrix(vals, ramp=i.ramp("viridis"), missing="#ffffff")
    r.text(2, 2, "label over empty cells")
    diags = _compiled(r, preset="scientific.nature").lint()

    assert not codes(diags, "OVERLAP")
    assert not codes(diags, "CROWDING")


def test_a_label_over_zero_cells_is_not_an_overlap():
    diags = _heatmap_under_label(value=0.0)
    assert not codes(diags, "OVERLAP")


def test_blank_cells_stay_out_of_the_batched_matrix_too():
    vals = [[None] * 10 for _ in range(10)]
    vals[5][5] = 1.0
    r = i.plot_spec(50, 50, x=(0, 10), y=(0, 10))
    r.matrix(vals, ramp=i.ramp("viridis"), missing="#ffffff", vector="batched")
    r.text(2, 2, "label over empty cells")
    diags = _compiled(r, preset="scientific.nature").lint()

    assert not codes(diags, "OVERLAP")


def test_a_label_over_a_filled_cell_still_overlaps():
    # The control: blank cells are exempt, drawn data is not.
    vals = [[1.0] * 10 for _ in range(10)]
    r = i.plot_spec(50, 50, x=(0, 10), y=(0, 10))
    r.matrix(vals, ramp=i.ramp("viridis"))
    r.text(2, 2, "label over data")
    diags = _compiled(r, preset="scientific.nature").lint()

    assert codes(diags, "OVERLAP"), diags


# -- INCONSISTENT_STROKE ------------------------------------------------------


def _strokes(max_widths, **plot):
    p = i.plot_spec(60, 40, x=(0, 10), y=(0, 10))
    xs = np.linspace(0, 10, 6)
    p.line(np.c_[xs, xs * 0.5 + 2], name="Data", stroke_width=0.6, stroke="#c00",
           err=0.5, err_style="bars")
    p.line([(0, 2), (10, 8)], name="Fit", stroke_width=0.9, stroke="#0c0")
    p.axes(x="x", y="y", **plot.get("axes", {}))
    p.legend()
    doc = i.preset("scientific.nature", format="single-column").document()
    doc.add("a", p)
    return doc.compile().lint(max_stroke_widths=max_widths)


def _stroke_message(diags):
    found = codes(diags, "INCONSISTENT_STROKE")
    assert len(found) == 1, found
    return found[0].message


def test_library_strokes_are_not_counted_against_the_budget():
    # Spines, ticks and legend swatches are the theme's, not the author's:
    # with a budget of 2 the figure has two weights of its own, and stays quiet.
    diags = _strokes(max_widths=3)
    assert not codes(diags, "INCONSISTENT_STROKE")


def test_the_message_names_each_weight_by_what_it_is():
    message = _stroke_message(_strokes(max_widths=1))

    assert "(errorbars 'Data')" in message
    assert "(line 'Fit')" in message
    assert "0.60mm on 1 (line 'Data')" in message
    assert "cell-" not in message     # no bare ids in the listing


def test_an_axis_the_author_gave_a_width_is_counted():
    message = _stroke_message(_strokes(max_widths=1, axes={"stroke_width": 0.9}))

    # The 0.90 weight is the author's line and the axis furniture, both at 0.9.
    assert "0.90mm on 15 (axis ticks, axis spine, line 'Fit')" in message


def test_error_bar_caps_are_not_crowding_obstacles():
    # A label beside an error bar's cap is not a crowding finding: the caps are
    # the library's and unfilled, and nothing measures them as obstacles.
    p = i.plot_spec(50, 40, x=(0, 10), y=(0, 10))
    p.errorbars([(2, 5)], yerr=2.0, cap=1.5)
    p.text(2.6, 7.0, "beside cap", font_size=1.4)
    p.axes(x="x", y="y")
    diags = _compiled(p, preset="scientific.nature").lint()

    assert not codes(diags, "CROWDING")


# -- expect= acknowledgement --------------------------------------------------


def _flat_series_figure():
    p = i.plot_spec(60, 40, x=(0, 10), y=(0, 5000))
    p.line([(0, 0), (5, 4000), (10, 5000)], name="big")
    p.line([(0, 0.5), (5, 0.6), (10, 0.5)], name="flat")
    p.axes(x="x", y="y")
    return _compiled(p)


def test_an_expected_code_is_acknowledged_not_a_warning():
    doc = _flat_series_figure()
    assert codes(doc.lint(), "SERIES_FLATTENED")[0].severity == "warning"

    acknowledged = codes(doc.lint(expect={"SERIES_FLATTENED"}), "SERIES_FLATTENED")
    assert len(acknowledged) == 1
    assert acknowledged[0].severity == "acknowledged"


def test_the_report_lists_acknowledged_findings_in_their_own_section():
    report = _flat_series_figure().report(expect={"SERIES_FLATTENED"})

    assert "ACKNOWLEDGED" in report
    assert "\nWARNING" not in report
    assert "pass expect=" in codes(_flat_series_figure().lint(), "SERIES_FLATTENED")[0].hint


def test_a_misspelt_expect_code_is_refused():
    with pytest.raises(ValueError, match="SERIES_FLATENED"):
        _flat_series_figure().lint(expect={"SERIES_FLATENED"})


# -- TINY_TEXT in a scaled inset ----------------------------------------------


def _katrin_inset(width):
    sub = i.plot_spec(height=36, x=(-10, 3), y=(0.5, 7.5), clip=True)
    sub.line([(-9, 7), (2, 7)], stroke="#1f7ae0")
    sub.axes(x=None, y=None, x_options=dict(ticks=[-8, -6, -4, -2, 0, 2]))
    main = i.plot_spec(60, 86, x=(-240, 70), y=(0.5, 14.5), clip=True)
    main.line([(-226, 14), (-68, 14)], stroke="#127d7d")
    main.axis("left", ticks=[14, 1], format=lambda v: "KATRIN (combined)")
    main.inset(sub, corner="sw", width=width, zoom=(-10, 3, 0.5, 7.5))
    return _compiled(main, preset="scientific.nature").lint()


def test_a_text_shrunk_by_an_inset_names_the_inset_and_the_real_fix():
    tiny = codes(_katrin_inset(width=0.5), "TINY_TEXT")

    assert tiny, "the 0.5-width inset should shrink its ticks below 5 pt"
    assert "width=None" in tiny[0].hint
    assert "set font_size" not in tiny[0].hint


def test_an_inset_built_at_its_printed_size_keeps_its_text():
    assert not codes(_katrin_inset(width=None), "TINY_TEXT")
