"""Regressions from the published-figure recreations, round 2: keys.

ISSUES-physics #2 (hollow scatter swatches), ISSUES-physics #4 and
ISSUES-stats-genomics #3 (key order), ISSUES-stats-genomics #2 (volcano
highlight= and q=), ISSUES-medicine-econ #3 (vertical size_key alignment).
"""

from __future__ import annotations

import math
import warnings

import pytest

import inklet
from inklet import use_theme
from inklet.core import DiagramError, resolve
from inklet.draw.coords import active_theme, as_drawn
from inklet.plot import area_scale, panel, polar, size_key, volcano_points
from inklet.plot.key import LEGEND_LABEL_KIND
from inklet.plot.series import swatch_for


@pytest.fixture(autouse=True)
def _theme():
    use_theme("nature")


def _texts(node, kind: str = LEGEND_LABEL_KIND) -> list[str]:
    found = []
    for placed in sorted(resolve(as_drawn(node)).values(),
                         key=lambda q: (q.bbox.y0, q.bbox.x0)):
        if placed.diagram.kind == kind and hasattr(placed.diagram.prim, "text"):
            found.append(placed.diagram.prim.text)
    return found


def _swatch_paint(entry) -> list[tuple]:
    """(fill, stroke, stroke_width) of every painted leaf in a swatch."""
    return [(q.style.fill, q.style.stroke, q.style.stroke_width)
            for q in resolve(swatch_for(entry, 2.0)).values()
            if q.diagram.prim is not None]


# -- hollow scatter and its swatch -------------------------------------------


def test_a_hollow_scatter_draws_rings_in_the_series_colour() -> None:
    p = panel(40, 30, x=(0, 1), y=(0, 1))
    p.scatter([(0.3, 0.4), (0.7, 0.6)], hollow=True, color="#8a5a00", name="means")
    paper = active_theme().paper
    marks = [q for q in resolve(as_drawn(p.build())).values()
             if q.diagram.kind == "mark" and q.diagram.prim is not None]
    assert len(marks) == 2
    for mark in marks:
        assert mark.style.fill == paper
        assert mark.style.stroke == "#8a5a00"
        assert mark.style.stroke_width == pytest.approx(active_theme().stroke)
    [(fill, stroke, _)] = _swatch_paint(p.keys[0])
    assert (fill, stroke) == (paper, "#8a5a00")


def test_a_hollow_scatter_without_a_colour_takes_its_palette_slot() -> None:
    p = panel(40, 30, x=(0, 1), y=(0, 1))
    p.line([(0, 0), (1, 1)], name="first")
    p.scatter([(0.5, 0.5)], hollow=True, name="second")
    entry = p.keys[1]
    assert entry.color == active_theme().color(1)
    assert entry.marker_stroke == active_theme().color(1)
    assert entry.marker_fill == active_theme().paper


def test_a_white_marker_with_a_stroke_gets_a_visible_swatch() -> None:
    p = panel(40, 30, x=(0, 1), y=(0, 1))
    p.scatter([(0.3, 0.4)], size=2, color="white", stroke="#8a5a00",
              stroke_width=0.3, name="group means")
    [(fill, stroke, width)] = _swatch_paint(p.keys[0])
    assert fill == "white"
    assert stroke == "#8a5a00"
    assert width == pytest.approx(0.3)


def test_a_plain_scatter_swatch_is_unchanged() -> None:
    p = panel(40, 30, x=(0, 1), y=(0, 1))
    p.scatter([(0.3, 0.4)], color="#123456", name="a")
    [(fill, stroke, _)] = _swatch_paint(p.keys[0])
    assert (fill, stroke) == ("#123456", "#123456")


def test_hollow_refuses_per_point_colours() -> None:
    p = panel(40, 30, x=(0, 1), y=(0, 1))
    with pytest.raises(DiagramError, match="hollow"):
        p.scatter([(0.1, 0.1), (0.2, 0.2)], hollow=True, color=["red", "blue"])


# -- legend(names=) -----------------------------------------------------------


def test_legend_names_orders_the_rows() -> None:
    p = panel(60, 40, x=(0, 1), y=(0, 1))
    p.line([(0, 0), (1, 1)], name="H1 (shifted)")
    p.line([(0, 1), (1, 0)], name="L1")
    p.legend(side="right", names=["L1", "H1 (shifted)"])
    assert _texts(p.build()) == ["L1", "H1 (shifted)"]


def test_legend_names_leaves_out_unlisted_series_and_rejects_unknown() -> None:
    p = panel(60, 40, x=(0, 1), y=(0, 1))
    p.line([(0, 0), (1, 1)], name="a").line([(0, 1), (1, 0)], name="b")
    p.legend(side="right", names=["b"])
    assert _texts(p.build()) == ["b"]
    q = panel(60, 40, x=(0, 1), y=(0, 1)).line([(0, 0), (1, 1)], name="a")
    with pytest.raises(DiagramError, match="never|drew"):
        q.legend(names=["zzz"])
    with pytest.raises(DiagramError, match="not both"):
        q.legend(names=["a"], entries=[("a", "#000000")])


def test_legend_names_in_a_recipe_and_on_a_polar_panel() -> None:
    spec = inklet.plot_spec(60, 40, x=(0, 1), y=(0, 1))
    spec.line([(0, 0), (1, 1)], name="a").line([(0, 1), (1, 0)], name="b")
    spec.legend(side="right", names=["b", "a"])
    doc = inklet.document(width=90)
    doc.add("p", spec)
    figure = doc.compile()
    svg = figure.to_svg()
    assert svg.index(">b<") < svg.index(">a<")
    pp = polar(40)
    pp.line([(0, 0.5), (90, 0.5)], name="a").line([(0, 0.2), (90, 0.2)], name="b")
    pp.legend(names=["b", "a"])
    assert _texts(pp.build()) == ["b", "a"]


