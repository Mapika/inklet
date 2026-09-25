"""Categorical, composition, comparison and time plots: numbers and geometry.

waterfall, slope, bump, stem, likert, diverging_bars, pyramid, waffle,
mosaic, streamgraph, parallel, bullet, gantt, timeline, calendar and
barplot -- each read back from the resolved page, not from its own return
values.
"""

from __future__ import annotations

import datetime as dt
import math
import os
import subprocess
import sys
from pathlib import Path

import pytest

import inklet
from inklet import use_theme
from inklet.core import DiagramError, resolve
from inklet.diagnostics import lint
from inklet.draw.coords import as_drawn
from inklet.draw.shapes import MARK_KIND, MARK_LINE_KIND
from inklet.plot import (calendar_weeks, likert_spans, mosaic_layout, panel,
                         parallel_ranges, ranks, stream_layers, summary_stats,
                         unsigned, waffle_cells, waterfall_steps)


@pytest.fixture(autouse=True)
def _theme():
    use_theme("nature")


def placed(p, kind):
    return [x for x in resolve(as_drawn(p.build())).values()
            if x.diagram.kind == kind]


def note(p, key):
    for node in as_drawn(p.build()).walk():
        if key in node.notes:
            return node.notes[key]
    raise AssertionError(f"no {key} note")


def close(a, b, tol=1e-6):
    return math.isclose(a, b, abs_tol=tol)


# -- waterfall ---------------------------------------------------------------

def test_waterfall_steps_run_and_reset() -> None:
    steps = waterfall_steps([100, 20, -30, None, 5, 80], totals=[3, 5])
    assert [(s.start, s.end, s.kind) for s in steps] == [
        (0, 100, "increase"), (100, 120, "increase"), (120, 90, "decrease"),
        (0, 90, "total"), (90, 95, "increase"), (0, 80, "total")]
    assert steps[2].change == -30
    with pytest.raises(DiagramError):
        waterfall_steps([1, None, 2])
    with pytest.raises(DiagramError):
        waterfall_steps([1, 2], totals=[5])


def test_waterfall_bars_span_the_running_total() -> None:
    at = ["a", "b", "c", "end"]
    p = panel(40, 30, x=at, y=(0, 200))
    p.waterfall(at, [120, 45, -38, None], totals=["end"], connectors=False)
    bars = sorted(placed(p, MARK_KIND), key=lambda b: b.bbox.center.x)
    assert len(bars) == 4
    for bar, (lo, hi) in zip(bars, [(0, 120), (120, 165), (127, 165), (0, 127)]):
        assert close(bar.bbox.y1, p.y.map(lo), 1e-3)
        assert close(bar.bbox.y0, p.y.map(hi), 1e-3)


def test_waterfall_names_give_three_legend_entries() -> None:
    p = panel(40, 30, x=["a", "b", "t"], y=(0, 10))
    p.waterfall(["a", "b", "t"], [5, -2, None], totals=["t"],
                name=["up", "down", "total"])
    assert [k.name for k in p.keys] == ["up", "down", "total"]


# -- slope and bump ------------------------------------------------------------

def test_slope_lines_join_the_two_values() -> None:
    p = panel(24, 40, x=["2015", "2025"], y=(0, 100))
    p.slope({"A": [10, 60], "B": [50, 20]}, labels="none")
    lines = placed(p, MARK_LINE_KIND)
    assert len(lines) == 2
    spans = sorted((round(l.bbox.y0, 4), round(l.bbox.y1, 4)) for l in lines)
    want = sorted((round(p.y.map(hi), 4), round(p.y.map(lo), 4))
                  for lo, hi in [(10, 60), (20, 50)])
    assert spans == want


def test_ranks_break_ties_by_input_order_and_skip_missing() -> None:
    assert ranks({"a": [3, 1], "b": [3, None], "c": [1, 2]}) == {
        "a": [1, 2], "b": [2, None], "c": [3, 1]}
    assert ranks({"a": [3, 0], "b": [1, 2]}, descending=False) == {"a": [2, 1], "b": [1, 2]}


