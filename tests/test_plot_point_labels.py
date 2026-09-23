"""Panel.label_points: many labels placed clear of marks and of each other."""

from __future__ import annotations

import random

import pytest

import inklet
from inklet import use_theme
from inklet.core import DiagramError, resolve
from inklet.diagnostics import lint
from inklet.draw.coords import as_drawn
from inklet.plot import panel
from inklet.plot.point_labels import LEADER_KIND, POINT_LABEL_KIND


@pytest.fixture(autouse=True)
def _theme():
    use_theme("nature")


def label_boxes(p):
    out = {}
    for placed in resolve(as_drawn(p.build())).values():
        prim = placed.diagram.prim
        if placed.diagram.kind == POINT_LABEL_KIND and getattr(prim, "text", None):
            out[prim.text] = placed.bbox
    return out


def note_of(p):
    for node in p._over:
        if "point_labels" in node.notes:
            return node.notes["point_labels"]
    raise AssertionError("no point label node")


def overlaps(a, b) -> bool:
    return a.x0 < b.x1 and b.x0 < a.x1 and a.y0 < b.y1 and b.y0 < a.y1


def test_isolated_points_are_labelled_beside_them_without_leaders() -> None:
    p = panel(40, 30, x=(0, 10), y=(0, 10))
    pts = [(2, 2), (8, 8)]
    p.scatter(pts)
    p.label_points(pts, ["low", "high"])
    boxes = label_boxes(p)
    note = note_of(p)
    assert note == {"count": 2, "leaders": [], "unresolved": []}
    for (x, y), name in zip(pts, ["low", "high"]):
        centre = p.point(x, y)
        box = boxes[name]
        assert abs(box.center.x - centre.x) < 6 and abs(box.center.y - centre.y) < 6
        assert not (box.x0 <= centre.x <= box.x1 and box.y0 <= centre.y <= box.y1)


def test_crowded_points_get_distinct_non_overlapping_labels() -> None:
    p = panel(40, 30, x=(0, 10), y=(0, 10))
    pts = [(5, 5), (5.2, 5.1), (4.9, 5.2), (5.1, 4.8), (5.3, 5.3)]
    p.scatter(pts)
    names = ["alpha", "beta", "gamma", "delta", "epsilon"]
    p.label_points(pts, names)
    boxes = label_boxes(p)
    assert sorted(boxes) == sorted(names)
    values = list(boxes.values())
    for i, a in enumerate(values):
        for b in values[i + 1:]:
            assert not overlaps(a, b)
    assert note_of(p)["unresolved"] == []
    # At least one label had to move out and got a leader.
    assert note_of(p)["leaders"]
    leaders = [x for x in resolve(as_drawn(p.build())).values()
               if x.diagram.kind == LEADER_KIND]
    assert leaders


def test_labels_avoid_a_dense_batched_scatter() -> None:
    rng = random.Random(1)
    cloud = [(rng.uniform(0, 10), rng.uniform(0, 5)) for _ in range(400)]
    p = panel(40, 30, x=(0, 10), y=(0, 10))
    p.scatter(cloud, size=0.6)
    hits = [(5, 8), (2, 9)]
    p.scatter(hits)
    p.label_points(hits, ["A", "B"])
    marks = [(p.point(x, y)) for x, y in cloud]
    for box in label_boxes(p).values():
        assert not any(box.x0 < m.x < box.x1 and box.y0 < m.y < box.y1
                       for m in marks)


def test_placement_is_deterministic() -> None:
    def build():
        p = panel(40, 30, x=(0, 10), y=(0, 10))
        pts = [(5, 5), (5.2, 5.1), (4.9, 5.2)]
        p.scatter(pts).label_points(pts, ["a", "b", "c"])
        return sorted((name, round(b.x0, 9), round(b.y0, 9))
                      for name, b in label_boxes(p).items())
    assert build() == build()


def test_mismatched_labels_are_refused() -> None:
    p = panel(40, 30, x=(0, 10), y=(0, 10))
    with pytest.raises(DiagramError):
        p.label_points([(1, 1)], ["a", "b"])


def test_labelled_scatter_lints_clean_and_exports() -> None:
    p = panel(40, 30, x=(0, 10), y=(0, 10))
    pts = [(2, 3), (2.3, 3.2), (7, 7), (7.1, 6.8)]
    p.scatter(pts).label_points(pts, ["one", "two", "three", "four"]).axes()
    node = p.build()
    assert lint(node) == []
    assert inklet.to_pdf(node)[:4] == b"%PDF"
