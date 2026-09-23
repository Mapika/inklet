"""Panel.bars(labels=): value labels on bars and stacked segments.

Each label is read back from the built panel and compared with the rectangle
it names: inside labels must sit wholly inside their rectangle, end labels
just past the free end, and a stacked segment too small for its label must be
left out and listed in the note rather than drawn over its neighbour.
"""

from __future__ import annotations

import pytest

import inklet
from inklet import use_theme
from inklet.core import DiagramError, resolve
from inklet.diagnostics import lint
from inklet.draw.coords import active_theme, as_drawn
from inklet.draw.shapes import MARK_KIND
from inklet.plot import panel
from inklet.plot.bar_labels import BAR_LABEL_KIND, label_texts


@pytest.fixture(autouse=True)
def _theme():
    use_theme("nature")


def labels(p):
    """`(text, bbox, text_fill)` of each bar label."""
    out = []
    for placed in resolve(as_drawn(p.build())).values():
        prim = placed.diagram.prim
        if placed.diagram.kind == BAR_LABEL_KIND and getattr(prim, "text", None):
            out.append((prim.text, placed.bbox, placed.style.text_fill))
    return out


def bars_of(p):
    return [placed.bbox for placed in resolve(as_drawn(p.build())).values()
            if placed.diagram.kind == MARK_KIND]


def notes_of(p):
    for node in p._over:
        if "bar_labels" in node.notes:
            return node.notes["bar_labels"]
    raise AssertionError("no bar label node")


def inside(inner, outer, eps=1e-6) -> bool:
    return (inner.x0 >= outer.x0 - eps and inner.x1 <= outer.x1 + eps
            and inner.y0 >= outer.y0 - eps and inner.y1 <= outer.y1 + eps)


def test_label_texts_spellings() -> None:
    series = [[1.0, 2.5]]
    assert label_texts(True, series) == [["1", "2.5"]]
    assert label_texts("{:.1f}%", series) == [["1.0%", "2.5%"]]
    assert label_texts(lambda v: f"n={v:g}", series) == [["n=1", "n=2.5"]]
    assert label_texts(["a", None], series) == [["a", None]]
    with pytest.raises(DiagramError):
        label_texts("plain", series)
    with pytest.raises(DiagramError):
        label_texts(["a"], series)


def test_tall_bars_get_labels_inside_short_ones_at_the_end() -> None:
    p = panel(40, 30, x=["a", "b"], y=(0, 100))
    p.bars(["a", "b"], [90, 3], labels=True)
    found = {text: box for text, box, _ in labels(p)}
    rects = sorted(bars_of(p), key=lambda b: b.x0)
    assert inside(found["90"], rects[0])
    # The short bar's label sits above its top, not over it.
    assert found["3"].y1 <= rects[1].y0
    assert rects[1].x0 <= found["3"].center.x <= rects[1].x1


def test_inside_label_colour_follows_contrast() -> None:
    p = panel(40, 30, x=["a", "b"], y=(0, 10))
    p.bars(["a", "b"], [9, 9], bar_colors=["#000000", "#f0f0f0"], labels=True)
    fills = [fill for _, _, fill in sorted(labels(p), key=lambda t: t[1].x0)]
    theme = active_theme()
    assert fills == [theme.paper, theme.ink]


def test_negative_bar_label_goes_below() -> None:
    p = panel(40, 30, x=["a"], y=(-10, 10))
    p.bars(["a"], [-1], labels=True)
    (text, box, _), = labels(p)
    rect, = bars_of(p)
    assert box.y0 >= rect.y1


def test_stacked_small_segment_is_omitted_and_noted() -> None:
    p = panel(40, 30, x=(0, 100), y=["x"])
    p.bars(["x"], [[60], [1], [39]], stacked=True, orient="h", labels=True)
    written = sorted(text for text, _, _ in labels(p))
    assert written == ["39", "60"]
    note = notes_of(p)
    assert note["drawn"] == 2
    assert note["omitted"] == [{"category": "x", "series": 1, "text": "1"}]


def test_stacked_end_labels_only_the_stack_tip() -> None:
    p = panel(40, 30, x=["a"], y=(0, 20))
    p.bars(["a"], [[5], [7]], stacked=True, labels=[[None], ["12"]],
           label_position="end")
    (text, box, _), = labels(p)
    top = min(b.y0 for b in bars_of(p))
    assert text == "12" and box.y1 <= top


def test_horizontal_inside_label_fits_its_bar() -> None:
    p = panel(50, 20, x=(0, 10), y=["a", "b"])
    p.bars(["a", "b"], [8, 6], orient="h", labels="{:.0f} cells")
    rects = bars_of(p)
    for text, box, _ in labels(p):
        assert any(inside(box, r) for r in rects), text


def test_unknown_option_and_position_are_refused() -> None:
    p = panel(40, 30, x=["a"], y=(0, 10))
    with pytest.raises(DiagramError):
        p.bars(["a"], [5], labels=True, label_position="middle")
    with pytest.raises(DiagramError):
        p.bars(["a"], [5], labels=True, label_options={"colour": "red"})


def test_labelled_bars_lint_clean_and_export() -> None:
    p = panel(40, 30, x=["a", "b", "c"], y=(0, 60))
    p.bars(["a", "b", "c"], [12, 55, 30], labels=True).axes()
    node = p.build()
    assert lint(node) == []
    svg = inklet.to_svg(node)
    assert "55" in svg or "<path" in svg
    assert inklet.to_pdf(node)[:4] == b"%PDF"