# -- volcano ------------------------------------------------------------------


def test_volcano_key_lists_significant_classes_first() -> None:
    p = panel(60, 40, x=(-5, 5), y=(0, 8))
    p.volcano([-3, 0.1, 3], [1e-6, 0.5, 1e-6],
              name={"down": "down", "ns": "n.s.", "up": "up"})
    assert [k.name for k in p.keys] == ["up", "down", "n.s."]
    p.legend(side="right")
    assert _texts(p.build()) == ["up", "down", "n.s."]


def test_ma_key_lists_significant_classes_first() -> None:
    p = panel(60, 40, x=(0, 10), y=(-5, 5))
    p.ma([10, 100, 1000], [-3, 0.1, 3], [1e-6, 0.5, 1e-6],
         name={"down": "down", "ns": "n.s.", "up": "up"})
    assert [k.name for k in p.keys] == ["up", "down", "n.s."]


def test_volcano_q_classes_while_p_sets_the_height() -> None:
    fold = [2.0, 2.0, -2.0, 2.0]
    p = [1e-4, 1e-4, 1e-3, 0.2]
    q = [0.01, 0.2, 0.04, float("nan")]
    result = volcano_points(fold, p, q=q)
    assert result["classes"] == ["up", "ns", "down", "ns"]
    assert [pt[1] for pt in result["points"]] == pytest.approx(
        [-math.log10(v) for v in p])
    assert result["skipped"] == []
    with pytest.raises(DiagramError, match="q-value"):
        volcano_points(fold, p, q=[0.1, 0.1])


def test_volcano_highlight_labels_the_named_genes() -> None:
    fold = [-4.0, -3.0, 0.1, 3.0, 0.5, 2.5]
    pv = [1e-9, 1e-8, 0.5, 1e-7, 0.3, 1e-6]
    genes = ["A", "B", "C", "D", "E", "F"]
    p = panel(60, 40, x=(-5, 5), y=(0, 10))
    p.volcano(fold, pv, labels=genes, highlight=["E", "D"])
    built = p.build()
    notes = [n.notes["volcano"] for n in built.walk() if "volcano" in n.notes]
    assert notes and notes[0]["labelled"] == [4, 3]       # top defaults to 0
    words = set(_all_text(built))
    assert {"D", "E"} <= words and not {"A", "B", "F"} & words
    q = panel(60, 40, x=(-5, 5), y=(0, 10))
    q.volcano(fold, pv, labels=genes, highlight=["E"], top=2)
    note = [n.notes["volcano"] for n in q.build().walk() if "volcano" in n.notes][0]
    assert note["labelled"] == [4, 0, 1]
    with pytest.raises(DiagramError, match="not among labels"):
        panel(60, 40, x=(-5, 5), y=(0, 10)).volcano(
            fold, pv, labels=genes, highlight=["ZZZ"])
    with pytest.raises(DiagramError, match="labels"):
        panel(60, 40, x=(-5, 5), y=(0, 10)).volcano(fold, pv, highlight=["A"])


def test_a_highlighted_gene_outside_the_plot_is_reported_not_labelled() -> None:
    p = panel(60, 40, x=(-5, 5), y=(0, 10))
    p.volcano([-4.0, 9.0], [1e-3, 1e-3], labels=["in", "out"],
              highlight=["in", "out"])
    note = [n.notes["volcano"] for n in p.build().walk() if "volcano" in n.notes][0]
    assert note["labelled"] == [0]
    assert note["unlabelled"] == [1]


def _all_text(node) -> list[str]:
    return [q.diagram.prim.text for q in resolve(as_drawn(node)).values()
            if hasattr(q.diagram.prim, "text")]


# -- size key -----------------------------------------------------------------


def _circles_and_labels(node):
    placed = resolve(as_drawn(node)).values()
    circles = sorted((q.bbox for q in placed if type(q.diagram.prim).__name__ == "EllipsePrim"),
                     key=lambda b: b.width)
    labels = [q.bbox for q in placed if hasattr(q.diagram.prim, "text")]
    return circles, labels


def test_a_vertical_size_key_centres_circles_and_aligns_labels() -> None:
    key = size_key(area_scale(1e9, 15), values=[1e7, 1e8, 1e9])
    circles, labels = _circles_and_labels(key)
    assert len(circles) == 3 and len(labels) == 3
    centres = [b.center.x for b in circles]
    assert max(centres) - min(centres) == pytest.approx(0.0, abs=1e-6)
    lefts = [b.x0 for b in labels]
    assert max(lefts) - min(lefts) == pytest.approx(0.0, abs=1e-6)
    # Rows still stack downward without overlapping.
    order = sorted(circles, key=lambda b: b.y0)
    assert all(a.y1 <= b.y0 + 1e-9 for a, b in zip(order, order[1:]))


def test_a_vertical_size_key_beside_a_panel_lints_clean() -> None:
    spec = inklet.plot_spec(x=(0, 1), y=(0, 1))
    spec.scatter([(0.5, 0.5)], size=2)
    spec.size_key(area_scale(1e9, 15), values=[1e7, 1e8, 1e9], side="right")
    doc = inklet.document(width=90)
    doc.add("a", spec)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        figure = doc.compile()
    circles, labels = _circles_and_labels(figure.root)
    lefts = sorted(b.x0 for b in labels)
    assert lefts[-1] - lefts[0] == pytest.approx(0.0, abs=1e-6)
