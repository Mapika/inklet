"""`inklet.place_labels`: the half of the loop that fixes what `inklet.lint` finds.

The claims worth pinning are the ones a placer is usually allowed to be vague
about:

* it **closes the loop** -- the same linter that reported `CROWDING` and
  `OVERLAP` on the greedy tree reports none on the placed one;
* it is a **fixed point** -- running it again changes nothing, which is the
  only way an opt-in pass is safe to call from a script that may already have
  called it;
* it does not depend on the **order the labels were written**, only on where
  their targets are, so two scripts that draw the same picture get the same
  picture back;
* it **stays in its lane** -- a tree with no annotation in it comes back as the
  very same object, panels and ticks untouched.
"""

from __future__ import annotations

import dataclasses

import pytest

import inklet
from inklet.core.diagram import resolve
from inklet.draw.annotate import (ANNOTATION_LABEL_KIND, LABEL_SPEC_NOTE,
                               annotation_side, label_slot, label_specs)
from inklet.layout.labels import LabelWeights

TH = inklet.theme("nature")

#: A deliberately mean little field: nine dots in 26 x 18mm, several pairs
#: closer together than a label is wide.
POINTS = [
    (2.0, 2.0, "alpha"), (9.0, 3.0, "beta"), (16.0, 2.5, "gamma"),
    (4.0, 9.0, "delta"), (10.5, 8.0, "epsilon"), (15.0, 9.5, "zeta"),
    (3.0, 15.0, "eta"), (11.0, 15.5, "theta"), (17.0, 14.0, "iota"),
]

CODES = ("CROWDING", "OVERLAP", "LINK_CROSSES")


def dots(points=POINTS) -> inklet.Diagram:
    return inklet.place([((x, y), inklet.marker("circle", 1.2, fill=TH.ink,
                                          stroke="none").named(name))
                      for x, y, name in points])


def labelled(field: inklet.Diagram, points=POINTS) -> inklet.Diagram:
    art = field
    for _, _, name in points:
        art = inklet.annotate(field.find(name), name, within=art, clear=1.0,
                           name=name, size=TH.font_size_small)
    return art


def sheet(art: inklet.Diagram) -> inklet.Figure:
    fig = inklet.figure(width="72mm", theme=TH, margin=4)
    fig.add(art)
    return fig


def counts(art: inklet.Diagram) -> dict[str, int]:
    out: dict[str, int] = {}
    for finding in sheet(art).lint():
        if finding.code in CODES:
            out[finding.code] = out.get(finding.code, 0) + 1
    return out


def sides(art: inklet.Diagram) -> dict[str, str]:
    """Which side each label actually landed on, keyed by the name it carries.

    Read off the tree rather than off a fresh `label_plan`, because the
    question is what the placer *did*, not what it would do next.
    """
    return {node.name.rsplit("!", 1)[0]: annotation_side(node)
            for node in art.walk() if node.name and "!" in node.name}


# -- the loop closes ------------------------------------------------------


def test_placer_clears_what_lint_reported():
    field = dots()
    greedy = labelled(field)
    before = counts(greedy)
    after = counts(inklet.place_labels(greedy))
    assert sum(before.values()) > 0, "the fixture has to be crowded to prove anything"
    assert after == {}, f"still crowded: {after} (was {before})"


def test_every_label_still_says_the_same_thing():
    """Moving a label must not lose it, rename it or drop its leader."""
    greedy = labelled(dots())
    placed = inklet.place_labels(greedy)
    for art in (greedy, placed):
        found = [n for n in art.walk() if n.kind == ANNOTATION_LABEL_KIND]
        assert len(found) == len(POINTS)
    assert len(label_specs(placed)) == len(POINTS)


# -- a fixed point --------------------------------------------------------


def test_running_it_twice_changes_nothing():
    once = inklet.place_labels(labelled(dots()))
    twice = inklet.place_labels(once)
    # `Diagram.__eq__` excludes `id`, which is the point: rebuilding mints new
    # ids and moves not one millimetre of geometry.
    assert twice == once
    assert inklet.place_labels(twice) == once


def test_second_pass_moves_nobody():
    once = inklet.place_labels(labelled(dots()))
    plan = inklet.label_plan(once)
    assert plan, "the plan has to see the labels for this to mean anything"
    assert not any(choice.moved for choice in plan)


def test_first_pass_moves_somebody():
    plan = inklet.label_plan(labelled(dots()))
    assert sum(choice.moved for choice in plan) >= 3


# -- the order the labels were written ------------------------------------


def test_order_of_the_annotate_calls_does_not_matter():
    field = dots()
    forward = inklet.place_labels(labelled(field))
    backward = inklet.place_labels(labelled(field, list(reversed(POINTS))))
    assert sides(forward) == sides(backward)


def test_two_builds_of_one_figure_agree():
    """Determinism across builds, ids aside -- nothing here reads a hash."""
    first = inklet.place_labels(labelled(dots()))
    second = inklet.place_labels(labelled(dots()))
    assert sides(first) == sides(second)
    assert first == second


# -- scope discipline -----------------------------------------------------


def test_a_tree_with_no_labels_comes_back_untouched():
    plain = inklet.vstack([inklet.box("a"), inklet.box("b")], gap=4)
    assert inklet.place_labels(plain) is plain
    assert inklet.label_plan(plain) == ()


