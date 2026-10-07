"""Point labels against lint's clearance, and leaders for labels that could
name a neighbour (examples/compare/ISSUES.md #5)."""

from __future__ import annotations

import math
import random
import sys
from pathlib import Path

import pytest

import inklet
from inklet import use_theme
from inklet.core import resolve
from inklet.diagnostics import lint
from inklet.diagnostics.rules import DEFAULT_MIN_CLEARANCE_MM
from inklet.draw.coords import as_drawn
from inklet.plot import panel
from inklet.plot import point_labels as pl

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _theme():
    use_theme("nature")


def _note(p) -> dict:
    p.build()
    return next(n.notes["point_labels"] for n in p._over
                if "point_labels" in n.notes)


def _grid_panel(spacing: float):
    p = panel(40, 30, x=(0, 16), y=(0, 12))
    peers = [(8 + dx * spacing, 6 + dy * spacing)
             for dx in range(-3, 4) for dy in range(-2, 3) if (dx, dy) != (0, 0)]
    p.scatter(peers, size=1.0)
    p.scatter([(8, 6)], size=1.0)
    p.label_points([(8, 6)], ["gene"])
    return p


def test_the_clearance_is_lints_own() -> None:
    assert pl.lint_clearance() == DEFAULT_MIN_CLEARANCE_MM


def test_a_label_among_equal_points_gets_a_leader() -> None:
    # Every side of the point has another point as near as it: the label
    # names one of them only with a line to it.
    note = _note(_grid_panel(1.5))
    assert note["leaders"] == [0]
    assert note["covering_marks"] == []


def test_a_label_with_a_free_side_needs_no_leader() -> None:
    p = panel(40, 30, x=(0, 10), y=(0, 10))
    p.scatter([(5, 5)], size=1.0)
    p.label_points([(5, 5)], ["solo"])
    assert _note(p)["leaders"] == []


def test_a_smaller_background_cloud_does_not_force_leaders() -> None:
    p = panel(40, 30, x=(0, 16), y=(0, 12))
    cloud = [(8 + dx * 1.5, 6 + dy * 1.5)
             for dx in range(-3, 4) for dy in range(-2, 3) if (dx, dy) != (0, 0)]
    p.scatter(cloud, size=0.5)
    p.scatter([(8, 6)], size=1.2)
    p.label_points([(8, 6)], ["gene"])
    assert _note(p)["leaders"] == []


def test_needs_leader_rule() -> None:
    from inklet.core import Rect, Vec2
    anchor = Vec2(0, 0)
    beside = Rect(1.5, -1, 5, 1)                       # east of the point
    other = Rect(5.5, -0.5, 6.5, 0.5)                  # a peer past its end
    grid = pl._Grid([other], 2.0)
    number_of = {id(other): 0}
    assert not pl._needs_leader(anchor, beside, 3.0, 0.8, pl._Grid([], 2.0),
                                {}, [], set())
    # Far from its own point.
    assert pl._needs_leader(anchor, Rect(4, -1, 8, 1), 3.0, 0.8,
                            pl._Grid([], 2.0), {}, [], set())
    # A peer nearer the label than the label's own point.
    assert pl._needs_leader(anchor, beside, 3.0, 0.8, grid, number_of,
                            [True], set())
    # ... unless it is the point's own marker, or smaller than a peer.
    assert not pl._needs_leader(anchor, beside, 3.0, 0.8, grid, number_of,
                                [True], {0})
    assert not pl._needs_leader(anchor, beside, 3.0, 1.5, grid, number_of,
                                [True], set())


def test_a_diagonal_label_is_moved_clear_of_its_marker_corner() -> None:
    from inklet.core import Rect, Vec2
    r, keep = 0.7, 1.0
    marker = Rect(-r, -r, r, r)
    # North-east on the first ring: set off by the gap along the diagonal,
    # which leaves the box's corner nearer the marker box's corner.
    box = pl._box_at(Vec2(0, 0), -45.0, keep + r, 2.0, 2.0)
    insets = (0.05, 0.05, 0.05, 0.05)
    assert pl._gap(pl._inked(box, insets), marker) < keep
    moved = pl._cleared(box, insets, marker, -45.0, keep)
    assert pl._gap(pl._inked(moved, insets), marker) == pytest.approx(keep, abs=1e-6)
    # Moved straight out along the diagonal, not sideways.
    shift = (moved.center.x - box.center.x, moved.center.y - box.center.y)
    assert shift[0] == pytest.approx(-shift[1]) and shift[0] > 0
    # A box already clear is left alone.
    east = pl._box_at(Vec2(0, 0), 0.0, keep + r, 2.0, 2.0)
    assert pl._cleared(east, insets, marker, 0.0, keep) == east


def test_scatter_text_labels_lint_clean() -> None:
    # The quick API's `text=` goes through label_points.
    random.seed(3)
    pts = {"x": [random.gauss(0, 1) for _ in range(40)],
           "y": [random.gauss(0, 1) for _ in range(40)]}
    pts["name"] = [f"g{k}" if abs(pts["x"][k]) > 1.3 else None for k in range(40)]
    report = inklet.scatter(pts, x="x", y="y", text="name").report()
    assert "CROWDING" not in report


def test_compare_volcano_labels_are_next_to_their_point_or_led() -> None:
    pytest.importorskip("pandas")
    sys.path.insert(0, str(ROOT / "examples" / "compare"))
    try:
        from data import volcano
    finally:
        sys.path.pop(0)
    df = volcano()
    p = panel(80, 55, x=(-6, 4.5), y=(0, 32))
    p.volcano(list(df["log2fc"]), list(df["p"]), labels=list(df["gene"]),
              top=10, size=1.0)
    p.axes(x="log2 fold change", y="-log10 p")
    built = p.build()
    assert [d for d in lint(built) if d.code == "CROWDING"] == []
    note = _note(p)
    assert note["unresolved"] == []
    # Every label without a leader has its own point as the nearest point.
    texts = {}
    for placed in resolve(as_drawn(built)).values():
        prim = placed.diagram.prim
        if placed.diagram.kind == pl.POINT_LABEL_KIND and getattr(prim, "text", None):
            texts[prim.text] = placed.bbox
    volcano_note = next(n.notes["volcano"] for n in [*p._content, *p._over]
                        if "volcano" in n.notes)
    genes = list(df["gene"])
    folds, ps = list(df["log2fc"]), list(df["p"])
    points = [p.point(f, min(32.0, -math.log10(max(q, 1e-300))))
              for f, q in zip(folds, ps)]
    led = {genes[volcano_note["labelled"][i]] for i in note["leaders"]}
    for index in volcano_note["labelled"]:
        name = genes[index]
        if name in led:
            continue
        box = texts[name]
        own = pl._to_box(points[index], box)
        assert own < 3.5, name
        nearest = min(pl._to_box(q, box) for k, q in enumerate(points)
                      if k != index and folds[k] * folds[index] > 0
                      and abs(folds[k]) > 1)
        assert nearest >= own, name
