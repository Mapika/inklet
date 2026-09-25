"""Panel.dotplot, Panel.size_key and plot.area_scale."""

from __future__ import annotations

import io
import math

import pytest

import inklet
from inklet import use_theme
from inklet.core import DiagramError, resolve
from inklet.diagnostics import lint
from inklet.draw.coords import as_drawn
from inklet.draw.shapes import MARK_KIND, MARK_LINE_KIND
from inklet.plot import area_scale, dendrogram_layout, panel, size_key
from inklet.plot.ramp import DIVERGING, SEQUENTIAL


@pytest.fixture(autouse=True)
def _theme():
    use_theme("nature")


GENES = ["a", "b", "c"]
GROUPS = ["g1", "g2"]
SIZES = [[0.25, 1.0, 0.0], [0.5, None, 0.81]]
COLOURS = [[0.1, 0.9, 0.4], [0.3, 0.7, float("nan")]]


def dots(p):
    return [x for x in resolve(as_drawn(p.build())).values()
            if x.diagram.kind == MARK_KIND]


def test_area_scale_is_proportional_to_value() -> None:
    sizes = area_scale(1.0, 4)
    assert sizes(1.0) == pytest.approx(4)
    assert sizes(0.25) == pytest.approx(2)
    assert sizes(0.0) == 0
    assert sizes(0.5) ** 2 == pytest.approx(sizes(1.0) ** 2 / 2)
    with pytest.raises(DiagramError):
        sizes(-0.1)
    with pytest.raises(DiagramError, match="top"):
        sizes(1.2)
    with pytest.raises(DiagramError):
        area_scale(0, 3)
    assert area_scale(0.99, 3).ticks() == (0.2, 0.4, 0.6, 0.8)
    assert area_scale(100, 3).ticks() in ((20, 60, 100), (25, 50, 75, 100))
    assert len(area_scale(7, 3).ticks()) >= 3


def test_circles_encode_area_and_missing_and_zero_draw_nothing() -> None:
    p = panel(30, 20, x=GENES, y=GROUPS)
    p.dotplot(SIZES, COLOURS, diameter=4)
    drawn = dots(p)
    # (g1, c) is zero, (g2, b) has no size and (g2, c) no colour.
    assert len(drawn) == 3
    by_place = {(round(d.bbox.center.x, 6), round(d.bbox.center.y, 6)): d.bbox.width
                for d in drawn}
    full = by_place[(round(p.x.map("b"), 6), round(p.y.map("g1"), 6))]
    quarter = by_place[(round(p.x.map("a"), 6), round(p.y.map("g1"), 6))]
    half = by_place[(round(p.x.map("a"), 6), round(p.y.map("g2"), 6))]
    assert full == pytest.approx(4, abs=1e-6)
    assert quarter == pytest.approx(2, abs=1e-6)
    assert half ** 2 == pytest.approx(8, abs=1e-6)
    note = p._content[-1].notes["dotplot"]
    assert note["missing"] == [(1, 1), (1, 2)]
    assert note["empty"] == [(0, 2)]
    assert note["top"] == 1.0 and note["diameter"] == 4


def test_default_diameter_fits_the_band_and_colours_use_matrix_ramps() -> None:
    p = panel(30, 20, x=GENES, y=GROUPS)
    p.dotplot(SIZES, COLOURS)
    step = min(abs(p.x.step), abs(p.y.step))
    assert p._sizes.diameter == pytest.approx(0.9 * step)
    assert p._ramp is SEQUENTIAL
    assert p._scale_domain.domain == (0.1, 0.9)
    crossing = panel(30, 20, x=GENES, y=GROUPS)
    crossing.dotplot(SIZES, [[-1, 1, 0], [0.5, -0.5, 1]])
    assert crossing._ramp is DIVERGING
    grey = panel(30, 20, x=GENES, y=GROUPS)
    grey.dotplot(SIZES, color="#336699")
    assert grey._ramp is None
    assert {d.diagram.style.fill for d in dots(grey)} == {"#336699"}


def test_colorbar_and_size_key_explain_the_dots_and_lint_clean() -> None:
    p = panel(30, 20, x=GENES, y=GROUPS)
    p.dotplot(SIZES, COLOURS)
    p.axes()
    p.colorbar(label="mean", length=14).size_key(title="fraction", format="{:.0%}")
    key = p._over[-1]
    found = [n for n in resolve(as_drawn(key)).values() if "size_key" in n.diagram.notes]
    note = found[0].diagram.notes["size_key"]
    assert note["values"] == (0.2, 0.6, 1.0)
    assert note["diameters"] == tuple(p._sizes(v) for v in note["values"])
    assert key.bbox.x0 > p._over[-2].bbox.x0     # beyond the colorbar
    svg = inklet.to_svg(p.build())
    assert "fraction" in svg
    assert lint(p.build()) == []


