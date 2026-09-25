"""Weighted networks, the width key, chord diagrams and arc diagrams."""

from __future__ import annotations

import math
import re

import pytest

import inklet
from inklet import use_theme
from inklet.core import DiagramError, resolve
from inklet.diagnostics import lint
from inklet.plot import chord_layout, width_scale


@pytest.fixture(autouse=True)
def _theme():
    use_theme("nature")


def _svg(node) -> str:
    return re.sub(r'(id|href|clip-path)="[^"]*"', "", inklet.to_svg(node))


def _note(node, key):
    return next(x.diagram.notes[key] for x in resolve(node).values() if key in x.diagram.notes)


NODES = {"a": 40, "b": 10, "c": 5, "d": 20, "e": 1}
EDGES = [("a", "b", 100, "x"), ("b", "c", 10, "y"), ("c", "a", 1, "x"),
         ("d", "e", 50, "y"), ("a", "d", 25, "x")]


def test_width_scale_is_proportional_with_a_floor() -> None:
    s = width_scale(100, 2.0, floor=0.1)
    assert s(100) == 2.0 and s(50) == 1.0
    assert s(1) == 0.1 and s.floored(1) and not s.floored(50)
    assert s(1000) == 2.0                     # past the top is drawn at the top
    assert all(0 < v <= 100 for v in s.ticks(3)) and len(s.ticks(3)) >= 3
    with pytest.raises(DiagramError):
        width_scale(0, 1)
    with pytest.raises(DiagramError):
        s(-1)


def test_circular_network_geometry_and_keys() -> None:
    p = inklet.panel(50, 50)
    p.network(NODES, EDGES, shape="square", groups={"a": "hub"}, arrows=True, width=2)
    p.width_key(title="weight").legend(side="bottom")
    node = p.build()
    note = _note(node, "network")
    pos = note["positions"]
    centre = (sum(x for x, _ in pos.values()) / 5, sum(y for _, y in pos.values()) / 5)
    radii = [math.hypot(x - centre[0], y - centre[1]) for x, y in pos.values()]
    assert max(radii) - min(radii) < 1e-6           # all on one ring
    # The first node sits at twelve o'clock.
    assert pos["a"][1] < centre[1] and abs(pos["a"][0] - centre[0]) < 1e-6
    # Areas are proportional to value above the floor.
    d = note["diameters"]
    assert math.isclose(d["b"] ** 2 / d["a"] ** 2, 10 / 40, rel_tol=1e-6)
    assert list(note["categories"]) == ["x", "y"]
    key = _note(node, "width_key")
    assert key["width"] == 2.0 and key["top"] == 100
    names = [k.name for k in p.keys]
    assert names == ["hub", "x", "y"]
    assert lint(node) == []


def test_force_network_fills_the_area_and_is_deterministic() -> None:
    def build():
        return inklet.panel(50, 40).network(list(NODES), EDGES, layout="force").build()
    node = build()
    pos = _note(node, "network")["positions"]
    xs = [x for x, _ in pos.values()]
    assert max(xs) - min(xs) > 30
    assert _svg(node) == _svg(build())
    with pytest.raises(DiagramError):
        inklet.panel(50, 40).network(NODES, EDGES, layout="spiral")
    with pytest.raises(DiagramError):
        inklet.panel(50, 40).network(NODES, [("a", "zz", 1)])


def test_width_key_needs_widths() -> None:
    with pytest.raises(DiagramError):
        inklet.panel(20, 20).width_key()


def test_chord_layout_angles() -> None:
    m = [[0, 6, 2], [6, 0, 4], [2, 4, 0]]
    layout = chord_layout(m, ["a", "b", "c"], gap=4)
    spans = [g.end - g.start for g in layout.groups]
    assert math.isclose(sum(spans), 360 - 3 * 4)
    assert math.isclose(spans[0] / spans[1], 8 / 10)
    # Symmetric flows are as wide at both ends.
    for r in layout.ribbons:
        assert math.isclose(r.source_span[1] - r.source_span[0],
                            r.target_span[1] - r.target_span[0])
    directed = chord_layout([[0, 3], [1, 0]], directed=True, gap=0)
    assert [g.value for g in directed.groups] == [4.0, 4.0]
    assert len(directed.ribbons) == 2
    with pytest.raises(DiagramError):
        chord_layout([[0, 1]])
    with pytest.raises(DiagramError):
        chord_layout([[0, -1], [1, 0]])
    with pytest.raises(DiagramError):
        chord_layout([[0, 0], [0, 0]])


def test_chord_panel_fits_and_lints_clean() -> None:
    m = [[0, 5, 3, 1], [5, 0, 2, 0], [3, 2, 1, 4], [1, 0, 4, 0]]
    node = inklet.panel(45, 45).chord(m, ["V1", "LM", "AL", "PM"]).build()
    note = _note(node, "chord")
    assert note["radius"] + note["ring"] < 22.5
    assert lint(node) == []
    assert lint(inklet.panel(45, 45).chord(m, ["V1", "LM", "AL", "PM"], directed=True).build()) == []


def test_arc_diagram_positions_and_directed_arcs() -> None:
    p = inklet.panel(60, 25)
    p.arc_diagram(NODES, EDGES, groups={"a": "g1", "b": "g1", "c": "g2"})
    p.width_key().legend(side="bottom")
    node = p.build()
    note = _note(node, "arc_diagram")
    xs = [note["positions"][n] for n in NODES]
    assert xs == sorted(xs)
    steps = [b - a for a, b in zip(xs, xs[1:])]
    assert max(steps) - min(steps) < 1e-9          # evenly spaced
    assert 0 < note["lift"] <= 1
    assert lint(node) == []
    directed = inklet.panel(60, 30).arc_diagram(list(NODES), EDGES, directed=True).build()
    assert lint(directed) == []
