"""The joint label search and what is built on it.

`layout.label_search` places point labels, curve labels, keys and (with
`method="joint"`) annotate callouts. These tests hold it to the benchmark in
`tools/benchmark_labels.py`: no overlaps on the dense cases, the same bytes
every time, and a runtime budget.
"""
from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest

import inklet
from inklet.core import DiagramError, Rect
from inklet.layout.label_search import (Candidate, emptiest, field_of, solve,
                                        stack)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import benchmark_labels as bench  # noqa: E402


@pytest.fixture(autouse=True)
def nature():
    inklet.use_theme("nature")
    yield


def texts_of(root, kind):
    from inklet.core import resolve
    places = resolve(root)
    out = {}
    for node in root.walk():
        if node.kind == kind and type(node.prim).__name__ == "TextPrim":
            out[node.prim.text] = places[node.id].bbox
    return out


# -- the benchmark ----------------------------------------------------------

CLEAN = ["scatter_60", "volcano_30", "curves_10", "curves_inside_5",
         "bars_areas_12", "callouts_34"]


@pytest.mark.parametrize("case", CLEAN)
def test_benchmark_case_has_no_overlaps_or_crossings(case):
    result = bench.run(case)
    assert result["label_label"] == 0
    assert result["leader_cross"] == 0
    assert result["label_text"] == 0
    assert result["unresolved"] == 0
    assert result["legend_cover"] == 0
    assert result["lint_codes"].get("LABEL_UNPLACED", 0) == 0


def test_runtime_budget():
    """Sixty labels in a clustered cloud of 420 points; the old placer took
    about 100 s on this case."""
    start = time.perf_counter()
    bench.run("scatter_60")
    assert time.perf_counter() - start < 20.0
    start = time.perf_counter()
    bench.run("volcano_30")
    assert time.perf_counter() - start < 8.0


def stable(svg: str) -> str:
    """The SVG without node ids, which count up across a process."""
    return re.sub(r'(id="|#)([A-Za-z_-]+)\d+', r"\1\2", svg)


def _svg(case):
    made, _ = bench.CASES[case](False)
    built = made.build() if hasattr(made, "build") else made
    return stable(inklet.to_svg(built))


@pytest.mark.parametrize("case", ["scatter_60", "curves_inside_5",
                                  "bars_areas_12", "callouts_34"])
def test_same_input_gives_the_same_bytes(case):
    assert _svg(case) == _svg(case)


def test_same_bytes_in_a_fresh_process_with_another_hash_seed():
    """Seeds come from content through sha256, not `hash()`, so another
    process with another PYTHONHASHSEED writes the same file."""
    code = ("import sys, hashlib; sys.path[:0] = [sys.argv[1], sys.argv[2]];"
            "import test_label_search as t, inklet;"
            "print(hashlib.sha256(t._svg('volcano_30').encode()).hexdigest())")
    digests = set()
    for seed in ("1", "2"):
        env = {**os.environ, "PYTHONHASHSEED": seed}
        done = subprocess.run(
            [sys.executable, "-c", code, str(ROOT / "src"), str(ROOT / "tests")],
            capture_output=True, text=True, env=env, check=True)
        digests.add(done.stdout.strip())
    digests.add(hashlib.sha256(_svg("volcano_30").encode()).hexdigest())
    assert len(digests) == 1


# -- the engine -------------------------------------------------------------


def test_solve_separates_two_labels_competing_for_one_spot():
    shared = (0.0, 0.0, 4.0, 2.0)
    elsewhere = (0.0, 5.0, 4.0, 7.0)
    options = [[Candidate(shared, None, 0.0), Candidate(elsewhere, None, 1.0)],
               [Candidate(shared, None, 0.0), Candidate(elsewhere, None, 1.0)]]
    solution = solve(options, spacing=1.0)
    assert sorted(solution.chosen) == [0, 1]
    assert solution.conflicted == ()


def test_solve_reports_labels_it_cannot_separate():
    only = (0.0, 0.0, 4.0, 2.0)
    options = [[Candidate(only, None, 0.0)], [Candidate(only, None, 0.0)]]
    assert solve(options, spacing=1.0).conflicted == (0, 1)


