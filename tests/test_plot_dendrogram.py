"""Panel.dendrogram and plot.dendrogram_layout."""

from __future__ import annotations

import io

import pytest

import inklet
from inklet import use_theme
from inklet.core import DiagramError, resolve
from inklet.diagnostics import lint
from inklet.draw.coords import as_drawn
from inklet.draw.shapes import MARK_LINE_KIND
from inklet.plot import dendrogram_layout, panel


@pytest.fixture(autouse=True)
def _theme():
    use_theme("nature")


# Five leaves: (1, 3) at 0.5, (0, 5) at 1.0, (2, 4) at 1.5, then 6 + 7 at 3.
LINK = [[1, 3, 0.5, 2], [0, 5, 1.0, 3], [2, 4, 1.5, 2], [6, 7, 3.0, 5]]
NAMES = ["a", "b", "c", "d", "e"]


def lines(p):
    return [x for x in resolve(as_drawn(p.build())).values()
            if x.diagram.kind == MARK_LINE_KIND]


def test_linkage_layout_orders_leaves_left_child_first() -> None:
    layout = dendrogram_layout(LINK, labels=NAMES)
    assert layout.order == (0, 1, 3, 2, 4)
    assert layout.leaves == ("a", "b", "d", "c", "e")
    assert layout.height == 3.0
    first = layout.links[0]
    assert first.children == ((1.0, 0.0), (2.0, 0.0))
    assert first.position == 1.5 and first.height == 0.5
    root = layout.links[-1]
    assert root.children == ((0.75, 1.0), (3.5, 1.5))
    assert sorted(root.members) == [0, 1, 2, 3, 4]


def test_layout_matches_scipy_leaf_order() -> None:
    hierarchy = pytest.importorskip("scipy.cluster.hierarchy")
    import random

    rng = random.Random(3)
    data = [[rng.gauss(0, 1) for _ in range(4)] for _ in range(12)]
    link = hierarchy.linkage(data, "average")
    expected = hierarchy.dendrogram(link, no_plot=True)["leaves"]
    assert list(dendrogram_layout(link).order) == expected
    assert list(dendrogram_layout(list(link)).order) == expected


def test_nested_tree_uses_levels_and_allows_many_children() -> None:
    layout = dendrogram_layout((("a", "b"), ("c", "d", "e")))
    assert layout.leaves == ("a", "b", "c", "d", "e")
    assert layout.height == 2.0
    three = [link for link in layout.links if len(link.children) == 3][0]
    assert three.position == 3.0 and three.height == 1.0


def test_layout_errors() -> None:
    with pytest.raises(DiagramError):
        dendrogram_layout([[0, 1, 1.0, 2], [0, 2, 2.0, 2]])      # 0 reused
    with pytest.raises(DiagramError):
        dendrogram_layout([[0, 5, 1.0, 2], [1, 2, 2.0, 2]])      # 5 not yet made
    with pytest.raises(DiagramError):
        dendrogram_layout([[0, 0, 1.0, 2]])
    with pytest.raises(DiagramError):
        dendrogram_layout(LINK, labels=["a"])
    with pytest.raises(DiagramError):
        dendrogram_layout((("a", "b"), "a"))
    with pytest.raises(DiagramError):
        dendrogram_layout((("a", "b"),), labels=["a", "b"])


def test_vertical_dendrogram_on_a_continuous_axis() -> None:
    p = panel(40, 30, x=(-0.5, 4.5), y=(0, 3))
    p.dendrogram(LINK, labels=NAMES)
    drawn = lines(p)
    assert len(drawn) == 4
    # The root spans from the first to the second subtree's merge position.
    root = max(drawn, key=lambda d: d.bbox.height)
    assert root.bbox.y0 == pytest.approx(p.y.map(3.0), abs=1e-6)
    assert root.bbox.x0 == pytest.approx(p.x.map(0.75), abs=1e-6)
    assert root.bbox.x1 == pytest.approx(p.x.map(3.5), abs=1e-6)
    # Leaf tips reach height 0.
    assert max(d.bbox.y1 for d in drawn) == pytest.approx(p.y.map(0), abs=1e-6)


