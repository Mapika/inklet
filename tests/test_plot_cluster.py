"""Hierarchical clustering, cluster boxes, correlograms, clustermaps,
genomics plots, ternary plots and the inset connector style."""

from __future__ import annotations

import math
import random
import re

import pytest

import inklet
from inklet import use_theme
from inklet.core import DiagramError, resolve
from inklet.diagnostics import lint
from inklet.plot import (chromosome_key, correlation, cut, dendrogram_layout, linkage,
                         manhattan_layout)


@pytest.fixture(autouse=True)
def _theme():
    use_theme("nature")


def _svg(node) -> str:
    return re.sub(r'(id|href|clip-path)="[^"]*"', "", inklet.to_svg(node))


def _note(node, key):
    return next(x.diagram.notes[key] for x in resolve(node).values() if key in x.diagram.notes)


def _table(seed=3, n=12, width=6):
    rng = random.Random(seed)
    return [[rng.gauss(3 * (k % 3 == j % 3), 1) for j in range(width)] for k in range(n)]


@pytest.mark.parametrize("method", ["single", "complete", "average", "weighted", "ward"])
def test_linkage_matches_scipy(method) -> None:
    hierarchy = pytest.importorskip("scipy.cluster.hierarchy")
    table = _table()
    ours = linkage(table, method=method)
    theirs = hierarchy.linkage(table, method=method, metric="euclidean").tolist()
    for a, b in zip(ours, theirs):
        assert math.isclose(a[2], b[2], rel_tol=1e-9, abs_tol=1e-12)
        assert a[3] == b[3]
        assert {a[0], a[1]} == {b[0], b[1]}


def test_linkage_metrics_and_cut() -> None:
    table = _table()
    link = linkage(table, metric="correlation")
    assert len(link) == len(table) - 1
    heights = [r[2] for r in link]
    assert heights == sorted(heights)
    labels = cut(link, 3)
    assert sorted(set(labels)) == [1, 2, 3]
    order = dendrogram_layout(link).order
    ordered = [labels[i] for i in order]
    # Numbered in leaf order, so the clusters are consecutive runs 1, 2, 3.
    assert ordered == sorted(ordered)
    assert cut(link, 1) == [1] * len(table)
    assert len(set(cut(link, height=-1))) == len(table)
    with pytest.raises(DiagramError):
        cut(link)
    with pytest.raises(DiagramError):
        linkage(table, method="median")
    with pytest.raises(DiagramError):
        linkage([[0, 1], [2, 0]], metric="precomputed")


def test_correlation() -> None:
    r = correlation([[1, 2, 3, 4], [2, 4, 6, 8.5], [4, 3, 2, 1]])
    assert math.isclose(r[0][2], -1.0)
    assert r[0][1] > 0.99 and r[1][1] == 1.0
    assert r[0][1] == r[1][0]
    assert math.isnan(correlation([[1, 1, 1], [1, 2, 3]])[0][1])


def test_cluster_boxes_span_whole_cells() -> None:
    groups = [1, 1, 1, 2, 2, 3, 3, 3, 3, 3]
    p = inklet.panel(40, 40).matrix([[i == j for j in range(10)] for i in range(10)])
    p.clusters(groups, highlight=2, labels=True)
    node = p.build()
    note = _note(node, "clusters")
    assert note["blocks"] == [(0, 3, 1), (3, 5, 2), (5, 10, 3)]
    assert note["highlighted"] == ["2"]
    assert "#c9352b" in inklet.to_svg(node)
    assert lint(node) == []
    with pytest.raises(DiagramError):
        inklet.panel(40, 40).clusters([1, 2, 1])
    with pytest.raises(DiagramError):
        inklet.panel(40, 40).clusters([1, 2], highlight=5)


def test_correlogram_triangle_and_areas() -> None:
    r = [[1, 0.8, -0.2], [0.8, 1, 0.1], [-0.2, 0.1, 1]]
    p = inklet.panel(30, 30).correlogram(r, ["a", "b", "c"]).colorbar(title="r")
    node = p.build()
    note = _note(node, "correlogram")
    assert note["cells"] == 3 and note["rows"] == ["b", "c"] and note["columns"] == ["a", "b"]
    assert lint(node) == []
    full = inklet.panel(30, 30).correlogram(r, triangle="full", shape="tile", values=True)
    assert _note(full.build(), "correlogram")["cells"] == 9
    with pytest.raises(DiagramError):
        inklet.panel(30, 30).correlogram([[1, 2], [2, 1]])


