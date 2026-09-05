"""CROWDING measured on glyphs rather than on line boxes.

A shaped text node's bbox runs from the font's ascender to its descender and
across the full advance, which for a row of digits is most of a millimetre of
empty box above the ink and half of one below. Two labels that pass each other
diagonally across that emptiness are nowhere near each other on the page, and
the linter has to agree -- `examples/gallery.py` reported the corner of a
log-log panel as a 0.97mm near miss when the reader sees 2.2mm.
"""

from __future__ import annotations

import inklet
from inklet.core import Vec2, group, resolve
from inklet.diagnostics import build_context, lint
from inklet.diagnostics.rules import _ink_box


def crowding(node) -> list[str]:
    return [d.message for d in lint(node) if d.code == "CROWDING"]


def placed(first, second, dx: float, dy: float):
    """`second` moved so its bottom-right corner clears `first`'s top-left by
    (dx, dy) -- measured on the line boxes, which is what used to be judged."""
    boxes = resolve(group([first, second]))
    one, two = boxes[first.id].bbox, boxes[second.id].bbox
    shift = Vec2(one.x0 - dx - two.x1, one.y0 - dy - two.y1)
    return group([first, second.translated(shift.x, shift.y)])


def test_two_labels_meeting_at_a_corner_are_not_crowded():
    # 0.92mm between the boxes, which is under the clearance; the digits
    # themselves are more than 2mm apart in y alone.
    x_tick = inklet.text("100", size=6.0).named("x-tick")
    y_tick = inklet.text("102", size=6.0).named("y-tick")

    assert crowding(placed(x_tick, y_tick, 0.6, 0.7)) == []


def test_a_label_that_really_does_nearly_touch_is_still_crowded():
    # 0.4mm of white between the digits and the rule beside them. Ink is the
    # only thing re-measured, so a finding that was about ink all along stands
    # -- and stands at the distance a reader would measure.
    label = inklet.text("100", size=6.0).named("value")
    ctx = build_context(label, resolve(label))
    item = ctx.items[0]
    bearing = _ink_box(ctx, item).x1 - item.bbox.x1   # negative: box is wider
    rule = inklet.box(width=4.0, height=8.0).named("rule")
    span = resolve(rule)[rule.id].bbox
    beside = rule.translated(item.bbox.x1 + 0.2 - span.x0, 0.0)

    found = crowding(group([label, beside]))

    assert len(found) == 1, found
    assert "value" in found[0], found[0]
    assert f"{0.2 - bearing:.2f}mm" in found[0], found[0]


def test_the_ink_box_of_a_hand_made_prim_is_its_line_box():
    # No `font_path`, so there is nothing to outline and nothing to gain: the
    # rules go on measuring exactly what they measured before.
    from inklet.core import Diagram, TextLine, TextPrim

    node = Diagram(
        prim=TextPrim(lines=(TextLine("100", 6.0, 0.0),), font_family="Inter",
                      font_size=2.0, ascent=1.6, descent=0.4),
        kind="text",
    )
    ctx = build_context(node, resolve(node))
    item = ctx.items[0]

    assert _ink_box(ctx, item) == item.bbox


def test_a_shape_keeps_its_own_box():
    box = inklet.box("cell", width=10.0, height=6.0)
    ctx = build_context(box, resolve(box))
    shapes = [i for i in ctx.items if i.is_shape]

    assert shapes and all(_ink_box(ctx, i) == i.bbox for i in shapes)
