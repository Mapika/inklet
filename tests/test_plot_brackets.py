"""Panel.brackets and plot.format_p."""

from __future__ import annotations

import pytest

import inklet
from inklet import use_theme
from inklet.core import DiagramError
from inklet.diagnostics import lint
from inklet.draw.coords import as_drawn
from inklet.plot import format_p, panel

GROUPS = ["wt", "het", "ko", "rescue"]
VALUES = {"wt": [2.8, 3.1, 3.3], "het": [3.2, 3.5, 3.4], "ko": [4.9, 5.2, 5.0],
          "rescue": [3.4, 3.6, 3.7]}


@pytest.fixture(autouse=True)
def _theme():
    use_theme("nature")


def test_format_p() -> None:
    assert [format_p(p) for p in (5e-5, 5e-4, 5e-3, 0.04, 0.05, 1)] == \
        ["****", "***", "**", "*", "ns", "ns"]
    assert format_p(0.0123, "p") == "//P// = 0.012"
    assert format_p(0.21, "p") == "//P// = 0.21"
    assert format_p(0.0004, "p") == "//P// < 0.001"
    assert format_p(0.0004, "p", smallest=1e-4, prefix="p = ") == "p = 0.00040"
    assert format_p(0.03, lambda p: f"{p:.0%}") == "3%"
    assert format_p(0.2, stars=((0.5, "+"),)) == "+"
    for bad in (-0.1, 1.5, float("nan"), "0.1", True):
        with pytest.raises(DiagramError):
            format_p(bad)
    with pytest.raises(DiagramError):
        format_p(0.1, "words")


def brackets_panel(comparisons, **kwargs):
    p = panel(40, 36, x=GROUPS, y=(0, 9))
    p.swarm(VALUES)
    p.brackets(comparisons, **kwargs)
    return p


def boxes(p):
    return [as_drawn(b).bbox for b in p._brackets]


def test_shortest_spans_lowest_and_nothing_overlaps() -> None:
    p = brackets_panel([("wt", "rescue", 0.03), ("wt", "ko", 3e-5),
                        ("wt", "het", 0.21), ("ko", "rescue", 8e-4)])
    note = p._over[-1].notes["brackets"]
    assert [(a, b) for a, b, _ in note] == [("wt", "het"), ("ko", "rescue"),
                                           ("wt", "ko"), ("wt", "rescue")]
    assert [t for _, _, t in note] == ["ns", "***", "****", "*"]
    found = [b for b in (x.bbox for x in p._brackets)]
    for i, a in enumerate(found):
        for b in found[i + 1:]:
            assert (min(a.x1, b.x1) <= max(a.x0, b.x0) + 1e-6
                    or min(a.y1, b.y1) <= max(a.y0, b.y0) + 1e-6)
    # Disjoint spans each sit just over their own data.
    assert found[0].y1 > found[1].y1
    # Each longer span is above the ones it covers, and at the shared end
    # (ko) its 1 mm tick stops 1 mm above the line of the bracket below.
    assert found[2].y1 < found[0].y0 + 1e-6
    assert found[2].y1 == pytest.approx(found[1].y1 - 1.0 - 1.0, abs=1e-6)
    assert found[3].y1 < found[2].y0 + 1e-6


def test_hide_ns_text_and_p_format() -> None:
    p = brackets_panel([("wt", "het", 0.21), ("wt", "ko", 0.002),
                        ("het", "ko", "n.s. by design")], hide_ns=True, format="p")
    note = p._over[-1].notes["brackets"]
    # A number at or above the largest star bound is hidden, text is not.
    assert [t for _, _, t in note] == ["n.s. by design", "//P// = 0.0020"]
    with pytest.raises(DiagramError):
        brackets_panel([("wt", "het")])


def test_brackets_lint_clean_and_replay_in_a_spec() -> None:
    p = brackets_panel([("wt", "het", 0.21), ("het", "ko", 0.004),
                        ("wt", "ko", 3e-5)])
    p.axes(y="response")
    assert lint(p.build()) == []
    spec = inklet.plot_spec(x=GROUPS, y=(0, 9), height=36)
    # Recorded before the marks, drawn after them.
    spec.brackets([("wt", "ko", 0.0005)])
    spec.swarm(VALUES)
    doc = inklet.document(width=80)
    doc.add("sig", spec)
    assert "***" in doc.compile().to_svg()
