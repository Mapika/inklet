"""Panel.ridgeline."""

from __future__ import annotations

import io
import math
import random

import pytest

import inklet
from inklet import use_theme
from inklet.core import DiagramError, resolve
from inklet.diagnostics import lint
from inklet.draw.coords import as_drawn
from inklet.draw.shapes import MARK_KIND, MARK_LINE_KIND
from inklet.plot import band, panel


@pytest.fixture(autouse=True)
def _theme():
    use_theme("nature")


STAGES = ["E12", "E14", "E16", "E18"]


def samples(seed: int = 3) -> dict[str, list[float]]:
    rng = random.Random(seed)
    return {s: [rng.gauss(2 + k * 1.5, 0.6) for _ in range(60)]
            for k, s in enumerate(STAGES)}


def placements(p, kind):
    return [x for x in resolve(as_drawn(p.build())).values()
            if x.diagram.kind == kind]


def ridge_panel(**kwargs):
    p = panel(50, 40, x=(0, 10), y=list(reversed(STAGES)))
    p.ridgeline(samples(), **kwargs)
    return p


def test_each_ridge_stands_on_the_lower_edge_of_its_row() -> None:
    p = ridge_panel()
    fills = placements(p, MARK_KIND)
    assert len(fills) == 4
    step = abs(p.y.step)
    bottoms = sorted(f.bbox.y1 for f in fills)
    expected = sorted(p.y.map(s) + step / 2 for s in STAGES)
    assert bottoms == pytest.approx(expected, abs=1e-6)
    # Ridges run across the whole x domain.
    for f in fills:
        assert f.bbox.x0 == pytest.approx(-25, abs=1e-6)
        assert f.bbox.x1 == pytest.approx(25, abs=1e-6)


def test_ridges_are_drawn_top_down_so_lower_ones_cover_upper() -> None:
    p = ridge_panel()
    node = p._content[-1]
    order = [child for child in node.children if child.kind == MARK_KIND]
    assert [c.bbox.y1 for c in order] == sorted(c.bbox.y1 for c in order)


def test_shared_scale_keeps_proportions_and_fit_keeps_ink_inside() -> None:
    p = ridge_panel(overlap=3.0)
    note = p._content[-1].notes["ridgeline"]
    assert note["overlap"] < 3.0 and note["above"] == pytest.approx(0, abs=1e-6)
    lines = placements(p, MARK_LINE_KIND)
    assert min(line.bbox.y0 for line in lines) >= -20 - 1e-6
    free = ridge_panel(overlap=3.0, fit=False)
    note = free._content[-1].notes["ridgeline"]
    assert note["overlap"] == 3.0 and note["above"] > 0


def test_each_scale_gives_every_ridge_the_same_peak() -> None:
    rng = random.Random(1)
    groups = {"a": [rng.gauss(5, 0.3) for _ in range(50)],
              "b": [rng.gauss(5, 2.0) for _ in range(50)]}
    p = panel(40, 30, x=(0, 10), y=["b", "a"])
    p.ridgeline(groups, scale="each", overlap=0.8)
    heights = [f.bbox.height for f in placements(p, MARK_KIND)]
    assert math.isclose(heights[0], heights[1], rel_tol=1e-3)


def test_ridgeline_needs_band_y_and_continuous_x() -> None:
    with pytest.raises(DiagramError):
        panel(40, 30, x=(0, 10), y=(0, 1)).ridgeline(samples())
    with pytest.raises(DiagramError):
        panel(40, 30, x=["a", "b"], y=STAGES).ridgeline(samples())
    with pytest.raises(DiagramError):
        ridge_panel(scale="global")


def test_ridgeline_works_through_plot_spec_and_band_padding() -> None:
    p = panel(50, 40, x=(0, 10), y=band(list(reversed(STAGES)), outer=1.0))
    p.ridgeline(samples(), overlap=2.0)
    assert p._content[-1].notes["ridgeline"]["overlap"] == pytest.approx(2.0)
    spec = inklet.plot_spec(x=(0, 10), y=list(reversed(STAGES)), height=40)
    spec.ridgeline(samples())
    doc = inklet.document(width=80)
    doc.add("ridges", spec)
    assert "<path" in doc.compile().to_svg()


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


def test_ridgeline_lints_clean_exports_and_ink_stays_measured() -> None:
    fitted = ridge_panel(colors=["#24698c", "#2d7d8a", "#3a9083", "#5aa374"])
    fitted.axes(x="Onset time / h")
    free = ridge_panel(overlap=2.5, fit=False)
    free.axes(x="Onset time / h")
    for p in (fitted, free):
        node = p.build()
        assert lint(node) == []
        assert inklet.to_pdf(node)[:4] == b"%PDF"
        assert "<path" in inklet.to_svg(node)
        assert _ink_outside(node) == []
