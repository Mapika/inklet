"""Regression tests for the key and legend fixes.

One test per reported item: a second `legend()` call replaces the first, the
`size=` suggestion, key order for bands, reference lines and spans with `name=`,
a key in an empty grid cell, and the LayoutError that names an outside key.
"""

import pytest

import inklet as i
from inklet.diagnostics import lint
from inklet.plot.key import LEGEND_KIND


def _legend_nodes(panel):
    return [node for node in panel.build().walk() if node.kind == LEGEND_KIND]


def _svg(panel, font="single-column"):
    doc = i.preset("scientific.nature", format=font).document()
    doc.add("a", panel)
    return doc.compile().to_svg()


def _keyed_panel():
    p = i.panel(70, 50, x=(0, 10), y=(-1, 1), clip=True)
    p.scatter([(1, 0.5), (2, -0.5)], color="#1E90FF", size=1.5, name="Group A")
    p.scatter([(3, 0.2), (4, -0.2)], color="#DAA520", size=1.5, name="Group B")
    p.line([(0, 0.8), (10, 0.8)], stroke="#B2182B", name="Curve X")
    p.line([(0, -0.8), (10, -0.8)], stroke="#FF7256", name="Curve Y")
    p.axes(x="x", y="y")
    return p


# -- 1. a second legend() call replaces the first ----------------------------


def test_a_second_legend_call_replaces_the_first_key():
    p = _keyed_panel()
    p.legend(corner="ne", names=["Group A", "Group B"])
    p.legend(corner="se", names=["Curve X", "Curve Y"])
    assert len(_legend_nodes(p)) == 1


def test_a_second_legend_call_sets_the_options_drawn():
    p = _keyed_panel()
    p.legend(corner="ne", names=["Group A", "Group B"])
    p.legend(corner="se", names=["Curve X"])
    svg = _svg(p)
    assert "Curve X" in svg
    assert "Group A" not in svg and "Curve Y" not in svg


def test_a_failed_second_legend_call_keeps_the_first_key():
    p = _keyed_panel()
    p.legend(corner="ne", names=["Group A"])
    with pytest.raises(Exception):
        p.legend(corner="ne", names=["No such series"])
    assert len(_legend_nodes(p)) == 1
    assert "Group A" in _svg(p)


# -- 2. size= suggests font_size= --------------------------------------------


def test_legend_size_suggests_font_size_on_a_panel():
    with pytest.raises(TypeError, match=r"did you mean font_size=\?"):
        _keyed_panel().legend(corner="nw", size="7pt")


def test_legend_size_suggests_font_size_on_a_recorded_plot():
    spec = i.plot_spec(70, 50, x=(0, 10), y=(-1, 1))
    with pytest.raises(TypeError, match=r"did you mean font_size=\?"):
        spec.legend(corner="nw", size="7pt")


def test_legend_font_size_still_works():
    p = _keyed_panel()
    p.legend(corner="nw", font_size="7pt")
    assert len(_legend_nodes(p)) == 1


# -- 3. key order: a band does not count as the first draw --------------------


def _band_then_line_panel():
    p = i.panel(70, 50, x=(0, 10), y=(-1, 1))
    t = list(range(11))
    p.band(t, [-1] * 11, [-0.5] * 11, name="excess")
    p.line([(x, 0.2) for x in t], name="reported")
    p.line([(x, -0.2) for x in t], name="excess")
    return p


def test_a_band_drawn_before_its_line_does_not_put_the_series_first():
    assert [entry.name for entry in _band_then_line_panel().keys] == ["reported", "excess"]


def test_a_band_only_series_keeps_its_drawing_place():
    p = i.panel(70, 50, x=(0, 10), y=(-1, 1))
    p.line([(0, 0.2), (10, 0.2)], name="line first")
    p.band(list(range(11)), [-1] * 11, [-0.5] * 11, name="band only")
    assert [entry.name for entry in p.keys] == ["line first", "band only"]


def test_names_orders_band_entries():
    p = _band_then_line_panel()
    rows = p._legend_rows(None, ["reported", "excess"])
    assert [name for name, _ in rows] == ["reported", "excess"]
    p.legend(names=["excess", "reported"], side="bottom")
    assert "excess" in _svg(p)


# -- 6. reference lines and spans take name= ----------------------------------


@pytest.mark.parametrize("method, args, form", [
    ("vline", (0.5,), "line"),
    ("hline", (0.5,), "line"),
    ("vspan", (0.2, 0.4), "area"),
    ("hspan", (0.2, 0.4), "area"),
])
def test_reference_marks_take_name_and_key_it(method, args, form):
    p = i.panel(40, 30, x=(0, 1), y=(0, 1))
    getattr(p, method)(*args, name="top 1%")
    (entry,) = [entry for entry in p.keys if entry.name == "top 1%"]
    assert form in entry.forms
    p.legend(corner="ne")
    assert len(_legend_nodes(p)) == 1