def test_solve_uncrosses_leaders():
    # Two points side by side, each with a label diagonally across the
    # other's: the crossing assignment is cheaper by distance alone.
    a = [Candidate((6, -6, 9, -4), (0, 0, 6, -4), 0.0),
         Candidate((-3, -6, 0, -4), (0, 0, 0, -4), 0.5)]
    b = [Candidate((-3, -6, 0, -4), (5, 0, 0, -4), 0.0),
         Candidate((6, -6, 9, -4), (5, 0, 6, -4), 0.5)]
    solution = solve([a, b], spacing=0.5)
    assert solution.conflicted == ()
    assert solution.chosen == (1, 1)


def test_stack_keeps_order_and_gap_and_moves_least():
    centres = stack([10.0, 10.2, 30.0], [2.0, 2.0, 2.0], gap=1.0,
                    top=0.0, bottom=50.0)
    assert centres[0] < centres[1] < centres[2]
    assert centres[1] - centres[0] == pytest.approx(3.0)
    assert (centres[0] + centres[1]) / 2 == pytest.approx(10.1)
    assert centres[2] == pytest.approx(30.0)


def test_stack_overflows_rather_than_overlapping():
    centres = stack([5.0] * 6, [2.0] * 6, gap=1.0, top=0.0, bottom=10.0)
    ordered = sorted(centres)
    assert all(b - a >= 3.0 - 1e-9 for a, b in zip(ordered, ordered[1:]))


def test_emptiest_finds_the_empty_quadrant():
    p = inklet.plot.panel(60, 40, x=(0, 10), y=(0, 10))
    p.scatter([(x / 2, y / 2) for x in range(21) for y in range(21)
               if not (x > 12 and y < 8)], size=0.8)
    area = p.area
    box, _, clean = emptiest(10, 6, area, field_of(p._content), pad=1.0)
    assert clean
    lower_right = p.point(10, 0)
    assert box.center.x > area.center.x and box.center.y > area.center.y
    assert abs(box.x1 - lower_right.x) < 6


# -- label_lines ------------------------------------------------------------


def curves_panel(n=6):
    p = inklet.plot.panel(70, 45, x=(0, 10), y=(0, 10))
    for name, pts in bench.curves()[:n]:
        p.line(pts, name=name, stroke_width=0.3)
    p.axes(x="Time (s)", y="Response")
    return p


def test_label_lines_names_every_curve_at_its_end_without_overlap():
    p = curves_panel()
    p.label_lines()
    built = p.build()
    boxes = texts_of(built, "line-label")
    assert sorted(boxes) == sorted(n for n, _ in bench.curves()[:6])
    ordered = sorted(boxes.values(), key=lambda b: b.y0)
    for a, b in zip(ordered, ordered[1:]):
        assert b.y0 >= a.y1 + 0.99      # the theme's xs gap
    assert all(b.x0 > p.area.x1 for b in boxes.values())
    note = next(n.notes["line_labels"] for n in built.walk()
                if "line_labels" in n.notes)
    assert note["unresolved"] == [] and note["where"] == "end"


def test_label_lines_draws_leaders_only_when_names_move():
    p = inklet.plot.panel(60, 40, x=(0, 10), y=(0, 10))
    p.line([(0, 1), (10, 2)], name="low")
    p.line([(0, 9), (10, 8)], name="high")
    p.label_lines()
    built = p.build()
    assert not [n for n in built.walk() if n.kind == "label-leader"]
    q = inklet.plot.panel(60, 40, x=(0, 10), y=(0, 10))
    q.line([(0, 1), (10, 5.0)], name="one")
    q.line([(0, 9), (10, 5.1)], name="two")
    q.label_lines()
    built = q.build()
    assert len([n for n in built.walk() if n.kind == "label-leader"]) == 2


def test_label_lines_colours_names_legibly():
    p = inklet.plot.panel(60, 40, x=(0, 10), y=(0, 10))
    p.line([(0, 1), (10, 2)], name="pale", stroke="#f0e442")
    p.label_lines()
    assert inklet.lint(p.build(), rules=["LOW_CONTRAST"]) == []


