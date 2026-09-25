"""Panel.split_violin."""

from __future__ import annotations

import random

import pytest

import inklet
from inklet import use_theme
from inklet.core import DiagramError, resolve
from inklet.diagnostics import lint
from inklet.draw.coords import as_drawn
from inklet.draw.shapes import MARK_KIND, MARK_LINE_KIND
from inklet.plot import panel
from inklet.plot.split_violin import split_violin
from inklet.plot.statistics import quantile

CATS = ["CA1", "CA3", "DG"]


@pytest.fixture(autouse=True)
def _theme():
    use_theme("nature")


def conditions(seed: int = 4):
    rng = random.Random(seed)
    first = {c: [rng.gauss(4 + k, 0.9) for _ in range(60)] for k, c in enumerate(CATS)}
    second = {c: [rng.gauss(5 + k, 1.4) for _ in range(40)] for k, c in enumerate(CATS)}
    return first, second


def placed(p, kind):
    return [x for x in resolve(as_drawn(p.build())).values() if x.diagram.kind == kind]


def test_halves_sit_either_side_of_the_centre_line() -> None:
    first, second = conditions()
    p = panel(50, 36, x=CATS, y=(0, 12))
    p.split_violin(first, second, median=False)
    halves = placed(p, MARK_KIND)
    assert len(halves) == 6
    for name in CATS:
        centre = p.x.map(name)
        mine = [h for h in halves if abs(h.bbox.x1 - centre) < 1e-6
                or abs(h.bbox.x0 - centre) < 1e-6]
        left = [h for h in mine if abs(h.bbox.x1 - centre) < 1e-6]
        right = [h for h in mine if abs(h.bbox.x0 - centre) < 1e-6]
        assert len(left) == len(right) == 1
        # Shared scale: the narrower density does not reach the slot edge.
        reach = 0.4 * abs(p.x.step)
        assert max(left[0].bbox.width, right[0].bbox.width) == pytest.approx(reach, rel=1e-3)
        assert right[0].bbox.width < left[0].bbox.width
    each = panel(50, 36, x=CATS, y=(0, 12))
    each.split_violin(first, second, median=False, scale="each")
    for h in placed(each, MARK_KIND):
        assert h.bbox.width == pytest.approx(0.4 * abs(each.x.step), rel=1e-3)


def test_horizontal_first_half_is_above() -> None:
    first, second = conditions()
    p = panel(50, 36, x=(0, 12), y=CATS)
    p.split_violin(first, second, orient="h", median=False)
    halves = placed(p, MARK_KIND)
    for name in CATS:
        centre = p.y.map(name)
        above = [h for h in halves if abs(h.bbox.y1 - centre) < 1e-6]
        below = [h for h in halves if abs(h.bbox.y0 - centre) < 1e-6]
        assert len(above) == len(below) == 1


def test_median_and_quartile_lines() -> None:
    first, second = conditions()
    p = panel(50, 36, x=CATS, y=(0, 12))
    p.split_violin(first, second, quartiles=True)
    lines = placed(p, MARK_LINE_KIND)
    assert len(lines) == 3 * 2 * 3
    dashed = [x for x in lines if x.style.stroke_dash]
    assert len(dashed) == 12
    level = p.y.map(quantile(first["CA1"], 0.5))
    assert any(abs(x.bbox.y0 - level) < 1e-6 and abs(x.bbox.x1 - p.x.map("CA1")) < 1e-6
               for x in lines)


def test_sequences_names_and_missing_halves() -> None:
    first, second = conditions()
    p = panel(50, 36, x=CATS, y=(0, 12))
    p.split_violin([first[c] for c in CATS], [second[c] for c in CATS],
                   names=["control", "treated"], colors=["#e6b93f", "#24698c"])
    assert [k.name for k in p.keys] == ["control", "treated"]
    assert p.keys[0].fill == "#e6b93f"
    q = panel(50, 36, x=CATS, y=(0, 12))
    node, _, note = split_violin(q, {"CA1": first["CA1"], "CA3": [1.0]},
                                 {"CA1": second["CA1"], "DG": second["DG"]})
    assert note["drawn"] == [0, 2]
    assert (1, 0) in note["empty"] and (1, 1) in note["empty"] and (2, 0) in note["empty"]
    with pytest.raises(DiagramError):
        split_violin(q, first, [1, 2, 3])
    with pytest.raises(DiagramError):
        split_violin(q, first, second, scale="width")
    with pytest.raises(DiagramError):
        q.split_violin(first, second, names=["one"])
    with pytest.raises(DiagramError):
        split_violin(q, {"CA1": [1.0]}, {"CA1": [2.0]})


def test_split_violin_lints_clean() -> None:
    first, second = conditions()
    p = panel(50, 36, x=CATS, y=(0, 12))
    p.split_violin(first, second, names=["control", "treated"], quartiles=True)
    p.axes(y="rate / Hz").legend(side="top")
    node = p.build()
    assert lint(node) == []
    assert inklet.to_pdf(node)[:4] == b"%PDF"
    spec = inklet.plot_spec(x=CATS, y=(0, 12), height=36)
    spec.split_violin(first, second)
    doc = inklet.document(width=80)
    doc.add("split", spec)
    assert "<path" in doc.compile().to_svg()
