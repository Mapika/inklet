"""Hierarchy input, treemap/partition layouts and the three hierarchy plots."""

from __future__ import annotations

import math

import pytest

import inklet
from inklet import use_theme
from inklet.core import DiagramError, Rect, resolve
from inklet.diagnostics import lint
from inklet.plot.hierarchy import hierarchy, partition_layout, squarify, treemap_layout


@pytest.fixture(autouse=True)
def _theme():
    use_theme("nature")


def _svg(node) -> str:
    """The SVG with the per-process node ids taken out."""
    import re
    return re.sub(r'(id|href|clip-path)="[^"]*"', "", inklet.to_svg(node))


CORTEX = {"cortex": {"L2/3 IT": 120, "L5 ET": 40,
                     "Inhibitory": {"Pvalb": 45, "Sst": 38, "Vip": 22},
                     "Glia": {"Astro": 50, "Oligo": 64}}}


def test_three_spellings_read_the_same_tree() -> None:
    nested = hierarchy(CORTEX)
    tuples = hierarchy(("cortex", [("L2/3 IT", 120), ("L5 ET", 40),
                                   ("Inhibitory", [("Pvalb", 45), ("Sst", 38), ("Vip", 22)]),
                                   ("Glia", [("Astro", 50), ("Oligo", 64)])]))
    table = hierarchy([("cortex", None), ("L2/3 IT", "cortex", 120), ("L5 ET", "cortex", 40),
                       ("Inhibitory", "cortex"), ("Pvalb", "Inhibitory", 45),
                       ("Sst", "Inhibitory", 38), ("Vip", "Inhibitory", 22),
                       ("Glia", "cortex"), ("Astro", "Glia", 50), ("Oligo", "Glia", 64)])
    for tree in (nested, tuples, table):
        assert tree.root.name == "cortex"
        assert tree.root.value == 379
        assert tree.height == 2
        assert tree.find("Inhibitory").value == 105
        assert tree.find(("Glia", "Oligo")).value == 64
        assert [n.name for n in tree.nodes(1)] == ["L2/3 IT", "L5 ET", "Inhibitory", "Glia"]


def test_hierarchy_details_and_errors() -> None:
    # Several top-level keys get an unnamed root; a list of names counts 1 each.
    tree = hierarchy({"a": ["x", "y", "z"], "b": 2})
    assert tree.root.name == "" and tree.root.value == 5
    assert tree.find("a").value == 3
    # A table leaf without a value counts once.
    assert hierarchy([("r", None), ("p", "r"), ("q", "r")]).root.value == 2
    with pytest.raises(DiagramError):
        hierarchy({"a": -1})
    with pytest.raises(DiagramError):
        hierarchy([("a", "b"), ("b", "a")])
    with pytest.raises(DiagramError):
        hierarchy({"a": 0})
    with pytest.raises(DiagramError):
        hierarchy([("a", None), ("a", None)])


def test_squarify_tiles_the_box_with_proportional_areas() -> None:
    box = Rect(0, 0, 60, 40)
    values = [6, 6, 4, 3, 2, 2, 1]
    cells = squarify(values, box)
    total = sum(values)
    for value, cell in zip(values, cells):
        assert math.isclose(cell.width * cell.height, 2400 * value / total, rel_tol=1e-9)
        assert box.x0 - 1e-9 <= cell.x0 and cell.x1 <= box.x1 + 1e-9
        assert box.y0 - 1e-9 <= cell.y0 and cell.y1 <= box.y1 + 1e-9
    # No two cells overlap.
    for a in range(len(cells)):
        for b in range(a + 1, len(cells)):
            ca, cb = cells[a], cells[b]
            overlap = (min(ca.x1, cb.x1) - max(ca.x0, cb.x0), min(ca.y1, cb.y1) - max(ca.y0, cb.y0))
            assert overlap[0] <= 1e-9 or overlap[1] <= 1e-9
    # The worst aspect ratio of the classic example (Bruls et al.) stays small.
    assert max(max(c.width / c.height, c.height / c.width) for c in cells) < 3


def test_treemap_layout_nests_children_inside_parents() -> None:
    cells = dict((n.path, r) for n, r in treemap_layout(CORTEX, Rect(0, 0, 50, 30), padding=1))
    parent = cells[("Inhibitory",)]
    for child in ("Pvalb", "Sst", "Vip"):
        c = cells[("Inhibitory", child)]
        assert parent.x0 + 1 - 1e-9 <= c.x0 and c.x1 <= parent.x1 - 1 + 1e-9
        assert parent.y0 + 1 - 1e-9 <= c.y0 and c.y1 <= parent.y1 - 1 + 1e-9


def test_partition_fractions_add_up() -> None:
    cells = partition_layout(CORTEX)
    assert cells[0].depth == 0 and (cells[0].start, cells[0].end) == (0.0, 1.0)
    for depth in (1, 2):
        spans = [c for c in cells if c.depth == depth]
        assert all(b.start >= a.end - 1e-12 for a, b in zip(spans, spans[1:]))
    inhibitory = next(c for c in cells if c.node.name == "Inhibitory")
    kids = [c for c in cells if c.node.parent is inhibitory.node]
    assert math.isclose(kids[0].start, inhibitory.start)
    assert math.isclose(kids[-1].end, inhibitory.end)


def test_treemap_panel_areas_and_labels() -> None:
    p = inklet.panel(60, 40).treemap(CORTEX, padding=0, header=False)
    node = p.build()
    note = next(x.diagram.notes["treemap"] for x in resolve(node).values()
                if "treemap" in x.diagram.notes)
    areas = dict(note["cells"])
    assert math.isclose(areas[("L2/3 IT",)], 2400 * 120 / 379, rel_tol=1e-6)
    assert "L2/3 IT" in inklet.to_svg(node)
    assert lint(node) == []


def test_icicle_counts_highlight_and_spans() -> None:
    tree = {"a": {"a1": 3, "a2": 1}, "b": {"b1": 2, "b2": {"x": 1, "y": 1}}}
    p = inklet.panel(30, 40).icicle(tree, gap=2, highlight=["b", ("b", "b2"), ("b", "b2", "x")],
                                     labels="highlight", levels=True, counts=True)
    node = p.build()
    note = next(x.diagram.notes["icicle"] for x in resolve(node).values()
                if "icicle" in x.diagram.notes)
    assert note["levels"] == [2, 4, 2]
    assert note["highlighted"] == [1, 1, 1]
    lo, hi = note["spans"][("a",)]
    lo2, hi2 = note["spans"][("b",)]
    # Spans are proportional to the values once spacing is taken out.
    assert math.isclose((hi - lo) / (hi2 - lo2), 4 / 4)
    svg = inklet.to_svg(node)
    assert "#c9352b" in svg
    assert lint(node) == []
    with pytest.raises(DiagramError):
        inklet.panel(30, 40).icicle(tree, orient="x")
    with pytest.raises(DiagramError):
        inklet.panel(30, 40).icicle(tree, highlight="nothing")


def test_sunburst_angles_and_determinism() -> None:
    def build():
        return inklet.panel(40, 40).sunburst(CORTEX).build()
    node = build()
    note = next(x.diagram.notes["sunburst"] for x in resolve(node).values()
                if "sunburst" in x.diagram.notes)
    angles = dict(note["angles"])
    assert math.isclose(sum(a for p, a in angles.items() if len(p) == 1), 360)
    assert math.isclose(angles[("Glia",)], 360 * 114 / 379)
    assert note["radius"] == 20
    assert _svg(node) == _svg(build())
    assert lint(node) == []