def test_a_named_rule_swatch_is_drawn_in_the_rule_paint():
    p = i.panel(40, 30, x=(0, 1), y=(0, 1))
    p.vline(0.5, name="cut", stroke="#B2182B", stroke_width=0.4)
    (entry,) = p.keys
    assert entry.color == "#B2182B"
    assert entry.width == 0.4


def test_a_named_span_swatch_is_the_span_fill():
    p = i.panel(40, 30, x=(0, 1), y=(0, 1))
    p.hspan(0.2, 0.4, name="target", color="#DAA520")
    (entry,) = p.keys
    assert entry.fill == "#DAA520"


def test_an_unnamed_reference_mark_is_not_keyed():
    p = i.panel(40, 30, x=(0, 1), y=(0, 1))
    p.vline(0.5).hspan(0.2, 0.4)
    assert p.keys == ()


# -- 4. a key in an empty grid cell -----------------------------------------


def _grid_panel(k):
    p = i.panel(24, 20, x=(0, 10), y=(0, 1))
    p.band([0, 5, 10], [0.1, 0.2, 0.1], [0.5, 0.6, 0.5], color="#1E90FF", name="Group A")
    p.line([(0, 0.3), (10, 0.4)], stroke="#1E90FF", name="Group A")
    p.line([(0, 0.7), (10, 0.6)], stroke="#DAA520", name="Group B")
    p.vline(5, name="cut point")
    p.hspan(0.8, 0.9, name="target band", color="#B2182B")
    p.axes(x="x", y="y")
    return p


def test_key_diagram_fills_an_empty_grid_cell_without_lint_findings():
    panels = [_grid_panel(k) for k in range(7)]
    cell = panels[0].key_diagram(title="Encoding")
    grid = i.facets(panels + [cell], cols=4)
    doc = i.preset("scientific.nature", format="double-column").document()
    doc.add("grid", grid)
    findings = [d.code for d in doc.compile().lint() if d.severity != "info"]
    assert "KEY_MISMATCH" not in findings


def test_key_diagram_rows_follow_names():
    p = _grid_panel(0)
    doc = i.preset("scientific.nature", format="single-column").document()
    doc.add("cell", p.key_diagram(names=["Group B", "Group A"]))
    svg = doc.compile().to_svg()
    assert svg.index("Group B") < svg.index("Group A")
    assert "cut point" not in svg


def test_key_diagram_needs_a_named_series():
    with pytest.raises(i.DiagramError, match="key_diagram"):
        i.panel(40, 30, x=(0, 1), y=(0, 1)).key_diagram()


# -- 5. an outside key too wide for its cell is named as the cause -----------


def _narrow_cell_document(**legend):
    doc = i.document(width=170, columns=4)
    for column in range(4):
        p = i.panel(30, 30, x=(0, 1), y=(0, 1))
        p.line([(0, 0.2), (1, 0.8)], name="alpha curve")
        p.line([(0, 0.5), (1, 0.4)], name="beta curve")
        p.line([(0, 0.9), (1, 0.1)], name="gamma curve")
        p.axes(x="x", y="y")
        p.legend(side="top", **legend)
        doc.add(f"c{column}", p, row=0, column=column)
    return doc


def test_a_top_key_wider_than_its_cell_is_named_as_the_cause():
    with pytest.raises(i.LayoutError, match=r"The top key is [\d.]+ mm wide") as error:
        _narrow_cell_document(columns=3).compile()
    message = str(error.value)
    assert "columns=" in message and "corner=" in message


def test_a_key_that_fits_its_cell_is_not_blamed():
    with pytest.raises(i.LayoutError) as error:
        _narrow_cell_document(columns=1).compile()
    assert "key" not in str(error.value)


def test_a_top_key_a_hair_wider_than_its_cell_is_named_not_left_to_run_away():
    # A centred top key wider than its cell overhangs both sides of the data;
    # each measurement pass widens the margins by the overhang, so the layout
    # never settles. The error must name the key, not the loop.
    p = i.plot_spec(50, 30, x=(0, 1), y=(0, 1))
    for k in range(4):
        p.line([(0, k / 4), (1, k / 4)], name=f"series {k} " + "w" * 14)
    p.axes(x="x", y="y").legend(side="top", columns=2)
    doc = i.preset("scientific.nature", format="single-column").document()
    doc.add("only", p)
    with pytest.raises(i.LayoutError, match=r"The top key is [\d.]+ mm wide") as error:
        doc.compile()
    assert "did not settle" not in str(error.value)
    assert "columns=" in str(error.value)
