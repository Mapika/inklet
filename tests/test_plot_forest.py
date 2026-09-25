"""inklet.forest and plot.forest_layout."""

from __future__ import annotations

import pytest

import inklet
from inklet import use_theme
from inklet.core import DiagramError, resolve
from inklet.diagnostics import lint
from inklet.draw.coords import plot_area
from inklet.draw.shapes import MARK_KIND, MARK_LINE_KIND
from inklet.plot import ForestRow, forest_layout
from inklet.plot.axis import TICK_LABEL_KIND


@pytest.fixture(autouse=True)
def _theme():
    use_theme("nature")


ROWS = [
    "Adults",
    {"label": "Ahmed 2019", "estimate": 0.72, "low": 0.55, "high": 0.94,
     "weight": 18.2, "n": 812},
    {"label": "Berg 2020", "estimate": 0.91, "low": 0.62, "high": 1.33,
     "weight": 4.55, "n": 355},
    {"label": "Subtotal", "estimate": 0.77, "low": 0.63, "high": 0.94,
     "summary": True},
    "Children",
    ("Evans 2022", 0.58, 0.08, 6.4),
    {"label": "Overall", "estimate": 0.81, "low": 0.68, "high": 0.96,
     "summary": True},
]


def placements(node, kind):
    return [x for x in resolve(node).values() if x.diagram.kind == kind]


def polygons(node, corners):
    return [m for m in placements(node, MARK_KIND)
            if type(m.diagram.prim).__name__ == "PathPrim"
            and len(m.diagram.prim.subpaths[0].points) == corners]


def squares(node):
    return sorted((m for m in placements(node, MARK_KIND)
                   if type(m.diagram.prim).__name__ == "RectPrim"),
                  key=lambda m: -m.bbox.width)


def texts(node):
    return {x.diagram.prim.text if hasattr(x.diagram.prim, "text") else None: x
            for x in placements(node, TICK_LABEL_KIND)}


def test_layout_reads_every_row_form_and_indents_groups() -> None:
    layout = forest_layout(ROWS, log=True)
    kinds = [r.kind for r in layout.rows]
    assert kinds == ["header", "study", "study", "summary", "header", "study",
                     "summary"]
    assert [r.indent for r in layout.rows] == [False, True, True, False, False,
                                               True, False]
    assert layout.rows[1].values == {"n": 812}
    assert layout.null == 1.0
    # Round 1-2-5 limits hold every interval.
    assert layout.limits == (0.05, 10.0)
    assert layout.clipped == ()
    assert forest_layout([("a", 1.0, -2.0, 3.0)]).null == 0.0
    assert forest_layout([ForestRow("a", 2.0, 1.0, 3.0)], null=2.0).null == 2.0


def test_limits_clip_intervals_and_draw_arrowheads() -> None:
    layout = forest_layout(ROWS, log=True, limits=(0.2, 5))
    assert layout.clipped == ((5, "low"), (5, "high"))
    plain = inklet.forest(ROWS, log=True)
    cut = inklet.forest(ROWS, log=True, limits=(0.2, 5))
    assert cut.notes["forest"]["clipped"] == [(5, "low"), (5, "high")]
    # Two arrowheads more than the unclipped plot: filled triangles.
    assert len(polygons(cut, 3)) == 2
    assert polygons(plain, 3) == []
    # The clipped interval stays inside the plot area.
    area = plot_area(cut)
    for m in placements(cut, MARK_KIND) + placements(cut, MARK_LINE_KIND):
        assert area.x0 - 1e-6 <= m.bbox.x0 and m.bbox.x1 <= area.x1 + 1e-6


def test_squares_follow_weights_and_summaries_are_diamonds() -> None:
    node = inklet.forest(ROWS, log=True)
    found = squares(node)
    # Largest weight 2.4 mm; a quarter of the weight, half the side.
    assert len(found) == 3
    # Unweighted rows get the fixed 1.3 mm.
    assert [round(m.bbox.width, 2) for m in found] == [2.4, 1.3, 1.2]
    assert len(polygons(node, 4)) == 2


def test_columns_line_up_with_rows_and_sit_beside_the_plot() -> None:
    node = inklet.forest(ROWS, log=True, measure="OR", right=["ci", "n"])
    area = plot_area(node)
    found = texts(node)
    assert "0.72 (0.55–0.94)" in found and "OR (95% CI)" in found
    assert "812" in found and "n" in found
    ahmed, ci, n = found["Ahmed 2019"], found["0.72 (0.55–0.94)"], found["812"]
    assert ahmed.bbox.center.y == pytest.approx(ci.bbox.center.y, abs=1e-6)
    assert ahmed.bbox.x1 < area.x0 and ci.bbox.x0 > area.x1
    # Right-aligned numbers share their right edge with the header.
    assert n.bbox.x1 == pytest.approx(found["n"].bbox.x1, abs=1e-6)
    # Indented study label, flush header label.
    assert ahmed.bbox.x0 > found["Adults"].bbox.x0 + 1
    # A function column and custom header.
    node = inklet.forest(ROWS, right=[("p", lambda r: "" if r.kind == "header"
                                       else f"{r.estimate * 2:.1f}")], log=True)
    assert "1.4" in texts(node)


def test_forest_errors() -> None:
    with pytest.raises(DiagramError):
        forest_layout([])
    with pytest.raises(DiagramError):
        forest_layout(["only a header"])
    with pytest.raises(DiagramError):
        forest_layout([("a", 2.0, 2.5, 3.0)])
    with pytest.raises(DiagramError):
        forest_layout([("a", 1.0, 0.0, 3.0)], log=True)
    with pytest.raises(DiagramError):
        forest_layout([("a", 1.0, 0.5, 3.0)], limits=(2, 1))
    with pytest.raises(DiagramError):
        forest_layout([{"label": "a", "estimate": 1, "low": 0, "high": 2,
                        "kind": "other"}])
    with pytest.raises(DiagramError):
        inklet.forest(ROWS, right=[("a", "b", "middle")], log=True)


def test_forest_lints_clean_and_exports() -> None:
    node = inklet.forest(ROWS, log=True, limits=(0.2, 5), measure="OR",
                         right=["ci", "n"], label="Odds ratio", summary_line=True)
    fig = inklet.figure(width=node.bbox.width + 10, theme="nature")
    fig.add(inklet.letters([node])[0])
    assert fig.lint() == []
    assert lint(node) == []
    assert inklet.to_pdf(node)[:4] == b"%PDF"
    doc = inklet.document(width=120)
    doc.add("forest", node)
    assert "<path" in doc.compile().to_svg()
