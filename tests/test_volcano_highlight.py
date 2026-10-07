"""Volcano highlights and labels, through the quick and Panel APIs.

`label_points` defers its placement to build time and leaves an empty
placeholder in the over layer until then. A quick chart fits its axes by
probing each mark into a placeholder panel, and that probe read the box of
the placeholder: any volcano with labels whose highlighted points fell inside
the probe's area crashed with "point-labels-pending<N> is empty and has no
bounding box". Which names fell inside depended on the data and the number
of names, so these tests cover several counts, with and without a scatter on
top (the scatter fixes the domain before the volcano is probed).
"""

from __future__ import annotations

import math
import random
import xml.etree.ElementTree as ET

import pytest

import inklet
from inklet import use_theme
from inklet.plot import panel


@pytest.fixture(autouse=True)
def _theme():
    use_theme("nature")


def features(n: int, seed: int = 0):
    rng = random.Random(seed)
    genes = [f"G{k}" for k in range(n)]
    fold = [rng.gauss(0, 1.5) for _ in genes]
    p = [min(1.0, 10 ** -abs(rng.gauss(0, 3))) for _ in genes]
    return genes, fold, p


def records(genes, fold, p):
    return [{"gene": g, "lfc": f, "p": pv} for g, f, pv in zip(genes, fold, p)]


def text_of(svg: str) -> set[str]:
    """Every whole `<text>` string in an SVG document. Exact strings, so
    the label G1 is not found inside G12."""
    root = ET.fromstring(svg)
    out = set()
    for element in root.iter():
        if element.tag.endswith("}text") or element.tag == "text":
            out.add("".join(element.itertext()).strip())
    return out


def quick_chart(genes, fold, p, highlight, extra: bool):
    rows = records(genes, fold, p)
    chart = inklet.chart()
    chart.volcano(rows, x="lfc", y="p", label="gene", highlight=highlight)
    if extra:
        chart.scatter(rows, x="lfc", y="p")
    return chart


def panel_figure(genes, fold, p, highlight, extra: bool):
    v = panel(60, 50, x=(-6, 6), y=(0, 16))
    v.volcano(fold, p, labels=genes, highlight=highlight)
    if extra:
        v.scatter([(f, -math.log10(pv)) for f, pv in zip(fold[:40], p[:40])],
                  color="#777777")
    fig = inklet.figure(width=90)
    fig.add(v.build())
    return fig


def severe(diagnostics) -> list:
    return [d for d in diagnostics if d.severity == "error"]


@pytest.mark.parametrize("count", [1, 4, 10, 30])
@pytest.mark.parametrize("extra", [False, True], ids=["alone", "with-scatter"])
def test_quick_volcano_names_every_highlight(count: int, extra: bool) -> None:
    genes, fold, p = features(300)
    highlight = genes[:count]
    chart = quick_chart(genes, fold, p, highlight, extra)
    svg = chart.to_svg(text="names")
    labels = text_of(svg)
    missing = [name for name in highlight if name not in labels]
    assert missing == []
    assert severe(chart.compile().lint()) == []


@pytest.mark.parametrize("count", [1, 4, 10, 30])
@pytest.mark.parametrize("extra", [False, True], ids=["alone", "with-scatter"])
def test_panel_volcano_names_every_highlight(count: int, extra: bool) -> None:
    genes, fold, p = features(300)
    highlight = genes[:count]
    fig = panel_figure(genes, fold, p, highlight, extra)
    labels = text_of(fig.to_svg(text="names"))
    missing = [name for name in highlight if name not in labels]
    assert missing == []
    assert severe(fig.lint()) == []


def test_quick_function_with_5000_rows_names_highlights() -> None:
    genes, fold, p = features(5000)
    highlight = genes[:10]
    chart = inklet.volcano(records(genes, fold, p), x="lfc", y="p", label="gene",
                           highlight=highlight)
    labels = text_of(chart.to_svg(text="names"))
    assert [name for name in highlight if name not in labels] == []
    assert severe(chart.compile().lint()) == []


def test_quick_chart_with_5000_rows_and_scatter_names_highlights() -> None:
    genes, fold, p = features(5000)
    highlight = genes[:10]
    chart = quick_chart(genes, fold, p, highlight, extra=True)
    labels = text_of(chart.to_svg(text="names"))
    assert [name for name in highlight if name not in labels] == []


def test_highlights_do_not_change_the_fitted_axes() -> None:
    # Labels are kept inside the plot area, so naming points must leave the
    # tick labels, and so the domain they were fitted to, where they were.
    genes, fold, p = features(300)
    plain = text_of(quick_chart(genes, fold, p, [], extra=True).to_svg(text="names"))
    named = text_of(quick_chart(genes, fold, p, genes[:10], extra=True).to_svg(text="names"))
    ticks = {t for t in plain if t.replace(".", "", 1).replace("-", "", 1).isdigit()}
    assert ticks
    assert ticks <= named


def test_one_label_text_per_highlight_and_no_extra_labels() -> None:
    genes, fold, p = features(300)
    highlight = genes[:10]
    labels = text_of(quick_chart(genes, fold, p, highlight, extra=True)
                     .to_svg(text="names"))
    gene_labels = {t for t in labels if t.startswith("G") and t[1:].isdigit()}
    assert gene_labels == set(highlight)