def test_bump_records_the_rank_table() -> None:
    p = panel(40, 30, x=["t1", "t2"], y=(3.5, 0.5))
    p.bump({"a": [1, 9], "b": [5, 5], "c": [9, 1]})
    table = note(p, "bump")["ranks"]
    assert dict(table) == {"a": [3, 1], "b": [2, 2], "c": [1, 3]} or \
        table == {"a": [3, 1], "b": [2, 2], "c": [1, 3]}


# -- stem --------------------------------------------------------------------------

def test_stem_draws_stems_from_the_baseline() -> None:
    p = panel(40, 30, x=(0, 4), y=(-2, 2))
    p.stem([(1, 1.5), (2, -1.0), (3, None)], baseline=0.0, rule=False)
    dots = placed(p, MARK_KIND)
    assert len(dots) == 2
    lines = sorted(placed(p, MARK_LINE_KIND), key=lambda l: l.bbox.center.x)
    assert len(lines) == 2
    assert close(lines[0].bbox.x0, p.x.map(1))
    assert close(lines[0].bbox.y1, p.y.map(0))
    assert close(lines[0].bbox.y0, p.y.map(1.5))
    assert close(lines[1].bbox.y1, p.y.map(-1.0))


# -- likert, diverging, pyramid ---------------------------------------------

def test_likert_spans_centre_the_neutral_level() -> None:
    [row] = likert_spans([[10, 20, 40, 20, 10]])
    assert row[2] == pytest.approx((-20.0, 20.0))
    assert row[0][0] == pytest.approx(-50.0)
    assert row[-1][1] == pytest.approx(50.0)
    [even] = likert_spans([[1, 1, 2, 0]])
    assert even[1][1] == pytest.approx(0.0)
    with pytest.raises(DiagramError):
        likert_spans([[1, 2, 3], [1, 2]])


def test_likert_draws_a_segment_per_nonzero_level() -> None:
    qs = ["q1", "q2"]
    p = panel(50, 20, x=(-100, 100), y=qs)
    p.likert(qs, [[1, 1, 2, 4, 2], [0, 5, 5, 0, 0]], name=list("abcde"))
    assert len(placed(p, MARK_KIND)) == 7
    assert [k.name for k in p.keys] == list("abcde")


def test_diverging_bars_go_left_and_right_of_zero() -> None:
    at = ["a", "b"]
    p = panel(40, 20, x=(-10, 10), y=at)
    p.diverging_bars(at, [3, 4], [5, 6], reference=(2, 3), zero=False)
    bars = placed(p, MARK_KIND)
    assert len(bars) == 4
    zero = p.x.map(0)
    lefts = [b for b in bars if b.bbox.center.x < zero]
    rights = [b for b in bars if b.bbox.center.x > zero]
    assert sorted(round(zero - b.bbox.x0, 4) for b in lefts) == \
        sorted(round(zero - p.x.map(-v), 4) for v in (3, 4))
    assert sorted(round(b.bbox.x1 - zero, 4) for b in rights) == \
        sorted(round(p.x.map(v) - zero, 4) for v in (5, 6))
    dashed = [l for l in placed(p, MARK_LINE_KIND)]
    xs = sorted(round(l.bbox.center.x, 4) for l in dashed)
    assert round(p.x.map(-2), 4) in xs and round(p.x.map(3), 4) in xs


def test_pyramid_is_diverging_bars_with_titles_and_unsigned_ticks() -> None:
    ages = ["0-9", "10-19"]
    p = panel(40, 20, x=(-8, 8), y=ages)
    p.pyramid(ages, [5, 4], [6, 3], titles=("Female", "Male"))
    assert len(placed(p, MARK_KIND)) == 4
    assert unsigned(-5) == "5" and unsigned(2.5) == "2.5"


# -- waffle and mosaic ------------------------------------------------------

