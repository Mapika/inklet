"""inklet.plot: the beeswarm, measured on the page.

A swarm makes four promises that a picture cannot be trusted to keep by
inspection, so every one of them is a test here: every observation is drawn,
no two dots touch, no dot is moved along its value axis, and the dots straddle
the category line. The fifth -- that the same sample swarms the same way twice
-- is what makes the SVG byte-identical, so it is checked against a shuffled
copy of the input as well as against a second build.

The geometry is read back the way the rest of the plot tests read it: resolve
the built panel and look at where the marks actually landed.
"""

from __future__ import annotations

import math

import pytest

from inklet import use_theme
from inklet.core import DiagramError, resolve
from inklet.draw.coords import as_drawn
from inklet.draw.shapes import MARK_KIND
from inklet.diagnostics import lint
from inklet.plot import panel
from inklet.plot.marks import swarm_offsets


SAMPLE = [73.0, 74.1, 75.0, 77.9, 78.6, 80.0, 80.5, 83.0, 85.4, 92.5, 93.4, 99.0]
OTHER = [62.6, 62.8, 64.8, 66.1, 66.4, 67.6, 69.8, 70.4, 72.1, 74.6, 77.3]


@pytest.fixture(autouse=True)
def _theme():
    use_theme("nature")


def dots(p) -> list[tuple[float, float, float]]:
    """`(x, y, diameter)` of every mark drawn into the panel."""
    out = []
    for placed in resolve(as_drawn(p.build())).values():
        if placed.diagram.kind == MARK_KIND:
            box = placed.bbox
            out.append(((box.x0 + box.x1) / 2, (box.y0 + box.y1) / 2,
                        box.x1 - box.x0))
    return sorted(out)


def closest(placed) -> float:
    """The smallest distance between two dot centres, in millimetres."""
    return min(math.dist(a[:2], b[:2])
               for i, a in enumerate(placed) for b in placed[i + 1:])


# --- the four promises -------------------------------------------------------


def test_every_observation_gets_its_own_dot() -> None:
    p = panel(30, 30, x=["a", "b"], y=(55, 105))
    p.swarm({"a": SAMPLE, "b": OTHER})

    assert len(dots(p)) == len(SAMPLE) + len(OTHER)


@pytest.mark.parametrize("size", [0.8, 1.1, 1.5])
def test_no_two_dots_overlap_at_any_publication_size(size: float) -> None:
    p = panel(30, 30, x=["a"], y=(55, 105))
    p.swarm({"a": SAMPLE}, size=size)
    placed = dots(p)

    assert all(d == pytest.approx(size) for _, _, d in placed)
    assert closest(placed) >= size - 1e-9


def test_a_swarm_never_moves_a_value() -> None:
    p = panel(30, 30, x=["a"], y=(55, 105))
    p.swarm({"a": SAMPLE})
    drawn = sorted(y for _, y, _ in dots(p))

    assert drawn == pytest.approx(sorted(p.y.map(v) for v in SAMPLE))


def test_the_dots_straddle_the_category_line() -> None:
    p = panel(30, 30, x=["a", "b"], y=(55, 105))
    p.swarm({"a": SAMPLE, "b": OTHER})
    for group, sample in (("a", SAMPLE), ("b", OTHER)):
        centre = p.x.map(group)
        xs = [x for x, _, _ in dots(p) if abs(x - centre) < 5.0]
        assert len(xs) == len(sample)
        assert (min(xs) + max(xs)) / 2 == pytest.approx(centre)


def test_two_builds_of_one_sample_place_the_dots_identically() -> None:
    def built():
        p = panel(30, 30, x=["a"], y=(55, 105))
        p.swarm({"a": SAMPLE})
        return dots(p)

    assert built() == built()


def test_the_input_order_does_not_change_the_picture() -> None:
    def built(sample):
        p = panel(30, 30, x=["a"], y=(55, 105))
        p.swarm({"a": sample})
        return dots(p)

    shuffled = SAMPLE[7:] + SAMPLE[:7]
    assert built(shuffled) == pytest.approx(built(SAMPLE))


def test_ties_are_broken_by_input_order_not_by_anything_else() -> None:
    # Five identical values have nothing to sort on but their index, which is
    # the only tie-break that is the same on every machine and every run.
    first = swarm_offsets([4.0] * 5, 1.0)
    assert first == swarm_offsets([4.0] * 5, 1.0)
    assert sorted(first) == pytest.approx([-2.0, -1.0, 0.0, 1.0, 2.0])


def test_a_crowded_swarm_separates_every_one_of_three_hundred_dots() -> None:
    # The placement merges the blocked intervals around the centre line rather
    # than scanning every edge against every interval, which is only a speed-up
    # if it never merges away a free offset. Three hundred points inside two
    # pitches of each other is where it would show.
    crowd = [20.0 + (i % 37) * 0.01 for i in range(300)]
    offsets = swarm_offsets(crowd, 1.0)
    placed = sorted(zip(offsets, crowd))

    assert len(placed) == 300
    assert min(math.dist(a, b)
               for i, a in enumerate(placed) for b in placed[i + 1:]) >= 1.0 - 1e-9


# --- width ------------------------------------------------------------------


def test_a_swarm_keeps_inside_the_millimetre_cap() -> None:
    crowd = [20.0 + (i % 11) * 0.05 for i in range(60)]
    p = panel(40, 30, x=["a"], y=(19, 22))
    p.swarm({"a": crowd}, max_width=8.0)
    placed = dots(p)
    reach = max(x for x, _, _ in placed) - min(x for x, _, _ in placed)

    assert reach + placed[0][2] <= 8.0 + 1e-9
    assert closest(placed) >= placed[0][2] - 1e-9


