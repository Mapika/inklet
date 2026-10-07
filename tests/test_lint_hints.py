"""Lint hints an agent can act on, and findings that used to go unreported.

Four changes, one file:

* An OVERLAP on crowded category labels leads with a fix that clears it. The
  45 degree turn is only offered where the slot fits it; otherwise the hint
  names the width at which it would, and the turn goes with that width.
* A finding names a text node by its words and its kind, with the id last.
* DUPLICATE_KEY: one panel holding two colour bars, or two legends, for one
  series.
* ORPHAN_LEADER: a leader drawn for a label with no text in it.
"""

from __future__ import annotations

import re
import warnings

import inklet as i
from inklet.core import Diagram
from inklet.diagnostics.rules import node_phrase


def _quietly(build):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return build()


def _codes(figure, code):
    return [d for d in figure.lint() if d.code == code]


# -- 1. crowded category labels ---------------------------------------------

LABELS = [f"treatment condition number {k}" for k in range(12)]


def _bars(width, rotate=None):
    options = {"rotate": rotate} if rotate else {}
    chart = i.bar({"c": LABELS, "v": list(range(12))}, x="c", y="v", width=width)
    chart = chart.axes(x="c", y="v", x_options=options)
    return _quietly(lambda: chart.compile())


def _leading_width(hint):
    (width,) = re.findall(r"\(width=(\d+)\)", hint)
    return int(width)


def test_turning_leads_when_the_turned_labels_fit_this_width():
    figure = _bars(120)
    (finding,) = _codes(figure, "OVERLAP")
    assert finding.hint.startswith("rotate them (axes(x_options={'rotate': 45}))")
    # Following the leading suggestion clears the finding.
    assert _codes(_bars(120, rotate=45), "OVERLAP") == []


def test_a_width_too_small_to_turn_in_is_widened_to_one_that_is_not():
    figure = _bars(60)
    (finding,) = _codes(figure, "OVERLAP")
    assert finding.hint.startswith("each turned label needs ")
    assert "widen the plot to at least" in finding.hint
    assert "rotate them" in finding.hint
    # The old advice, turning at this width, does not clear it: that is the
    # suggestion an agent was sent round in a loop by.
    assert _codes(_bars(60, rotate=45), "OVERLAP")
    # Following the widened width, with the turn, clears it.
    assert _codes(_bars(_leading_width(finding.hint), rotate=45), "OVERLAP") == []


def test_an_axis_already_turned_is_not_told_to_turn_again():
    figure = _bars(60, rotate=45)
    (finding,) = _codes(figure, "OVERLAP")
    assert "rotate them" not in finding.hint
    assert "widen the plot to at least" in finding.hint
    assert _codes(_bars(_leading_width(finding.hint), rotate=45), "OVERLAP") == []


# -- 2. internal ids in messages ----------------------------------------------


def _hline_figure():
    """A label written on top of a column of points.

    Placed with `text`, which goes exactly where it is told: a rule's
    `label=` now searches for clear space and would not overlap.
    """
    points = [(x / 10, 60 + y / 2) for x in range(60, 101, 4) for y in range(0, 12, 2)]
    panel = i.panel(60, 40, x=(0, 10), y=(0, 100))
    panel.scatter(points, name="data")
    panel.text(8.0, 63.9, "mean 63.9")
    panel.axis("bottom").axis("left")
    figure = i.figure(width="96mm")
    figure.add(panel.build())
    return _quietly(lambda: figure.lint())


def test_a_labelled_text_node_is_named_by_its_words_and_kind_with_the_id_last():
    found = _hline_figure()
    overlap = next(d for d in found if d.code == "OVERLAP")
    # One label over a cloud of marks is one finding that names the count, not
    # one sentence per mark (see test_lint_grouping_text).
    assert re.search(r"^the label 'mean 63\.9' \(label\d+\) overlaps \d+ marks",
                     overlap.message)


def _near_miss_figure(y):
    """A label set just above a column of points, near enough to crowd them."""
    points = [(x / 10, 60 + k / 2) for x in range(60, 101, 4) for k in range(0, 12, 2)]
    panel = i.panel(60, 40, x=(0, 10), y=(0, 100))
    panel.scatter(points, name="data")
    panel.text(8.0, y, "mean 63.9")
    panel.axis("bottom").axis("left")
    figure = i.figure(width="96mm")
    figure.add(panel.build())
    return _quietly(lambda: figure.lint())


def test_a_crowding_finding_names_the_label_by_its_words():
    found = _near_miss_figure(69.0)
    crowding = [d for d in found if d.code == "CROWDING"]
    assert crowding
    assert all(re.search(r"the label 'mean 63\.9' \(label\d+\)", d.message) for d in crowding)