def test_waffle_cells_largest_remainder() -> None:
    assert waffle_cells([1, 1, 1], 10) == [4, 3, 3]
    assert sum(waffle_cells([46, 31, 15, 8], 100)) == 100
    assert waffle_cells([30], 100, total=100) == [30]
    with pytest.raises(DiagramError):
        waffle_cells([60, 60], 100, total=100)


def test_waffle_draws_every_cell_square() -> None:
    p = panel(30, 20)
    p.waffle([3, 1], rows=4, columns=5, total=5)
    cells = placed(p, MARK_KIND)
    assert len(cells) == 20
    assert all(close(c.bbox.width, c.bbox.height) for c in cells)
    assert note(p, "waffle")["counts"] == (12, 4)


def test_mosaic_cell_areas_are_proportional_to_values() -> None:
    columns = mosaic_layout(["x", "y"], [[1, 3], [1, 1]])
    assert [c.end - c.start for c in columns] == pytest.approx([2 / 6, 4 / 6])
    assert [v for cell in columns[1].cells for v in cell] == pytest.approx([0, 0.75, 0.75, 1])
    p = panel(40, 40, x=(0, 1), y=(0, 1))
    p.mosaic(["x", "y"], [[1, 3], [1, 1]], gap=0, stroke_width=0,
             categories=False)
    areas = sorted(c.bbox.width * c.bbox.height for c in placed(p, MARK_KIND))
    unit = 40 * 40 / 6
    assert areas == pytest.approx(sorted(v * unit for v in (1, 3, 1, 1)), rel=1e-3)


# -- streamgraph ----------------------------------------------------------------

def test_stream_layers_stack_without_gaps() -> None:
    values = [[1, 2, 3], [2, 2, 2], [0, 1, 4]]
    for offset in ("wiggle", "silhouette", "zero", "expand"):
        layers = stream_layers(values, offset=offset)
        order = sorted(range(3), key=lambda s: layers[s][0][0])
        for a, b in zip(order, order[1:]):
            assert layers[a][1] == pytest.approx(layers[b][0])
    sil = stream_layers(values, offset="silhouette")
    for i in range(3):
        low = min(l[0][i] for l in sil)
        high = max(l[1][i] for l in sil)
        assert low == pytest.approx(-high)
    expand = stream_layers(values, offset="expand")
    assert max(l[1][2] for l in expand) == pytest.approx(1.0)


def test_streamgraph_legend_and_note() -> None:
    p = panel(50, 20, x=(0, 2), y=(-6, 6))
    p.streamgraph([0, 1, 2], [[1, 2, 3], [2, 2, 2]], name=["a", "b"])
    assert [k.name for k in p.keys] == ["a", "b"]
    assert note(p, "streamgraph")["offset"] == "wiggle"
    with pytest.raises(DiagramError):
        stream_layers([[1, -1]])


# -- parallel -------------------------------------------------------------------

def test_parallel_maps_each_value_on_its_own_axis() -> None:
    dims = ["a", "b"]
    p = panel(40, 30, x=dims)
    p.parallel([[0, 10], [5, 0]], ranges=[(0, 5), (0, 10)], groups=["g", "h"],
               labels=False)
    lines = placed(p, MARK_LINE_KIND)
    ends = sorted((round(l.bbox.y0, 4), round(l.bbox.y1, 4)) for l in lines
                  if close(l.bbox.width, p.x.map("b") - p.x.map("a"), 1e-3))
    area = p.area
    assert ends == sorted([(round(area.y0, 4), round(area.y1, 4))] * 2)
    assert [k.name for k in p.keys] == ["g", "h"]
    assert parallel_ranges([[1.2, 7], [3.8, 9]]) == [(1.0, 4.0), (7.0, 9.0)]


# -- bullet ------------------------------------------------------------------------