def test_horizontal_dendrogram_aligns_with_a_band_and_checks_its_order() -> None:
    order = list(dendrogram_layout(LINK, labels=NAMES).leaves)
    p = panel(12, 40, x=(3, 0), y=order)
    p.dendrogram(LINK, labels=NAMES, orient="h")
    tips = sorted({round(d.bbox.y1, 6) for d in lines(p)} |
                  {round(d.bbox.y0, 6) for d in lines(p)})
    for name in order:
        assert round(p.y.map(name), 6) in tips
    # Leaves at the right-hand edge (height 0 on a reversed x).
    assert max(d.bbox.x1 for d in lines(p)) == pytest.approx(6, abs=1e-6)
    with pytest.raises(DiagramError, match="leaf order"):
        panel(12, 40, x=(3, 0), y=NAMES).dendrogram(LINK, labels=NAMES, orient="h")
    with pytest.raises(DiagramError):
        panel(12, 40, x=NAMES, y=order).dendrogram(LINK, labels=NAMES, orient="h")
    with pytest.raises(DiagramError):
        p.dendrogram(LINK, orient="x")


def test_threshold_colours_clusters_below_it() -> None:
    p = panel(40, 30, x=(-0.5, 4.5), y=(0, 3))
    p.dendrogram(LINK, labels=NAMES, threshold=2.0, color=["#aa0000", "#0000aa"])
    note = p._content[-1].notes["dendrogram"]
    assert note["clusters"] == [["a", "b", "d"], ["c", "e"]]
    svg = inklet.to_svg(p.build())
    assert "#aa0000" in svg and "#0000aa" in svg
    plain = panel(40, 30, x=(-0.5, 4.5), y=(0, 3))
    plain.dendrogram(LINK)
    assert plain._content[-1].notes["dendrogram"]["clusters"] == []


def _ink_outside(node, margin: float = 2.0, dpi: int = 600) -> list[str]:
    from PIL import Image

    fig = inklet.figure(width=node.bbox.width + 2 * margin, theme="nature")
    fig.add(node)
    image = Image.open(io.BytesIO(fig.to_png(dpi=dpi))).convert("L")
    width, height = image.size
    band_px = int((margin - 0.25) * dpi / 25.4)
    pixels = image.load()
    sides = {"left": (range(band_px), range(height)),
             "right": (range(width - band_px, width), range(height)),
             "top": (range(width), range(band_px)),
             "bottom": (range(width), range(height - band_px, height))}
    return [side for side, (xs, ys) in sides.items()
            if any(pixels[x, y] < 250 for x in xs for y in ys)]


def test_dendrogram_beside_a_heatmap_lints_clean_and_ink_stays_measured() -> None:
    order = list(dendrogram_layout(LINK, labels=NAMES).leaves)
    tree = panel(12, 40, x=(3, 0), y=order)
    tree.dendrogram(LINK, labels=NAMES, orient="h", threshold=2.0)
    heat = panel(30, 40, x=["x", "y", "z"], y=order)
    heat.matrix([[k + j for j in range(3)] for k in range(5)], x=["x", "y", "z"],
                y=order, ramp=inklet.ramp("tol-ylorbr"), scale=inklet.linear((0, 8)),
                raster=False)
    heat.axis("bottom", spine=False).axis("right", spine=False)
    alone = panel(40, 30, x=(-0.5, 4.5), y=(0, 3))
    alone.dendrogram(LINK, labels=NAMES).axis("left", label="Distance")
    for node in (inklet.row([tree, heat], gap=1), alone.build()):
        assert lint(node) == []
        assert inklet.to_pdf(node)[:4] == b"%PDF"
        assert "<path" in inklet.to_svg(node)
        assert _ink_outside(node) == []
    spec = inklet.plot_spec(x=(-0.5, 4.5), y=(0, 3), height=30)
    spec.dendrogram(LINK)
    doc = inklet.document(width=80)
    doc.add("tree", spec)
    assert "<path" in doc.compile().to_svg()