def test_clustermap_orders_and_lints() -> None:
    table = _table(n=9, width=6)
    names = [f"g{k}" for k in range(9)]

    def build():
        return inklet.clustermap(table, rows=names, standardize="rows", k=3,
                                 col_colors={"batch": ["a", "a", "b", "b", "c", "c"]},
                                 width=30)
    node = build()
    note = node.notes["clustermap"]
    assert sorted(note["row_order"]) == list(range(9))
    ordered = [note["clusters"][names[i]] for i in note["row_order"]]
    assert ordered == sorted(ordered)
    assert _svg(node) == _svg(build())
    r = correlation(table)
    square = inklet.clustermap(r, rows=names, columns=names, k=3, width=30, center=0)
    assert any("clusters" in x.diagram.notes for x in resolve(square).values())
    with pytest.raises(DiagramError):
        inklet.clustermap(table, rows=names[:3])


def test_chromosome_order_and_manhattan_layout() -> None:
    assert sorted(["chr10", "chrX", "chr2", "chr1", "MT", "chrY"], key=chromosome_key) == \
        ["chr1", "chr2", "chr10", "chrX", "chrY", "MT"]
    chrom = ["2", "1", "1", "2", "X"]
    pos = [100, 50, 200, 300, 10]
    p = [1e-9, 0.5, 1e-10, 1e-8, 0.01]
    layout = manhattan_layout(chrom, pos, p, gap=0.0, window=150)
    assert layout.order == ("1", "2", "X")
    assert layout.spans["2"] == (200.0, 500.0)
    assert layout.x[0] == 300.0
    assert math.isclose(layout.y[2], 10)
    # 1e-9 and 1e-8 on chr2 are 200 bp apart, past the window: both lead.
    assert layout.leads == (2, 0, 3)
    with pytest.raises(DiagramError):
        manhattan_layout(chrom, pos, [2, 0, 0, 0, 0])


def test_manhattan_and_ma_panels() -> None:
    rng = random.Random(1)
    chrom = [str(1 + k % 4) for k in range(400)]
    pos = [rng.uniform(0, 1e7) for _ in range(400)]
    pv = [10 ** -rng.expovariate(1) for _ in range(400)]
    pv[5] = 1e-12
    names = [f"rs{k}" for k in range(400)]
    m = inklet.manhattan(chrom, pos, pv, labels=names, width=80, height=30)
    node = m.build()
    note = _note(node, "manhattan")
    assert note["labelled"] == [5]
    assert "rs5" in inklet.to_svg(node)
    assert lint(node) == []
    mean = [2 ** rng.uniform(0, 12) for _ in range(200)]
    fold = [rng.gauss(0, 1.2) for _ in range(200)]
    padj = [0.001 if abs(f) > 1.5 else 0.5 for f in fold]
    ma = inklet.panel(50, 40, x=(0, 13), y=(-5, 5)).ma(mean, fold, padj)
    ma_note = _note(ma.build(), "ma")
    assert all(c == ("up" if f >= 1.5 else "down" if f <= -1.5 else "ns")
               for c, f in zip(ma_note["classes"], fold) if abs(abs(f) - 1.5) > 1e-9)


def test_ternary_points_land_on_the_triangle() -> None:
    p = inklet.panel(40, 36)
    p.ternary([(1, 0, 0), (0, 1, 0), (0, 0, 1), (1, 1, 1)], labels=("A", "B", "C"))
    frame = p._ternary
    assert math.isclose(frame.point(1, 0, 0).x, frame.a.x)
    centroid = frame.point(2, 2, 2)
    assert math.isclose(centroid.x, (frame.a.x + frame.b.x + frame.c.x) / 3)
    assert math.isclose(frame.c.x - frame.b.x, frame.side)
    assert math.isclose(frame.b.y - frame.a.y, frame.side * math.sqrt(3) / 2)
    assert lint(p.build()) == []
    with pytest.raises(DiagramError):
        p.ternary([(1, 1, 1)], labels=("x", "y", "z"))
    with pytest.raises(DiagramError):
        inklet.panel(40, 36).ternary([(0, 0, 0)])


def test_inset_connector_style_applies_to_connectors_only() -> None:
    p = inklet.panel(50, 40, x=(0, 10), y=(0, 10))
    p.scatter([(1, 1), (9, 9)])
    sub = inklet.panel(15, 12, x=(0, 2), y=(0, 2)).scatter([(1, 1)])
    p.inset(sub, zoom=(0, 2, 0, 2), stroke="#c9352b", connector={"stroke": "#555555",
                                                                   "stroke_dash": (1, 0.6)})
    svg = inklet.to_svg(p.build())
    assert "#c9352b" in svg and "#555555" in svg
    assert svg.count("stroke-dasharray") == 2
