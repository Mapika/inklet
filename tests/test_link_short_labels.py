"""Labels on links only a few millimetres long.

Two 11 x 7 mm boxes a few millimetres apart leave no room beside the shaft
for a word. The label must then stay clear of both boxes and the arrowhead,
sit as close to the link as that allows, and say it moved.
"""

from __future__ import annotations

import pytest

from inklet import connect
from inklet.core import Diagram, Placement, Rect, RectPrim, group, resolve
from inklet.diagnostics import lint
from inklet.links import (FLAG_LABEL_OFF_LINK, HEAD_KIND, LABEL_KIND, link,
                          link_flags, route, route_all)


def box(w: float, h: float) -> Diagram:
    return Diagram(prim=RectPrim(w, h, 0.0))


def parts(routed: Diagram, kind: str) -> list[Rect]:
    places: dict[str, Placement] = resolve(routed)
    return [places[node.id].bbox for node in routed.walk() if node.kind == kind]


def overlap(a: Rect, b: Rect) -> float:
    hit = a.overlap(b)
    return 0.0 if hit is None else hit.width * hit.height


def pair(gap: float) -> tuple[Diagram, Diagram, dict[str, Placement]]:
    a = box(11, 7)
    b = box(11, 7).translated(11 + gap, 0)
    return a, b, resolve(group([a, b]))


@pytest.mark.parametrize("gap", [3.0, 4.0])
def test_label_on_a_short_link_clears_both_boxes_and_stays_close(gap):
    a, b, places = pair(gap)
    routed = route_all([link(a, b, label=box(4.5, 2.0))], places).children[0]
    label = parts(routed, LABEL_KIND)[0]
    head = parts(routed, HEAD_KIND)[0]

    for rect in (places[a.id].bbox, places[b.id].bbox, head):
        assert overlap(label, rect) == 0.0
    # Just above the boxes, over the gap -- not a label-height further out.
    assert -3.5 - 1.0 <= label.y1 <= -3.5
    assert places[a.id].bbox.x1 - 1.0 <= label.center.x <= places[b.id].bbox.x0 + 1.0
    assert FLAG_LABEL_OFF_LINK in link_flags(routed)


def test_connect_keeps_a_short_link_label_off_its_end_boxes():
    a, b, places = pair(4.0)
    routed = connect(a, b, within=group([a, b]), label=box(4.5, 2.0))
    label = parts(routed, LABEL_KIND)[0]

    assert overlap(label, places[a.id].bbox) == 0.0
    assert overlap(label, places[b.id].bbox) == 0.0
    assert FLAG_LABEL_OFF_LINK in link_flags(routed)


def test_label_keeps_off_the_arrowhead():
    a, b, places = pair(6.0)
    routed = route_all([link(a, b, label=box(3.0, 1.0), label_offset=0.2)],
                       places).children[0]
    label = parts(routed, LABEL_KIND)[0]

    assert overlap(label, parts(routed, HEAD_KIND)[0]) == 0.0
    assert overlap(label, places[a.id].bbox) == 0.0
    assert overlap(label, places[b.id].bbox) == 0.0


def test_a_label_that_fits_beside_the_link_is_not_flagged():
    a, b, places = pair(8.0)
    routed = route_all([link(a, b, label=box(3.0, 1.5))], places).children[0]
    label = parts(routed, LABEL_KIND)[0]

    assert label.y1 == pytest.approx(-1.0)
    assert FLAG_LABEL_OFF_LINK not in link_flags(routed)


def test_lint_reports_a_label_moved_off_its_link():
    a, b, places = pair(4.0)
    routed = route_all([link(a, b, label=box(4.5, 2.0))], places)
    found = lint(group([a, b, routed]), rules=["LABEL_OFF_LINK"])

    assert [d.code for d in found] == ["LABEL_OFF_LINK"]
    assert found[0].severity == "info"

    wide = pair(12.0)
    clear = route_all([link(wide[0], wide[1], label=box(4.5, 2.0))], wide[2])
    assert lint(group([wide[0], wide[1], clear]), rules=["LABEL_OFF_LINK"]) == []