def test_size_key_for_a_scatter_and_both_orientations() -> None:
    sizes = area_scale(500, 3)
    p = panel(40, 30, x=(0, 10), y=(0, 10))
    counts = [50, 200, 500]
    p.scatter([(2, 2), (5, 5), (8, 8)], size=[sizes(v) for v in counts])
    p.axes()
    p.size_key(sizes, side="bottom")
    row = p._over[-1]
    assert row.bbox.width > row.bbox.height
    assert row.bbox.y0 > p.area.y1
    column = size_key(sizes, values=[100, 500])
    assert column.notes["size_key"]["values"] == (100.0, 500.0)
    assert column.bbox.height > column.bbox.width * 0.5
    with pytest.raises(DiagramError):
        size_key(sizes, values=[0, 100])
    with pytest.raises(DiagramError):
        size_key(sizes, orient="x")
    with pytest.raises(DiagramError, match="dotplot"):
        panel(40, 30, x=(0, 10), y=(0, 10)).size_key()
    inside = panel(40, 30, x=(0, 10), y=(0, 10))
    inside.size_key(sizes, corner="ne", plate=True)
    box = inside._over[-1].bbox
    assert inside.area.x0 <= box.x0 and box.x1 <= inside.area.x1


def test_dots_line_up_with_a_dendrogram_on_the_same_band() -> None:
    link = [[0, 1, 1.0, 2], [2, 3, 1.5, 2], [4, 5, 3.0, 4]]
    names = ["T", "NK", "B", "Mono"]
    order = list(dendrogram_layout(link, labels=names).leaves)
    tree = panel(10, 24, x=(3, 0), y=order)
    tree.dendrogram(link, labels=names, orient="h")
    grid = panel(18, 24, x=GENES, y=order)
    grid.dotplot([[0.5, 1, 0.2]] * 4)
    leaves = sorted({round(n.bbox.y0, 6) for n in resolve(as_drawn(tree.build())).values()
                     if n.diagram.kind == MARK_LINE_KIND} |
                    {round(n.bbox.y1, 6) for n in resolve(as_drawn(tree.build())).values()
                     if n.diagram.kind == MARK_LINE_KIND})
    centres = sorted({round(d.bbox.center.y, 6) for d in dots(grid)})
    assert set(centres) <= set(leaves)
    assert len(centres) == 4
    # In a row, the areas share their vertical extent, so the rows stay aligned.
    both = inklet.row([tree, grid], gap=1)
    assert lint(both) == []


def test_dotplot_errors() -> None:
    p = panel(30, 20, x=GENES, y=GROUPS)
    with pytest.raises(DiagramError):
        p.dotplot([[1, 2, 3]])                       # one row, two categories
    with pytest.raises(DiagramError):
        p.dotplot(SIZES, [[1, 2, 3]])
    with pytest.raises(DiagramError):
        p.dotplot([[1, -2, 3], [1, 1, 1]])
    with pytest.raises(DiagramError):
        p.dotplot([[None, None, None], [None, None, None]])
    with pytest.raises(DiagramError, match="top"):
        p.dotplot([[1, 2, 3], [1, 1, 1]], top=2)
    with pytest.raises(DiagramError, match="band"):
        panel(30, 20, x=(0, 3), y=GROUPS).dotplot(SIZES)
    numeric = panel(30, 20, x=(0, 4), y=GROUPS)
    numeric.dotplot(SIZES, x=[1, 2, 3])
    assert len(dots(numeric)) == 4


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


def test_renders_and_builds_in_a_document() -> None:
    p = panel(30, 20, x=GENES, y=GROUPS)
    p.dotplot(SIZES, COLOURS).axes().colorbar(length=12).size_key()
    node = p.build()
    assert inklet.to_pdf(node)[:4] == b"%PDF"
    assert _ink_outside(node) == []
    spec = inklet.plot_spec(x=GENES, y=GROUPS, height=20)
    spec.dotplot(SIZES, COLOURS)
    spec.size_key(title="fraction")
    doc = inklet.document(width=80)
    doc.add("dots", spec)
    assert "<ellipse" in doc.compile().to_svg() or "<circle" in doc.compile().to_svg()
    assert not math.isnan(p._sizes.top)