def test_bullet_measure_and_target() -> None:
    p = panel(60, 12, x=(0, 300), y=["r"])
    p.bullet(["r"], [270], targets=[250], ranges=[150, 225, 300])
    marks = placed(p, MARK_KIND)
    # three bands, a measure bar and the target
    assert len(marks) == 5
    measure = min(marks, key=lambda m: m.bbox.height if m.bbox.width > 5 else 99)
    assert close(measure.bbox.x1, p.x.map(270), 1e-3)
    target = min(marks, key=lambda m: m.bbox.width)
    assert close(target.bbox.center.x, p.x.map(250), 1e-3)


# -- gantt and timeline --------------------------------------------------------

def test_gantt_bars_run_from_start_to_end_and_milestones_are_diamonds() -> None:
    rows = ["b", "a"]
    p = panel(80, 20, x=("2025-01-01", "2025-03-01"), y=rows)
    p.gantt([("a", "2025-01-06", "2025-02-01"), ("b", "2025-02-10", "2025-02-10")],
            groups=["x", "y"])
    bars = placed(p, MARK_KIND)
    assert len(bars) == 2
    bar = max(bars, key=lambda b: b.bbox.width)
    assert close(bar.bbox.x0, p.x.map("2025-01-06"), 1e-3)
    assert close(bar.bbox.x1, p.x.map("2025-02-01"), 1e-3)
    diamond = min(bars, key=lambda b: b.bbox.width)
    assert close(diamond.bbox.center.x, p.x.map("2025-02-10"), 1e-3)
    assert [k.name for k in p.keys] == ["x", "y"]
    with pytest.raises(DiagramError):
        p.gantt([("a", "2025-02-01", "2025-01-01")])


def test_timeline_levels_keep_neighbouring_labels_apart() -> None:
    p = panel(80, 30, x=(0, 100))
    p.timeline([(10, "first long label"), (12, "second long label"),
                (14, "third long label"), (90, "far")])
    levels = note(p, "timeline")["levels"]
    assert 0 not in levels
    assert len(set(levels[:3])) == 3
    assert lint(as_drawn(p.build())) == []


# -- calendar ----------------------------------------------------------------------

def test_calendar_weeks_and_cells() -> None:
    assert calendar_weeks("2025-01-01", "2025-01-31") == 5
    assert calendar_weeks("2025-01-05", "2025-01-06", week_start="sunday") == 1
    p = panel(12, 16)
    p.calendar({dt.date(2025, 1, d): d for d in range(1, 15) if d != 3},
               start="2025-01-01", end="2025-01-14", labels=False)
    cells = placed(p, MARK_KIND)
    assert len(cells) == 14
    top = min(c.bbox.y0 for c in cells)
    # 1 Jan 2025 is a Wednesday: the first column starts on row 3.
    first = [c for c in cells if close(c.bbox.x0, min(x.bbox.x0 for x in cells))]
    assert len(first) == 5
    assert min(c.bbox.y0 for c in first) > top + 1
    assert p._ramp is not None


# -- barplot --------------------------------------------------------------------

def test_summary_stats() -> None:
    assert summary_stats([1, 2, 3]) == pytest.approx((2.0, 1 / math.sqrt(3), 1 / math.sqrt(3)))
    assert summary_stats([1, 2, 3], error="sd") == pytest.approx((2, 1, 1))
    assert summary_stats([1, 2, 3, 10], estimator="median", error=None) == (2.5, 0, 0)
    assert summary_stats([4], error="sem") == (4, 0, 0)
    assert summary_stats([1, 3], error=lambda v: (0.5, 1.5)) == (2, 0.5, 1.5)
    with pytest.raises(DiagramError):
        summary_stats([1], estimator="mode")


def test_barplot_bar_heights_points_and_error_bars() -> None:
    at = ["a", "b"]
    p = panel(30, 30, x=at, y=(0, 10))
    p.barplot(at, [[[2, 4, 6], [5, 5]], [[1, 3], [7, 8, 9]]], name=["s", "t"])
    marks = placed(p, MARK_KIND)
    assert len(marks) == 4 + 10
    bars = sorted((m for m in marks if m.bbox.width > 2), key=lambda m: m.bbox.center.x)
    assert [round(b.bbox.y0, 4) for b in bars] == \
        [round(p.y.map(v), 4) for v in (4, 2, 5, 8)]
    stats = note(p, "barplot")["stats"]
    assert stats[0][0][:1] == (4.0,) and stats[0][0][3] == 3
    assert [k.name for k in p.keys] == ["s", "t"]