def test_no_message_leads_with_a_bare_internal_id():
    for finding in _hline_figure():
        assert not re.match(r"^(label|mark|text|box|link)\d", finding.message), finding.message


def test_node_phrase_puts_the_id_last_and_keeps_the_words_and_name():
    labelled = i.text("plain", size=2.0).named("tag")
    phrase = node_phrase(labelled, words="plain")
    assert phrase == f"the text 'plain' named 'tag' ({labelled.id})"


# -- 3. duplicate keys ---------------------------------------------------------


def _heatmap(*, second_bar: bool):
    chart = i.heatmap([[1, 2], [3, 4]], x=["a", "b"], y=["r1", "r2"], colorbar=True)
    if second_bar:
        chart.spec.colorbar(title="r")
    return _quietly(lambda: chart.compile())


def test_a_heatmap_bar_plus_a_second_colorbar_call_is_a_duplicate_key():
    (finding,) = _codes(_heatmap(second_bar=True), "DUPLICATE_KEY")
    assert finding.severity == "warning"
    assert "two colour bars for the same" in finding.message
    assert len(finding.targets) == 2


def test_one_colour_bar_is_not_a_duplicate():
    assert _codes(_heatmap(second_bar=False), "DUPLICATE_KEY") == []


def _two_legends(second_entries):
    panel = i.panel(60, 40, x=(0, 10), y=(0, 10))
    panel.scatter([(1, 1), (5, 5)], name="a")
    panel.legend(corner="ne", entries=[("a", "#ff0000"), ("b", "#00ff00")])
    panel.legend(corner="nw", entries=second_entries)
    figure = i.figure(width="96mm")
    figure.add(panel.build())
    return figure


def test_two_legends_keying_the_same_colour_are_a_duplicate_key():
    figure = _two_legends([("a", "#ff0000"), ("c", "#0000ff")])
    (finding,) = _codes(figure, "DUPLICATE_KEY")
    assert finding.severity == "warning"
    assert "both key the same 1 entry ('a')" in finding.message


def test_two_legends_with_different_entries_are_left_alone():
    figure = _two_legends([("c", "#0000ff"), ("d", "#ffff00")])
    assert _codes(figure, "DUPLICATE_KEY") == []


# -- 4. leaders with no label ------------------------------------------------


def _annotated(text, **options):
    box = i.box("target", width=20, height=10)
    figure = i.figure(width="96mm")
    figure.add(i.annotate(box, text, side="e", clear=8.0, **options))
    return figure


def test_a_leader_drawn_for_an_empty_label_is_an_orphan_leader():
    (finding,) = _codes(_annotated(""), "ORPHAN_LEADER")
    assert finding.severity == "warning"
    assert "drawn for an empty label" in finding.message
    assert "the label ''" in finding.message
    assert finding.targets and finding.targets[0].startswith("link")


def test_a_leader_with_text_at_its_end_is_not_an_orphan():
    assert _codes(_annotated("Peak"), "ORPHAN_LEADER") == []


def test_an_empty_label_without_a_leader_is_not_an_orphan():
    assert _codes(_annotated("", leader=False), "ORPHAN_LEADER") == []


def _point_labels(words):
    """A `label_points` group built by hand: a leader and a label per word.

    The placer draws the leaders in index order, then the labels, and records
    the indices it drew leaders for; the rule matches the two by that order.
    """
    # Direct children, as `draw_place` leaves them: no wrapper per child.
    lines = [i.polyline([(k, k), (k + 3.0, k + 3.0)], kind="mark-line",
                        stroke="#000000") for k in range(len(words))]
    labels = [i.text(word, size=2.0, kind="label") for word in words]
    group = Diagram(kind="point-labels", children=tuple(lines + labels))
    group.note("point_labels", {"count": len(words),
                                "leaders": list(range(len(words))),
                                "unresolved": [], "covering_marks": []})
    figure = i.figure(width="96mm")
    figure.add(group)
    return figure


def test_a_point_label_leader_for_an_empty_word_is_an_orphan_leader():
    (finding,) = _codes(_point_labels(["", "B"]), "ORPHAN_LEADER")
    assert "the label ''" in finding.message
    assert "drawn for an empty label" in finding.message


def test_point_label_leaders_for_labelled_words_are_not_orphans():
    assert _codes(_point_labels(["A", "B"]), "ORPHAN_LEADER") == []


def test_a_leader_with_no_label_beside_it_at_all_is_an_orphan():
    target = i.box("target", width=20, height=10)
    figure = i.figure(width="96mm")
    figure.add(Diagram(kind="annotation",
                       children=(target, Diagram(kind="link"))))
    (finding,) = _codes(figure, "ORPHAN_LEADER")
    assert "is drawn with no label at all" in finding.message
    assert finding.targets and finding.targets[0].startswith("link")
