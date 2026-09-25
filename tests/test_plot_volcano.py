"""Panel.volcano and plot.volcano_points."""

from __future__ import annotations

import io
import math
import random

import pytest

import inklet
from inklet import use_theme
from inklet.core import DiagramError
from inklet.diagnostics import lint
from inklet.plot import panel
from inklet.plot.volcano import volcano_points


@pytest.fixture(autouse=True)
def _theme():
    use_theme("nature")


def data(n: int = 600, seed: int = 11):
    rng = random.Random(seed)
    fold, p = [], []
    for _ in range(n):
        effect = rng.gauss(0, 0.5) if rng.random() < 0.9 else rng.gauss(0, 1.8)
        z = effect * 1.3 + rng.gauss(0, 1)
        fold.append(effect)
        p.append(math.erfc(abs(z) / math.sqrt(2)))
    return fold, p, [f"G{k}" for k in range(n)]


def test_points_are_classified_by_both_thresholds() -> None:
    fold = [2.0, -2.0, 2.0, 0.5, -1.0, 1.0, None, 3.0]
    p = [0.01, 0.001, 0.2, 0.001, 0.04, 0.05, 0.01, 0.0]
    got = volcano_points(fold, p, fold_threshold=1.0, p_threshold=0.05)
    assert got["classes"] == ["up", "down", "ns", "ns", "down", "ns", None, "up"]
    assert got["skipped"] == [6]
    # p = 0 is drawn at the smallest positive p in the data.
    assert got["capped"] == [7]
    assert got["points"][7] == pytest.approx((3.0, 3.0))
    assert got["points"][0] == pytest.approx((2.0, 2.0))
    # Ranked by p, ties by the larger fold change.
    assert got["ranked"] == [7, 1, 0, 4]


def test_volcano_points_errors() -> None:
    with pytest.raises(DiagramError):
        volcano_points([1.0], [0.1, 0.2])
    with pytest.raises(DiagramError):
        volcano_points([1.0], [1.5])
    with pytest.raises(DiagramError):
        volcano_points([1.0], [0.1], p_threshold=0)
    with pytest.raises(DiagramError):
        volcano_points([1.0], [0.1], fold_threshold=-1)


def volcano_panel(**kwargs):
    fold, p, genes = data()
    v = panel(60, 50, x=(-6, 6), y=(0, 16))
    v.volcano(fold, p, labels=genes, **kwargs)
    return v


def test_volcano_draws_rules_points_and_top_labels() -> None:
    v = volcano_panel(top=6)
    note = v._over[-1].notes["volcano"]
    assert note["labelled"] == note["ranked"][:6]
    v.build()                           # labels are placed when built
    label_note = v._over[-1].notes["point_labels"]
    assert label_note["unresolved"] == []
    # Three dashed rules under the points: two at the fold threshold, one at p.
    rules = [n for n in v._under if "stroke-dasharray" in inklet.to_svg(n)]
    assert len(rules) == 3


def test_volcano_colours_names_and_no_thresholds() -> None:
    fold, p, _ = data()
    v = panel(60, 50, x=(-6, 6), y=(0, 16))
    v.volcano(fold, p, colors={"up": "#aa0000"}, names=("Down", None, "Up"),
              thresholds=False)
    assert v._under == []
    svg = inklet.to_svg(v.build())
    assert "#aa0000" in svg
    v.legend(side="right")
    text = inklet.to_svg(v.build())
    assert "Down" in text and "Up" in text
    with pytest.raises(DiagramError):
        v.volcano(fold, p, colors=("#000", "#111"))
    with pytest.raises(DiagramError):
        v.volcano(fold, p, names={"sig": "x"})
    with pytest.raises(DiagramError):
        v.volcano(fold, p, labels=["a"])
    with pytest.raises(DiagramError):
        panel(40, 40, x=["a", "b"], y=(0, 5)).volcano(fold, p)


def test_points_outside_the_area_are_not_labelled() -> None:
    fold = [5.0, 2.0, -2.0]
    p = [1e-40, 1e-4, 1e-3]
    v = panel(50, 40, x=(-4, 4), y=(0, 8))
    v.volcano(fold, p, labels=["far", "b", "c"], clip=True)
    assert v._over[-1].notes["volcano"]["labelled"] == [1, 2]


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


def test_volcano_lints_clean_exports_and_ink_stays_measured() -> None:
    v = volcano_panel(top=8, names=("Down", None, "Up"), size=0.8)
    v.axes(x="log2 fold change", y="-log10 p").legend(side="right")
    node = v.build()
    # Labels in a dense cloud may sit closer than 1 mm to an unlabelled point
    # (an info-level CROWDING); nothing may overlap.
    assert [d for d in lint(node) if d.severity != "info"] == []
    assert inklet.to_pdf(node)[:4] == b"%PDF"
    assert "<path" in inklet.to_svg(node) or "<circle" in inklet.to_svg(node)
    assert _ink_outside(node) == []
    fold, p, genes = data()
    spec = inklet.plot_spec(x=(-6, 6), y=(0, 16), height=50)
    spec.volcano(fold, p, labels=genes, top=5)
    doc = inklet.document(width=90)
    doc.add("volcano", spec)
    assert "G" in doc.compile().to_svg()
