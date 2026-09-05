"""`OFF_PANEL` -- a label that leaves through the wall of its own plot box.

`OFF_CANVAS` catches ink that runs off the page, and every rule in the library
is happy with a panel: the frame `inklet.panel(...).outline()` draws is a single
closed polyline, so it takes part in no overlap pair and no crowding pair, and
a label placed half outside it is nobody's finding. It is also one of the few
figure faults you cannot see in the data -- the label is *there*, correctly
positioned in data coordinates, and what removes half of it is the edge of the
box it was drawn in.

`figures/structure.py` panel (d) is the motivating case, and its own comment
says so: five concentration labels, each five response units above its own
curve, and the top one over a curve that reaches 36 of the 40 the axis is
marked to, in a box whose y range stops at 42. Five units above 36 is 41 and
the type is 1.4mm tall, so the label came out cut in half by the frame. The fix
in the figure is `lift = min(5.0, D_TOP - 0.6 - tall - level)` -- a clamp the
figure has to compute for itself, from numbers only it knows, because nothing
would have told it. This is the rule that tells it.

**Grade: info.** A label crossing the wall is nearly always a defect, but not
quite always -- a caption deliberately hung over the frame, a legend keyed to
sit on the edge -- and unlike `OFF_CANVAS` the ink is still on the page and
still printed. It is worth a line in the report and not worth failing on.

The plot box is the `plot_area` note, so this needs nothing new from `plot`:
`Panel.build` publishes it, `row`, `column` and `facets` publish the union of
their members', and `draw.annotate.letters` carries it onto the wrapper it puts
round a lettered panel. That last one is why the *nearest* declaring ancestor
is the one that answers -- a label inside a lettered panel has two of them
above it, naming the same rectangle, and reporting it twice would be a report
about the linter.
"""

from __future__ import annotations

from collections.abc import Mapping

from ..core import Rect
from ..draw.coords import AREA_NOTE
from ..plot.axis import AXIS_KIND
from ..plot.key import COLORBAR_KIND, LEGEND_KIND
from .rules import (
    Diagnostic, Item, LintContext, _mm, _outside, _sides_phrase,
)

__all__ = ["rule_off_panel"]

#: Containers the plot layer places itself, whose contents sit where the layer
#: put them. A `side="top"` legend is above the plot box by construction and a
#: tick label is below it by construction, so where their text falls relative
#: to that rectangle is the layer's arithmetic and not a finding about the
#: figure. The geometric test below catches most of these on its own -- they
#: are usually clear of the box entirely -- but not all: a top legend's entry
#: dips a few tenths of a millimetre inside the frame, which is enough to make
#: it overlap and enough to make it "leave", and reporting that would put a
#: line in the report of every panel with a legend on it.
FURNITURE_KINDS = (AXIS_KIND, LEGEND_KIND, COLORBAR_KIND)


def rule_off_panel(ctx: LintContext) -> list[Diagnostic]:
    """Text that leaves the plot box of the panel it was placed in."""
    out: list[Diagnostic] = []
    for item in ctx.items:
        if not item.is_text or not item.draws:
            continue
        if _is_furniture(ctx, item.id):
            continue
        home = _plot_box(ctx, item.id)
        if home is None:
            continue
        panel_id, box = home
        if box.overlap(item.bbox) is None:
            continue       # axis furniture: outside the box, and meant to be
        sides = _outside(item.bbox, box)
        if not sides:
            continue
        worst = max(sides, key=lambda side: sides[side])
        out.append(Diagnostic(
            code="OFF_PANEL",
            severity="info",
            message=(f"{item.described} leaves {ctx.label(panel_id)}'s plot "
                     f"box by {_sides_phrase(sides)}"),
            targets=(item.id,),
            where=item.bbox,
            hint=(f"clamp it to the axis range, or widen the panel's "
                  f"{'x' if worst in ('left', 'right') else 'y'} range by "
                  f"{_mm(sides[worst])} on the {worst}"),
        ))
    return out


def _is_furniture(ctx: LintContext, node_id: str) -> bool:
    """Whether this text was placed by an axis, a legend or a colour bar."""
    return any(getattr(ctx.nodes.get(step), "kind", None) in FURNITURE_KINDS
               for step in ctx.chain(node_id))


def _plot_box(ctx: LintContext, node_id: str) -> tuple[str, Rect] | None:
    """The plot box of the nearest ancestor-or-self that declares one.

    *Nearest*, because a lettered panel and the panel inside it both carry the
    note and both name the same rectangle; and because a `facets` grid's note
    is the union of its members', which a label inside one member is inside
    even when it has left that member's own box.

    The note is written in the declaring node's own local frame -- the frame it
    was drawn in, before the recentring a built panel gets -- and
    `Placement.world` maps exactly that frame onto the page, so one transform
    puts the rectangle in the same space as `Item.bbox`. Reading it through
    `draw.coords.plot_area` instead would apply the node's own transform twice.
    """
    for step in reversed(ctx.chain(node_id)):
        node = ctx.nodes.get(step)
        notes = getattr(node, "notes", None)
        area = notes.get(AREA_NOTE) if isinstance(notes, Mapping) else None
        if not isinstance(area, Rect):
            continue
        placed = ctx.placements.get(step)
        if placed is None:                               # pragma: no cover
            continue      # placements from a different resolve(); say nothing
        return step, area.transform(placed.world)
    return None