def test_it_does_not_touch_a_panel():
    """v1 places point-labels. Ticks, axes and legends belong to `Panel`."""
    p = inklet.panel(40, 25, x=(0.0, 10.0), y=(0.0, 10.0))
    p.line([(0.0, 0.0), (10.0, 10.0)], name="model")
    p.axes(x="t / s", y="x")
    built = p.build()
    page = inklet.vstack([built, labelled(dots())], gap=4)
    placed = inklet.place_labels(page)
    assert placed is not page              # the labels did move
    assert placed.children[0] is page.children[0]


def test_a_label_whose_target_left_the_frame_is_left_alone():
    """A spec naming a node the frame never held is skipped, not crashed on."""
    stray = inklet.annotate(inklet.box("other"), "x", side="s", name="x")
    stray.notes[LABEL_SPEC_NOTE] = dataclasses.replace(
        stray.notes[LABEL_SPEC_NOTE], target=inklet.box("elsewhere"))
    assert inklet.label_plan(stray) == ()
    assert sides(inklet.place_labels(stray)) == {"x": "s"}


# -- the knobs ------------------------------------------------------------


def test_sides_restricts_the_candidate_set():
    placed = inklet.place_labels(labelled(dots()), sides=("e", "w"))
    assert set(sides(placed).values()) == {"e", "w"}


def test_a_heavy_length_weight_pins_everything_to_the_near_radius():
    art = labelled(dots())
    plan = inklet.label_plan(art, weights=LabelWeights(length=1000.0))
    assert {round(choice.clear, 6) for choice in plan} == {1.0}


def test_radii_are_multiples_of_the_authored_clearance():
    plan = inklet.label_plan(labelled(dots()), radii=(1.0, 3.0))
    assert {round(choice.clear, 6) for choice in plan} <= {1.0, 3.0}


# -- the geometry the placer scores on ------------------------------------


def test_label_slot_is_where_annotate_actually_puts_it():
    field = dots()
    target = field.find("epsilon")
    art = inklet.annotate(target, "epsilon", within=field, side="se", clear=1.7)
    spec, = label_specs(art)
    placed = [n for n in art.walk() if n.kind == ANNOTATION_LABEL_KIND][0]
    actual = resolve(art)[placed.id].bbox
    slot = label_slot(target, spec.body, side="se", clear=1.7, within=field)
    assert slot.x0 == pytest.approx(actual.x0)
    assert slot.y0 == pytest.approx(actual.y0)
    assert slot.x1 == pytest.approx(actual.x1)
    assert slot.y1 == pytest.approx(actual.y1)


def test_label_slot_rejects_a_nonsense_side():
    field = dots()
    with pytest.raises(ValueError):
        label_slot(field.find("alpha"), inklet.text("x"), side="up")


def test_search_false_takes_the_side_as_final():
    """The knob `place_labels` relies on: no local second-guessing."""
    field = dots()
    art = field
    for _, _, name in POINTS:
        art = inklet.annotate(field.find(name), name, within=art, side="n",
                           clear=1.0, size=TH.font_size_small, search=False)
    assert all(annotation_side(n) == "n" for n in art.walk()
               if n.name and "!" in n.name)
    # ...and with the search on, at least one of them has to give way.
    greedy = labelled(field)
    assert any(annotation_side(n) != "n" for n in greedy.walk()
               if n.name and "!" in n.name)


def test_the_spec_records_what_was_asked_not_what_happened():
    field = dots()
    art = labelled(field)
    asked = {spec.target_id: spec.side for spec in label_specs(art)}
    assert set(asked.values()) == {"n"}
    placed = inklet.place_labels(art)
    got = {spec.target_id: spec.side for spec in label_specs(placed)}
    assert got != asked


# -- what the placer is trading off ---------------------------------------


def test_the_score_is_the_sum_of_the_three_terms():
    weights = LabelWeights()
    for choice in inklet.label_plan(labelled(dots()), weights=weights):
        expected = (weights.overlap * choice.overlap
                    + weights.crossing * choice.crossings
                    + weights.length * choice.length)
        assert choice.score == pytest.approx(expected)


def test_an_uncrowded_label_costs_nothing_but_its_leader():
    lonely = inklet.place([((0.0, 0.0), inklet.marker("circle", 1.2).named("one"))])
    art = inklet.annotate(lonely.find("one"), "one", within=lonely, clear=1.0)
    choice, = inklet.label_plan(art)
    assert choice.overlap == 0.0
    assert choice.crossings == 0
    assert choice.side == "n"          # first candidate, nothing beats it
    assert choice.clear == pytest.approx(1.0)


def test_the_crossing_term_decides_when_nothing_else_does():
    """The one weight the field measurements never exercised, pinned here.

    A dot with a bar 4mm north of it: the north slot is otherwise the cheapest
    (it is the first candidate and every slot at this clearance is the same
    length), and its leader is the only one that has to drive through the bar.
    Priced at nothing the label goes north across the bar; priced at all it
    steps aside.
    """
    bar = inklet.polygon([(-6.0, -4.1), (6.0, -4.1), (6.0, -3.9), (-6.0, -3.9)],
                      fill=TH.ink, stroke="none").named("bar")
    field = inklet.place([
        ((0.0, 0.0), inklet.marker("circle", 1.2, fill=TH.ink,
                                stroke="none").named("dot")),
        ((0.0, -4.0), bar),
    ])
    art = inklet.annotate(field.find("dot"), "cell", within=field, clear=6.0,
                       size=TH.font_size_small)
    blind, = inklet.label_plan(art, weights=LabelWeights(crossing=0.0))
    seeing, = inklet.label_plan(art, weights=LabelWeights(crossing=1000.0))
    assert (blind.side, blind.crossings) == ("n", 1)
    assert seeing.crossings == 0 and seeing.side != "n"
