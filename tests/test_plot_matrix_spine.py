"""A heatmap axis with no ticks draws no spine; other axes are unchanged."""

from __future__ import annotations

import pytest

import inklet
from inklet import use_theme
from inklet.core import resolve
from inklet.diagnostics import lint
from inklet.draw.coords import as_drawn
from inklet.plot import panel
from inklet.plot.axis import SPINE_KIND


@pytest.fixture(autouse=True)
def _theme():
    use_theme("nature")


CELLS = [[0.1, 0.5, 0.9], [0.4, 0.2, 0.7]]


def spines(node) -> list:
    return [x for x in resolve(as_drawn(node)).values()
            if x.diagram.kind == SPINE_KIND]


def heat(**options):
    p = panel(30, 20, x=["a", "b", "c"], y=["u", "v"])
    p.matrix(CELLS, x=["a", "b", "c"], y=["u", "v"])
    return p


def test_empty_ticks_on_a_matrix_draw_no_spine() -> None:
    p = heat()
    p.axes(x="target", y="source", x_options={"ticks": []},
           y_options={"ticks": []})
    node = p.build()
    assert spines(node) == []
    # The axis names are still drawn.
    texts = {getattr(x.diagram.prim, "text", None)
             for x in resolve(as_drawn(node)).values()}
    assert {"target", "source"} <= texts
    assert lint(node) == []


def test_hidden_ticks_on_a_matrix_draw_no_spine() -> None:
    p = heat()
    p.axis("bottom", labels=False, tick_size=0).axis("left", ticks=[])
    assert spines(p.build()) == []


def test_matrix_axes_with_ticks_keep_their_spine() -> None:
    p = heat()
    p.axes()
    assert len(spines(p.build())) == 2
    # Only the empty side loses its spine.
    q = heat()
    q.axis("bottom", ticks=[]).axis("left")
    assert len(spines(q.build())) == 1


def test_an_explicit_spine_wins_on_a_matrix() -> None:
    p = heat()
    p.axis("bottom", ticks=[], spine=True)
    assert len(spines(p.build())) == 1


def test_empty_ticks_off_a_matrix_keep_the_spine() -> None:
    p = panel(30, 20, x=(0, 1), y=(0, 1))
    p.line([(0, 0), (1, 1)])
    p.axes(x_options={"ticks": []}, y_options={"ticks": []})
    assert len(spines(p.build())) == 2


def test_plot_spec_heatmap_without_ticks_has_no_spine() -> None:
    spec = inklet.plot_spec(height=20, x=(-.5, 2.5), y=(1.5, -.5))
    spec.matrix(CELLS, x=range(3), y=range(2))
    spec.axes(x="target", y="source", x_options={"ticks": []},
              y_options={"ticks": []})
    doc = inklet.document(width=60)
    doc.add("heat", spec)
    root = doc.compile().root
    assert [n for n in root.walk() if n.kind == SPINE_KIND] == []
