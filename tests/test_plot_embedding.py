"""Panel.embedding and plot.cluster_centres."""

from __future__ import annotations

import math
import random
import re

import pytest

import inklet
from inklet import use_theme
from inklet.core import DiagramError, MarkerBatchPrim, resolve
from inklet.diagnostics import lint
from inklet.draw.coords import as_drawn
from inklet.plot import cluster_centres, panel
from inklet.plot.embedding import cluster_colors
from inklet.plot.point_labels import POINT_LABEL_KIND


@pytest.fixture(autouse=True)
def _theme():
    use_theme("nature")


CENTRES = {"T cells": (-4, 3), "B cells": (-4, -3), "NK": (0, 4),
           "Monocytes": (3, 1), "Platelets": (3, -4)}


def cloud(per: int = 400, seed: int = 2):
    rng = random.Random(seed)
    points, names = [], []
    for name, (cx, cy) in CENTRES.items():
        for _ in range(per):
            points.append((cx + rng.gauss(0, 0.7), cy + rng.gauss(0, 0.5)))
            names.append(name)
    return points, names


def placed(p):
    return list(resolve(as_drawn(p.build())).values())


def test_centres_lie_on_the_data_near_the_middle() -> None:
    points, names = cloud()
    for method in ("median", "medoid"):
        found = cluster_centres(points, names, method=method)
        assert list(found) == list(CENTRES)
        for name, (x, y) in found.items():
            assert (x, y) in points
            cx, cy = CENTRES[name]
            assert math.hypot(x - cx, y - cy) < 0.5
    mean = cluster_centres(points, names, method="mean")
    assert mean["NK"][0] == pytest.approx(0, abs=0.2)
    # A crescent: its mean falls off the data, the median centre does not.
    arc = [(math.cos(t / 50 * math.pi), math.sin(t / 50 * math.pi)) for t in range(51)]
    (x, y), = cluster_centres(arc, ["c"] * len(arc)).values()
    assert math.hypot(x, y) == pytest.approx(1.0)
    assert list(cluster_centres([(0, 0), (1, 1)], [2, 1])) == [1, 2]
    with pytest.raises(DiagramError):
        cluster_centres(points, names[:-1])
    with pytest.raises(DiagramError):
        cluster_centres(points, names, method="mode")


def test_embedding_is_one_marker_batch_with_named_clusters() -> None:
    points, names = cloud()
    p = panel(50, 50, x=(-7, 7), y=(-7, 7))
    p.embedding(points, names, size=0.4)
    nodes = placed(p)
    batches = [n for n in nodes if isinstance(n.diagram.prim, MarkerBatchPrim)]
    assert len(batches) == 1
    assert len(list(batches[0].diagram.prim.records())) == len(points)
    labels = [n for n in nodes if n.diagram.kind == POINT_LABEL_KIND]
    assert len(labels) == len(CENTRES)
    boxes = [n.bbox for n in labels]
    for i, a in enumerate(boxes):
        assert p.area.x0 - 1e-6 <= a.x0 and a.x1 <= p.area.x1 + 1e-6
        for b in boxes[i + 1:]:
            assert min(a.x1, b.x1) <= max(a.x0, b.x0) or min(a.y1, b.y1) <= max(a.y0, b.y0)
    note = p._over[-1].notes["embedding"]
    assert note["clusters"] == list(CENTRES)
    assert note["colors"] == list(cluster_colors(len(CENTRES)))
    assert [k.name for k in p.keys] == list(CENTRES)


def test_crowded_names_move_apart() -> None:
    points = [(0, 0), (0.05, 0), (0.1, 0.02)]
    p = panel(40, 30, x=(-1, 1), y=(-1, 1))
    p.embedding(points, ["alpha cells", "beta cells", "gamma cells"], shuffle=False)
    labels = [n.bbox for n in placed(p) if n.diagram.kind == POINT_LABEL_KIND]
    for i, a in enumerate(labels):
        for b in labels[i + 1:]:
            assert min(a.x1, b.x1) <= max(a.x0, b.x0) or min(a.y1, b.y1) <= max(a.y0, b.y0)


def test_axis_arrows_and_colours() -> None:
    points, names = cloud(per=40)
    p = panel(40, 40, x=(-7, 7), y=(-7, 7))
    p.embedding(points, names, arrows="UMAP", labels=False,
                colors={n: "#336699" for n in CENTRES})
    words = [n for n in placed(p) if n.diagram.kind == "axis-label"]
    assert sorted(w.diagram.prim.text for w in words) == ["UMAP1", "UMAP2"]
    for w in words:
        # Outside the data area, beside the corner.
        assert w.bbox.y0 >= p.area.y1 - 1e-6 or w.bbox.x1 <= p.area.x0 + 1e-6
    assert len(cluster_colors(30)) == len(set(cluster_colors(30))) == 30
    with pytest.raises(DiagramError):
        panel(40, 40).embedding(points, names, colors={"NK": "red"})
    with pytest.raises(DiagramError):
        panel(40, 40).embedding(points, names, arrows=("a",))


def test_embedding_lints_clean_and_is_repeatable() -> None:
    points, names = cloud(per=300)

    def build(seed=0):
        p = panel(50, 50, x=(-7, 7), y=(-7, 7))
        p.embedding(points, names, arrows=("tSNE 1", "tSNE 2"), size=0.4, seed=seed)
        return p.build()

    node = build()
    fig = inklet.figure(width=70, theme="nature")
    fig.add(inklet.letters([node])[0])
    assert [d for d in fig.lint() if d.severity != "info"] == []
    def svg(seed=0):
        return re.sub(r'id="[^"]*"', "", inklet.to_svg(build(seed)))

    assert svg() == svg() and svg(0) != svg(1)
    assert [d for d in lint(node) if d.severity != "info"] == []
    spec = inklet.plot_spec(x=(-7, 7), y=(-7, 7), width=50, height=50)
    spec.embedding(points, names, arrows="UMAP")
    doc = inklet.document(width=80)
    doc.add("umap", spec)
    assert "UMAP1" in doc.compile().to_svg()