def test_label_lines_inside_keeps_names_off_curves_and_each_other():
    result = bench.run("curves_inside_5")
    assert result["label_mark"] == 0 and result["label_label"] == 0


def test_label_lines_errors():
    p = curves_panel(2)
    p.label_lines(["nope"])
    with pytest.raises(DiagramError, match="nope"):
        p.build()
    q = inklet.plot.panel(40, 30, x=(0, 1), y=(0, 1))
    q.line([(0, 0), (1, 1)])
    q.label_lines()
    with pytest.raises(DiagramError, match="no named curves"):
        q.build()
    with pytest.raises(ValueError):
        r = curves_panel(2)
        r.label_lines(where="middle")
        r.build()


def test_label_lines_sees_curves_drawn_after_the_call():
    p = inklet.plot.panel(60, 40, x=(0, 10), y=(0, 10))
    p.label_lines()
    p.step([(0, 1), (5, 3), (10, 4)], name="late")
    boxes = texts_of(p.build(), "line-label")
    assert list(boxes) == ["late"]


# -- legend(corner="best") --------------------------------------------------


def test_best_legend_avoids_the_data():
    result = bench.run("bars_areas_12")
    assert result["legend_cover"] == 0


def test_best_legend_goes_outside_when_the_plot_is_full():
    def legend_box(**kwargs):
        p = inklet.plot.panel(40, 30, x=(0, 10), y=(0, 10))
        p.scatter([(x / 2, y / 2) for x in range(21) for y in range(21)],
                  size=1.2, name="dense")
        p.legend(**kwargs)
        built = p.build()
        legend = next(n for n in built.walk() if n.kind == "legend")
        return inklet.core.resolve(built)[legend.id].bbox
    assert legend_box(corner="best") == legend_box(side="right")


def test_fixed_corners_are_unchanged():
    def svg(corner):
        p = inklet.plot.panel(40, 30, x=(0, 10), y=(0, 10))
        p.line([(0, 0), (10, 10)], name="a")
        p.legend(corner=corner)
        return inklet.to_svg(p.build())
    assert svg("ne") != svg("sw")


# -- graceful failure -------------------------------------------------------


def test_unplaceable_labels_are_reported_by_lint():
    p = inklet.plot.panel(30, 20, x=(0, 1), y=(0, 1))
    pts = [(0.5, 0.5)] * 14
    p.scatter(pts)
    p.label_points(pts, [f"label {k}" for k in range(14)])
    built = p.build()
    note = next(n.notes["point_labels"] for n in built.walk()
                if "point_labels" in n.notes)
    assert note["unresolved"]
    found = inklet.lint(built, rules=["LABEL_UNPLACED"])
    assert len(found) == 1 and found[0].severity == "warning"


def test_clean_labels_are_not_reported():
    p = inklet.plot.panel(40, 30, x=(0, 10), y=(0, 10))
    pts = [(2, 2), (8, 8)]
    p.scatter(pts)
    p.label_points(pts, ["low", "high"])
    assert inklet.lint(p.build(), rules=["LABEL_UNPLACED"]) == []


# -- place_labels(method="joint") -------------------------------------------


def test_joint_callouts_cover_no_parts_where_greedy_does():
    greedy = bench.run("diagram_24", legacy=True)
    joint = bench.run("diagram_24")
    assert joint["label_mark"] == 0 < greedy["label_mark"]
    assert joint["unresolved"] < greedy["unresolved"]


def test_place_labels_notes_and_method_check():
    th = inklet.current_theme()
    dots = inklet.place([((x * 6, 0), inklet.marker("circle", 1.2).named(f"d{x}"))
                         for x in range(4)])
    art = dots
    for x in range(4):
        art = inklet.annotate(dots.find(f"d{x}"), f"dot {x}", within=art,
                              size=th.font_size_small)
    for method in ("greedy", "joint"):
        placed = inklet.place_labels(art, method=method)
        note = placed.notes["place_labels"]
        assert note == {"count": 4, "method": method, "unresolved": []}
    with pytest.raises(ValueError):
        inklet.place_labels(art, method="magic")
    once = inklet.place_labels(art, method="joint")
    assert stable(inklet.to_svg(once)) == stable(inklet.to_svg(
        inklet.place_labels(art, method="joint")))
