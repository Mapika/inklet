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
from inklet.plot import cluster_centers, panel
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
        found = cluster_centers(points, names, method=method)
        assert list(found) == list(CENTRES)
        for name, (x, y) in found.items():
            assert (x, y) in points
            cx, cy = CENTRES[name]
            assert math.hypot(x - cx, y - cy) < 0.5
    mean = cluster_centers(points, names, method="mean")
    assert mean["NK"][0] == pytest.approx(0, abs=0.2)
    # A crescent: its mean falls off the data, the median centre does not.
    arc = [(math.cos(t / 50 * math.pi), math.sin(t / 50 * math.pi)) for t in range(51)]
    (x, y), = cluster_centers(arc, ["c"] * len(arc)).values()
    assert math.hypot(x, y) == pytest.approx(1.0)
    assert list(cluster_centers([(0, 0), (1, 1)], [2, 1])) == [1, 2]
    with pytest.raises(DiagramError):
        cluster_centers(points, names[:-1])
    with pytest.raises(DiagramError):
        cluster_centers(points, names, method="mode")


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
                color={n: "#336699" for n in CENTRES})
    words = [n for n in placed(p) if n.diagram.kind == "axis-label"]
    assert sorted(w.diagram.prim.text for w in words) == ["UMAP1", "UMAP2"]
    for w in words:
        # Outside the data area, beside the corner.
        assert w.bbox.y0 >= p.area.y1 - 1e-6 or w.bbox.x1 <= p.area.x0 + 1e-6
    assert len(cluster_colors(30)) == len(set(cluster_colors(30))) == 30
    with pytest.raises(DiagramError):
        panel(40, 40).embedding(points, names, color={"NK": "red"})
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


# -- outlines -----------------------------------------------------------------


def outline_paths(p, kind):
    from inklet.core import PathPrim

    return [n for n in placed(p) if isinstance(n.diagram.prim, PathPrim)
            and n.diagram.kind == kind]


def test_core_outline_holds_the_core_and_ignores_strays() -> None:
    from inklet.core import Rect, Vec2
    from inklet.plot.outlines import core_outline

    rng = random.Random(4)
    blob = [Vec2(rng.gauss(0, 2), rng.gauss(0, 1)) for _ in range(4000)]
    rings = core_outline(blob, core=0.8)
    assert len(rings) == 1
    box = Rect.hull(rings[0])
    # About the 80% ellipse of the blob, 1.8 spreads either way.
    assert 2.8 < box.width / 2 < 4.4 and 1.4 < box.height / 2 < 2.2
    # Strays, scattered far out or in one tight handful, neither grow the
    # outline nor add an island.
    strays = [Vec2(rng.uniform(-40, 40), rng.uniform(-40, 40)) for _ in range(60)]
    strays += [Vec2(30 + rng.gauss(0, .1), 30 + rng.gauss(0, .1)) for _ in range(40)]
    again = core_outline(blob + strays, core=0.8)
    assert len(again) == 1
    other = Rect.hull(again[0])
    assert abs(other.width - box.width) < 0.6 and abs(other.height - box.height) < 0.4
    # Deterministic, and smaller for a smaller core share.
    assert again == core_outline(blob + strays, core=0.8)
    small = Rect.hull(core_outline(blob, core=0.5)[0])
    assert small.width < box.width and small.height < box.height
    assert core_outline(blob[:2]) == []
    with pytest.raises(ValueError):
        core_outline(blob, core=1.0)


def _inside(pt, ring) -> bool:
    hit = False
    for a, b in zip(ring, ring[1:] + ring[:1]):
        if (a.y > pt.y) != (b.y > pt.y):
            hit ^= a.x + (pt.y - a.y) * (b.x - a.x) / (b.y - a.y) > pt.x
    return hit


def test_core_outline_follows_a_curved_cluster() -> None:
    from inklet.core import Vec2
    from inklet.plot.outlines import core_outline

    rng = random.Random(6)
    arc = []
    for _ in range(3000):
        t = rng.uniform(0, math.pi)
        r = 10 + rng.gauss(0, 0.6)
        arc.append(Vec2(r * math.cos(t), -r * math.sin(t)))
    rings = core_outline(arc, core=0.8)
    assert len(rings) == 1
    # On the arc, not over its hollow as a hull would be.
    assert _inside(Vec2(0, -10), rings[0])
    assert not _inside(Vec2(0, -4), rings[0])