# -- everything together ------------------------------------------------------

def _gallery() -> list:
    steps = ["s", "a", "b", "e"]
    w = panel(40, 25, x=steps, y=(0, 220))
    w.waterfall(steps, [100, 50, -30, None], totals=["e"], labels=True).axes()
    s = panel(20, 30, x=["x", "y"], y=(0, 100))
    s.slope({"A": [20, 60], "B": [70, 40]})
    st = panel(40, 25, x=(0, 10), y=(-1, 1))
    st.stem([(n, math.cos(n)) for n in range(10)]).axes()
    lk = panel(40, 16, x=(-100, 100), y=["q"])
    lk.likert(["q"], [[1, 2, 3, 2, 1]]).axis("bottom", format=unsigned)
    wf = panel(20, 20)
    wf.waffle([6, 4])
    ms = panel(40, 30, x=(0, 100), y=(0, 100))
    ms.mosaic(["a", "b"], [[3, 1], [1, 3]])
    sg = panel(40, 20, x=(0, 2), y=(-6, 6))
    sg.streamgraph([0, 1, 2], [[1, 2, 3], [2, 2, 2]])
    bl = panel(40, 10, x=(0, 10), y=["r"])
    bl.bullet(["r"], [7], targets=8, ranges=[5, 10]).axes()
    bp = panel(30, 30, x=["a", "b"], y=(0, 10))
    bp.barplot(["a", "b"], [[2, 4, 6], [5, 5, 6]]).axes()
    return [w, s, st, lk, wf, ms, sg, bl, bp]


def test_new_plots_lint_clean() -> None:
    for p in _gallery():
        node = as_drawn(p.build())
        assert [d for d in lint(node) if d.severity != "info"] == []


def test_new_plots_render_byte_identical_svg_in_fresh_processes() -> None:
    # Node ids are sequential per process, so identity is a property of a
    # fresh interpreter building the same thing.
    script = (
        "import sys; sys.path[:0] = [%r, %r]\n"
        "import inklet, test_plot_categorical as t\n"
        "from inklet.draw.coords import as_drawn\n"
        "inklet.use_theme('nature')\n"
        "sys.stdout.write(''.join(inklet.to_svg(as_drawn(p.build())) for p in t._gallery()))\n"
    ) % (str(Path(__file__).parent), str(Path(__file__).parents[1] / "src"))
    runs = [subprocess.run([sys.executable, "-c", script], capture_output=True,
                           text=True, check=True).stdout for _ in range(2)]
    assert runs[0] and runs[0] == runs[1]


def test_errors_are_diagram_errors() -> None:
    p = panel(40, 30, x=["a"], y=(0, 10))
    with pytest.raises(DiagramError):
        p.barplot(["a", "b"], [[1, 2]])
    with pytest.raises(DiagramError):
        p.waffle([-1, 2])
    with pytest.raises(DiagramError):
        p.likert(["a"], [[1, -2, 3]])
    with pytest.raises(DiagramError):
        p.gantt([("a", 1)])


def test_the_example_page_lints_without_errors_or_warnings(tmp_path) -> None:
    root = Path(__file__).parents[1]
    (tmp_path/"examples").mkdir()
    result = subprocess.run(
        [sys.executable, str(root/"examples/categorical_plot_types.py")],
        cwd=tmp_path, capture_output=True, text=True, check=True,
        env={**os.environ, "PYTHONPATH": str(root/"src")})
    assert "ERROR" not in result.stdout and "WARNING" not in result.stdout
    assert (tmp_path/"examples/categorical_plot_types.svg").exists()