def test_overflow_closes_the_gap_before_it_shrinks_the_dots() -> None:
    crowd = [20.0 + (i % 9) * 0.08 for i in range(24)]
    loose = panel(40, 30, x=["a"], y=(19, 22))
    loose.swarm({"a": crowd}, size=1.0)
    tight = panel(40, 30, x=["a"], y=(19, 22))
    tight.swarm({"a": crowd}, size=1.0, max_width=0.92 * (
        max(x for x, _, _ in dots(loose)) - min(x for x, _, _ in dots(loose)) + 1.0))

    assert all(d == pytest.approx(1.0) for _, _, d in dots(tight))
    assert closest(dots(tight)) < closest(dots(loose))


def test_a_swarm_that_cannot_fit_shrinks_the_dots_but_not_below_the_floor() -> None:
    crowd = [20.0] * 200
    p = panel(40, 30, x=["a"], y=(19, 22))
    p.swarm({"a": crowd}, size=1.2, max_width=6.0)
    placed = dots(p)

    assert 0.4 == pytest.approx(placed[0][2])          # the floor, not smaller
    assert closest(placed) >= 0.4 - 1e-9               # still no overlap
    reach = max(x for x, _, _ in placed) - min(x for x, _, _ in placed)
    assert reach > 6.0                                 # and it says so by overrunning


def test_one_call_draws_one_dot_size_however_uneven_the_groups() -> None:
    p = panel(60, 30, x=["few", "many"], y=(19, 22))
    p.swarm({"few": [20.0, 20.5, 21.0],
             "many": [20.0 + (i % 13) * 0.05 for i in range(80)]},
            size=1.2, max_width=7.0)
    sizes = {round(d, 9) for _, _, d in dots(p)}

    assert len(sizes) == 1
    assert sizes.pop() < 1.2


def test_the_slot_caps_the_swarm_when_it_is_the_narrower_of_the_two() -> None:
    crowd = [20.0 + (i % 11) * 0.05 for i in range(40)]
    p = panel(24, 30, x=["a", "b"], y=(19, 22))          # a 12mm band step
    p.swarm({"a": crowd, "b": crowd}, width=0.5, max_width=40.0)
    middle = (p.x.map("a") + p.x.map("b")) / 2
    xs = [x for x, _, _ in dots(p) if x < middle]

    assert max(xs) - min(xs) <= 6.0


# --- the rest of the surface -------------------------------------------------


def test_a_horizontal_swarm_offsets_along_the_other_axis() -> None:
    p = panel(40, 24, y=["a"], x=(55, 105))
    p.swarm({"a": SAMPLE}, orient="h")
    placed = dots(p)

    assert sorted(x for x, _, _ in placed) == pytest.approx(
        sorted(p.x.map(v) for v in SAMPLE))
    assert len({round(y, 6) for _, y, _ in placed}) > 1


def test_hollow_dots_are_paper_with_a_coloured_edge() -> None:
    p = panel(30, 30, x=["a"], y=(55, 105))
    p.swarm({"a": SAMPLE}, hollow=True, colors=["#0072b2"])
    styles = [placed.diagram.style for placed in resolve(as_drawn(p.build())).values()
              if placed.diagram.kind == MARK_KIND]

    assert {s.fill for s in styles} == {"#ffffff"}
    assert {s.stroke for s in styles} == {"#0072b2"}


def test_one_colour_per_group_in_the_order_the_groups_came_in() -> None:
    p = panel(30, 30, x=["a", "b"], y=(55, 105))
    p.swarm({"a": SAMPLE, "b": OTHER}, colors=["#0072b2", "#d55e00"])
    middle = (p.x.map("a") + p.x.map("b")) / 2
    inked = [((q.bbox.x0 + q.bbox.x1) / 2, q.diagram.style.fill)
             for q in resolve(as_drawn(p.build())).values()
             if q.diagram.kind == MARK_KIND]

    assert {fill for x, fill in inked if x < middle} == {"#0072b2"}
    assert {fill for x, fill in inked if x > middle} == {"#d55e00"}


def test_a_swarm_beside_a_box_plot_lints_clean() -> None:
    p = panel(50, 34, x=["a", "b"], y=(55, 105))
    p.grid(x=False, y=True)
    p.boxplot({"a": SAMPLE, "b": OTHER}, outliers=False, width=0.5)
    p.swarm({"a": SAMPLE, "b": OTHER}, size=0.9)
    p.axis("bottom")
    p.axis("left", label="correct (%)")

    assert lint(p.build()) == []


def test_an_empty_group_draws_nothing_and_the_others_still_swarm() -> None:
    p = panel(30, 30, x=["a", "b"], y=(55, 105))
    p.swarm({"a": SAMPLE, "b": []})

    assert len(dots(p)) == len(SAMPLE)


def test_a_swarm_of_nothing_says_so() -> None:
    p = panel(30, 30, x=["a"], y=(55, 105))
    with pytest.raises(DiagramError):
        p.swarm({"a": []})


def test_a_dot_has_to_have_a_size() -> None:
    p = panel(30, 30, x=["a"], y=(55, 105))
    with pytest.raises(DiagramError):
        p.swarm({"a": SAMPLE}, size=0.0)