@pytest.mark.parametrize("style", ["line", "fill", True])
def test_embedding_outlines_one_path_per_cluster(style) -> None:
    points, names = cloud(per=500)
    rng = random.Random(9)
    # Strays of one cluster all over the panel.
    points += [(rng.uniform(-6, 6), rng.uniform(-6, 6)) for _ in range(30)]
    names += ["NK"] * 30
    p = panel(50, 50, x=(-7, 7), y=(-7, 7))
    p.embedding(points, names, size=0.4, outline=style)
    note = p._over[-1].notes["embedding"]
    wanted = "line" if style is True else style
    assert note["outline"]["style"] == wanted
    assert note["outline"]["rings"] == {n: 1 for n in CENTRES}
    paths = outline_paths(p, "mark-line" if wanted == "line" else "mark")
    assert len(paths) == len(CENTRES)
    # The strays do not balloon NK's outline: it stays round its own blob
    # (about 3 x 2 data units, 11 x 7 mm here).
    nk = paths[list(CENTRES).index("NK")]
    assert nk.bbox.width < 16 and nk.bbox.height < 11
    nodes = placed(p)
    batch = next(k for k, n in enumerate(nodes)
                 if isinstance(n.diagram.prim, MarkerBatchPrim))
    first = nodes.index(paths[0])
    colour = cluster_colors(len(CENTRES))[0]
    if wanted == "line":
        assert paths[0].style.stroke == colour and first > batch
    else:
        assert paths[0].style.fill != colour and first < batch
    assert [d for d in lint(p.build()) if d.severity != "info"] == []


def test_embedding_outline_is_opt_in_and_checked() -> None:
    points, names = cloud(per=60)
    p = panel(40, 40, x=(-7, 7), y=(-7, 7))
    p.embedding(points, names)
    assert "outline" not in p._over[-1].notes["embedding"]
    assert outline_paths(p, "mark-line") == outline_paths(p, "mark") == []
    with pytest.raises(DiagramError):
        panel(40, 40).embedding(points, names, outline="hull")
    with pytest.raises(DiagramError):
        panel(40, 40).embedding(points, names, outline="line", outline_core=1.2)


def test_embedding_outline_is_fast_for_many_points() -> None:
    import time

    rng = random.Random(1)
    points, names = [], []
    for k in range(8):
        cx, cy = rng.uniform(-5, 5), rng.uniform(-5, 5)
        for _ in range(5000):
            points.append((cx + rng.gauss(0, .7), cy + rng.gauss(0, .5)))
            names.append(f"c{k}")
    p = panel(60, 60, x=(-8, 8), y=(-8, 8))
    start = time.perf_counter()
    p.embedding(points, names, size=0.3, outline="line")
    assert time.perf_counter() - start < 5.0


# -- names clear of other clusters --------------------------------------------


def test_names_avoid_other_clusters_points() -> None:
    rng = random.Random(3)
    points, names = [], []
    # A dense small cluster laid over the centre of a wide one.
    for _ in range(2000):
        points.append((rng.gauss(0, 1.6), rng.gauss(0, 1.2)))
        names.append("Background cells")
    for _ in range(600):
        points.append((rng.gauss(0, .3), rng.gauss(0, .25)))
        names.append("Core")
    p = panel(50, 50, x=(-5, 5), y=(-5, 5))
    p.embedding(points, names, size=0.35)
    note = p._over[-1].notes["embedding"]
    boxes = {}
    for node in placed(p):
        if node.diagram.kind == POINT_LABEL_KIND:
            for name, at in note["labels"].items():
                centre = p.point(*at)
                if math.hypot(node.bbox.center.x - centre.x,
                              node.bbox.center.y - centre.y) < 1e-6:
                    boxes[name] = node.bbox
    assert set(boxes) == {"Background cells", "Core"}
    # The wide cluster's name was at the shared centre; it moved off the
    # small cluster's points. The small one's name sits on its own points.
    core = [p.point(*q) for q, n in zip(points, names) if n == "Core"]
    box = boxes["Background cells"]
    assert not any(box.x0 <= q.x <= box.x1 and box.y0 <= q.y <= box.y1
                   for q in core)
    # The small cluster lies wholly inside the wide one, so no place near
    # it is free of the wide one's points; the note says so.
    assert note["covering"] == ["Core"]


@pytest.mark.parametrize("outline", [None, "line"])
def test_a_name_may_cover_its_own_cluster(outline) -> None:
    points, names = cloud(per=300)
    p = panel(50, 50, x=(-7, 7), y=(-7, 7))
    # Names wider than their clusters' cores, which may cross their own
    # outline line.
    p.embedding(points, names, size=0.4, outline=outline, outline_core=0.5)
    note = p._over[-1].notes["embedding"]
    # Well-separated clusters: every name stays at its own centre.
    for name, at in note["labels"].items():
        cx, cy = note["centres"][name]
        assert math.hypot(at[0] - cx, at[1] - cy) < 1e-6
    assert note["covering"] == []
