"""Folding one label's collisions, and naming links and containers by words.

* One label over a cloud of marks is one OVERLAP that names the label and how
  many marks it reaches, not one line per mark.
* Two labels over marks are two findings; a label touching one or two things
  stays as it was, one line per pair.
* A label crowding three or more things is one CROWDING, folded the same way.
* A link finding leads with the words of its route, and a container finding
  with what the container is, each with its id after it.
"""

from __future__ import annotations

import re
import warnings

import inklet as i
from inklet.core import Diagram, RectPrim, TextLine, TextPrim, group, pt, resolve
from inklet.diagnostics import lint
from inklet.links import link as make_link, route


def _quietly(build):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return build()


def _findings(points, labels):
    """A scatter with labels written on it, linted the way a figure is."""
    panel = i.panel(60, 40, x=(0, 10), y=(0, 100))
    panel.scatter(points, name="data")
    for x, y, words in labels:
        panel.text(x, y, words)
    panel.axis("bottom").axis("left")
    figure = i.figure(width="96mm")
    figure.add(panel.build())
    return _quietly(lambda: figure.lint())


def _codes(findings, code):
    return [d for d in findings if d.code == code]


#: The cloud from the bug report: 25 marks, the label written on top of them.
_CLOUD = [(x / 10, 60 + y / 2) for x in range(60, 101, 4) for y in range(0, 12, 2)]


def test_one_label_over_a_cloud_is_one_overlap_naming_the_count():
    found = _findings(_CLOUD, [(8.0, 63.9, "mean 63.9")])

    (overlap,) = _codes(found, "OVERLAP")
    assert re.search(
        r"^the label 'mean 63\.9' \(label\d+\) overlaps 25 marks inside .+ "
        r"\(largest overlap \d+\.\dmm\^2\)$",
        overlap.message), overlap.message
    assert overlap.severity == "warning"
    # Every mark and the label are involved, so the agent can find them all.
    assert len(overlap.targets) == 26
    assert "annotate()" in overlap.hint


def test_two_labels_over_marks_are_two_findings():
    cloud_below = [(x / 10, 10 + y / 2) for x in range(60, 101, 4) for y in range(0, 12, 2)]
    found = _findings(_CLOUD + cloud_below,
                      [(8.0, 63.9, "mean 63.9"), (8.0, 13.9, "mean 13.9")])

    overlaps = _codes(found, "OVERLAP")
    assert len(overlaps) == 2
    words = sorted(re.match(r"^the label '([^']+)'", d.message).group(1)
                   for d in overlaps)
    assert words == ["mean 13.9", "mean 63.9"]
    for overlap in overlaps:
        assert "overlaps 25 marks" in overlap.message


def test_an_isolated_pair_is_reported_as_it_always_was():
    found = _findings([(8.0, 67.0)], [(8.0, 69.0, "mean 63.9")])

    (overlap,) = _codes(found, "OVERLAP")
    assert re.match(
        r"^the label 'mean 63\.9' \(label\d+\) overlaps the mark \(mark\d+\) over ",
        overlap.message), overlap.message
    assert "separate them by at least" in overlap.hint


def test_two_pairs_on_one_label_stay_two_lines():
    found = _findings([(8.0, 67.0), (8.0, 68.0)], [(8.0, 69.0, "mean 63.9")])

    overlaps = _codes(found, "OVERLAP")
    assert len(overlaps) == 2
    assert all("overlaps the mark (mark" in d.message for d in overlaps)


# -- CROWDING --------------------------------------------------------------


def _text(content: str, width: float, name: str) -> Diagram:
    size = pt(8)
    node = Diagram(
        prim=TextPrim(lines=(TextLine(content, width, 0.0),), font_family="Inter",
                      font_size=size, ascent=size * 0.8, descent=size * 0.2),
        kind="text",
    )
    return node.named(name)


def _box(w: float, h: float, *children: Diagram, name: str | None = None) -> Diagram:
    node = Diagram(prim=RectPrim(w, h), children=tuple(children), kind="box")
    return node.named(name) if name else node


def test_a_label_crowding_three_things_at_three_gaps_is_one_crowding():
    # Three boxes under one text, each at its own gap, so no two share a gap
    # and the pairs reach the fold rather than one line per container gap.
    label = _text("mean 63.9", 10.0, "tag")
    boxes = [_box(2.0, 2.0, name=f"b{k}").translated(cx, -1.4112 - gap - 1.0)
             for k, (cx, gap) in enumerate(zip((-4.0, 0.0, 4.0), (0.4, 0.6, 0.8)))]
    figure = Diagram(children=(label, *boxes), kind="content")

    crowding = _codes(lint(figure), "CROWDING")

    (finding,) = crowding
    assert re.match(
        r"^the text 'mean 63\.9' named 'tag' \(text\d+\) is under the 1\.00mm "
        r"clearance from 3 boxes inside ", finding.message), finding.message
    assert finding.severity == "info"
    assert len(finding.targets) == 4
    assert finding.hint.startswith("move the text clear of them")


# -- link and container wording --------------------------------------------


def _connected(content, source, target, **kwargs) -> Diagram:
    laid_out = group(content)
    routed = route(make_link(source, target, **kwargs), resolve(laid_out))
    return Diagram(children=(laid_out, routed), kind="content")


def test_a_link_finding_leads_with_its_route_and_keeps_the_id_last():
    a = _box(10.0, 10.0, name="a")
    b = _box(10.0, 10.0, name="b").translated(0.0, 40.0)
    mid = _box(20.0, 8.0, name="mid").translated(0.0, 20.0)
    figure = _connected([a, b, mid], a, b.children[0])

    (crossing,) = _codes(lint(figure), "LINK_CROSSES")

    assert re.match(
        r"^the link 'a -> b' \(link\d+\) runs through the box named 'mid' \(box\d+\)",
        crossing.message), crossing.message
    assert not re.match(r"^link\d", crossing.message)


def test_a_container_finding_leads_with_what_it_is():
    label = _text("Encoder (ViT-B/16)", 23.0, "label")
    frame = _box(20.0, 10.0, label)

    (overflow,) = _codes(lint(frame), "TEXT_OVERFLOW")

    assert re.search(r"overflows the box \(box\d+\) by ", overflow.message), overflow.message
    assert not re.search(r"overflows box\d", overflow.message)
    assert re.search(r"widen the box \(box\d+\) by 3\.00mm", overflow.hint), overflow.hint
