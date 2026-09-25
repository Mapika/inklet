"""Panel.raincloud."""

from __future__ import annotations

import io
import random
import re

import pytest

import inklet
from inklet import use_theme
from inklet.core import DiagramError, resolve
from inklet.diagnostics import lint
from inklet.draw.coords import as_drawn
from inklet.draw.shapes import MARK_KIND
from inklet.plot import panel
from inklet.plot.raincloud import _cloud, raincloud
from inklet.themes import contrast_ratio


@pytest.fixture(autouse=True)
def _theme():
    use_theme("nature")


def samples(seed: int = 5) -> dict[str, list[float]]:
    rng = random.Random(seed)
    return {"control": [rng.gauss(4, 0.6) for _ in range(50)],
            "treated": [rng.gauss(5, 0.8) for _ in range(40)]}


def placed(p):
    return list(resolve(as_drawn(p.build())).values())


def rain_panel(**kwargs):
    p = panel(50, 36, x=(0, 8), y=["treated", "control"])
    p.raincloud(samples(), **kwargs)
    return p


def marks(p):
    return [x for x in placed(p) if x.diagram.kind == MARK_KIND]


def test_cloud_rises_from_the_centre_line_and_rain_falls_below() -> None:
    p = rain_panel(box=False)
    step = abs(p.y.step)
    found = marks(p)
    assert len(found) == 2 + 90
    for name in ("control", "treated"):
        centre = p.y.map(name)
        cloud = [c for c in found if abs(c.bbox.y1 - centre) < 1e-6]
        assert len(cloud) == 1
        # The cloud peak reaches most of the way to the slot edge.
        assert cloud[0].bbox.height == pytest.approx(0.95 * 0.45 * step, rel=1e-3)
        # The rain lies below the centre line, inside the slot.
        dots = [c for c in found if c.bbox.height < 1 and
                centre < c.bbox.y0 and c.bbox.y1 < centre + 0.45 * step]
        assert len(dots) == len(samples()[name])
    note = p._content[-1].notes["raincloud"]
    assert note["drawn"] == [0, 1] and note["empty"] == []


def test_vertical_rainclouds_put_the_cloud_on_the_right() -> None:
    p = panel(40, 40, x=["control", "treated"], y=(0, 8))
    p.raincloud(samples(), orient="v", points=None, box=False)
    clouds = sorted(marks(p), key=lambda c: c.bbox.x0)
    for cloud, name in zip(clouds, ("control", "treated")):
        assert cloud.bbox.x0 == pytest.approx(p.x.map(name), abs=1e-6)
        assert cloud.bbox.x1 > p.x.map(name) + 5


def test_box_marks_quartiles_and_median() -> None:
    from inklet.plot.statistics import box_stats

    data = samples()["control"]
    p = panel(50, 36, x=(0, 8), y=["control"])
    p.raincloud({"control": data}, points=None)
    stats = box_stats(data)
    width = p.x.map(stats.q3) - p.x.map(stats.q1)
    boxes = [c for c in marks(p) if c.bbox.width == pytest.approx(width, abs=1e-6)]
    assert len(boxes) == 1
    assert boxes[0].bbox.y0 > p.y.map("control")


def test_swarm_rain_and_seeded_jitter_are_repeatable() -> None:
    def svg(**kwargs):
        return re.sub(r'id="[^"]*"', "", inklet.to_svg(rain_panel(**kwargs).build()))

    assert svg(seed=4) == svg(seed=4)
    assert svg(seed=4) != svg(seed=5)
    swarm = rain_panel(points="swarm")
    assert swarm._content[-1].notes["raincloud"]["drawn"] == [0, 1]
    assert len(marks(swarm)) == 2 + 2 + 90
    bare = rain_panel(points=None, box=False)
    assert len(marks(bare)) == 2


def test_dark_colours_give_a_pale_cloud() -> None:
    assert contrast_ratio(_cloud("#000000", "#ffffff"), "#ffffff") <= 3.0
    pale = _cloud("#24698c", "#ffffff")
    assert contrast_ratio(pale, "#ffffff") <= 3.0


def test_raincloud_errors_and_empty_groups() -> None:
    with pytest.raises(DiagramError):
        rain_panel(points="dots")
    with pytest.raises(DiagramError):
        rain_panel(samples=2)
    with pytest.raises(DiagramError):
        rain_panel(size=0)
    p = panel(50, 36, x=(0, 8), y=["b", "a"])
    node, _, note = raincloud(p, {"a": [1.0, 2.0, 3.0], "b": []})
    assert note["empty"] == [1] and note["drawn"] == [0]


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


def test_raincloud_lints_clean_exports_and_ink_stays_measured() -> None:
    across = rain_panel(color=["#24698c", "#288675"])
    across.axes(x="Measurement / a.u.")
    upright = panel(40, 40, x=["control", "treated"], y=(0, 8))
    upright.raincloud(samples(), orient="v", points="swarm")
    upright.axes(y="Measurement / a.u.")
    for p in (across, upright):
        node = p.build()
        assert lint(node) == []
        assert inklet.to_pdf(node)[:4] == b"%PDF"
        assert "<path" in inklet.to_svg(node)
        assert _ink_outside(node) == []
    spec = inklet.plot_spec(x=(0, 8), y=["treated", "control"], height=36)
    spec.raincloud(samples())
    doc = inklet.document(width=80)
    doc.add("rain", spec)
    assert "<path" in doc.compile().to_svg()
