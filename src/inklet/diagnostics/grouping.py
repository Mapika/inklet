"""Folding a run of pairwise collisions into one finding.

`OVERLAP` and `CROWDING` are pairwise by nature, and a pairwise report scales
with the square of the fault: eight long category names under one axis each
overlap three or four of their neighbours, and that came out as twenty-two
OVERLAP lines and three CROWDING lines -- twenty-five findings, every one with
the same cause and the same fix. A reader skims that, and an agent reading it
spends its context on repetitions of one sentence.

So, after the rules have run, pairs are folded when they concern a *run of
siblings*: text items of one kind under one parent (the tick labels of one
axis, the bar labels of one plot), linked to each other by the pairs
themselves. The links matter. Two unrelated collisions in opposite corners of
one panel share a parent and a kind, but not a pair, so they stay two lines;
a chain of three or more labels touching one another is one problem and is
reported once. An isolated pair -- the common case -- is never touched.

The folded finding keeps the shape every reader of `lint()` relies on: one
`Diagnostic`, the most severe code and severity among the pairs (an overlap
outranks a near miss), every item involved in `targets`, and the first few
label texts quoted in the message the way the pairwise messages quote them.
`inklet.quick` reads those quotes to decide whether to turn category labels.
"""

from __future__ import annotations

import math
from typing import Sequence

from ..core import Rect
from .plot_rules import _panel_name
from .rules import (
    Diagnostic, Item, LintContext, _SEVERITY_RANK, _text_excerpt,
)

__all__ = ["group_runs", "GROUPED_CODES"]

#: The pairwise codes a run is folded out of, most serious first. A run with
#: one overlapping pair in it is an overlap, whatever else is near.
GROUPED_CODES = ("OVERLAP", "CROWDING")

#: Fewer items than this is a pair, which is reported as it always was.
_MIN_RUN = 3

#: How many label texts the message quotes before "and N more".
_QUOTED = 3

#: Wrappers that position a node and say nothing about what it belongs to.
_WRAPPER_KINDS = frozenset({"place", "g"})

_AXIS_KIND = "axis"
_TICK_LABEL_KIND = "tick-label"
_PANEL_KIND = "panel"


def group_runs(ctx: LintContext, diags: Sequence[Diagnostic]) -> list[Diagnostic]:
    """`diags` with every run of three or more colliding siblings folded."""
    keyed: dict[tuple[str, str], list[Diagnostic]] = {}
    rest: list[Diagnostic] = []
    for diag in diags:
        key = _run_key(ctx, diag)
        if key is None:
            rest.append(diag)
        else:
            keyed.setdefault(key, []).append(diag)
    for key in sorted(keyed):
        for component in _components(keyed[key]):
            members = sorted({t for d in component for t in d.targets})
            if len(members) < _MIN_RUN:
                rest.extend(component)
            else:
                rest.append(_folded(ctx, key[0], members, component))
    return rest


def _run_key(ctx: LintContext, diag: Diagnostic) -> tuple[str, str] | None:
    """(parent, kind) when this is a pair of same-kind sibling texts."""
    if diag.code not in GROUPED_CODES or len(diag.targets) != 2:
        return None
    first, second = (ctx.item(t) for t in diag.targets)
    if first is None or second is None or not (first.is_text and second.is_text):
        return None
    if first.node.kind != second.node.kind:
        return None
    home = _run_parent(ctx, first.id)
    if home is None or home != _run_parent(ctx, second.id):
        return None
    return home, first.node.kind or ""


def _run_parent(ctx: LintContext, node_id: str) -> str | None:
    """The nearest ancestor that is more than a positioning wrapper."""
    for step in ctx.ancestors(node_id):
        node = ctx.nodes.get(step)
        if node is not None and node.kind not in _WRAPPER_KINDS:
            return step
    return None


def _components(diags: list[Diagnostic]) -> list[list[Diagnostic]]:
    """The pairs split into groups that share an item, in a fixed order."""
    root: dict[str, str] = {}

    def find(x: str) -> str:
        while root.setdefault(x, x) != x:
            root[x] = root[root[x]]
            x = root[x]
        return x

    for diag in diags:
        a, b = (find(t) for t in diag.targets)
        if a != b:
            root[max(a, b)] = min(a, b)
    groups: dict[str, list[Diagnostic]] = {}
    for diag in diags:
        groups.setdefault(find(diag.targets[0]), []).append(diag)
    return [groups[key] for key in sorted(groups)]


def _folded(ctx: LintContext, parent: str, members: list[str],
            pairs: list[Diagnostic]) -> Diagnostic:
    overlaps = [d for d in pairs if d.code == "OVERLAP"]
    near = [d for d in pairs if d.code != "OVERLAP"]
    code = "OVERLAP" if overlaps else pairs[0].code
    severity = min((d.severity for d in pairs),
                   key=lambda s: _SEVERITY_RANK.get(s, len(_SEVERITY_RANK)))
    items = [ctx.item(t) for t in members]
    items = [i for i in items if i is not None]
    what, hint = _describe_run(ctx, parent, items)
    verb = "overlap each other" if overlaps else "crowd each other"
    counts = []
    if overlaps:
        counts.append(f"{len(overlaps)} overlapping "
                      f"{'pair' if len(overlaps) == 1 else 'pairs'}")
    if near and not overlaps:
        counts.append(f"{len(near)} {'pair' if len(near) == 1 else 'pairs'} "
                      f"under the {ctx.min_clearance_mm:.2f}mm clearance")
    message = (f"{len(members)} {what} {verb}: {_quoted(items)} "
               f"({', '.join(counts)})")
    where: Rect | None = None
    for d in pairs:
        if isinstance(d.where, Rect):
            where = d.where if where is None else where.union(d.where)
    return Diagnostic(code=code, severity=severity, message=message,
                      targets=tuple(members), where=where, hint=hint)


def _quoted(items: list[Item]) -> str:
    """The first few texts, in reading order, as the pairwise messages quote
    them."""
    ordered = sorted(items, key=lambda i: (round(i.bbox.y0, 1), i.bbox.x0, i.id))
    texts = [repr(_text_excerpt(i.prim)) for i in ordered[:_QUOTED]]  # type: ignore[arg-type]
    more = len(ordered) - len(texts)
    return ", ".join(texts) + (f" and {more} more" if more else "")


def _describe_run(ctx: LintContext, parent: str,
                  items: list[Item]) -> tuple[str, str]:
    """(what the run is, how to fix it), from where its members sit."""
    node = ctx.nodes.get(parent)
    panel = next((step for step in ctx.ancestors(parent)
                  if getattr(ctx.nodes.get(step), "kind", None) == _PANEL_KIND),
                 None)
    within = f" of {_panel_name(ctx, panel)}" if panel is not None else ""
    if (node is not None and node.kind == _AXIS_KIND
            and all(i.node.kind == _TICK_LABEL_KIND for i in items)):
        xs = [i.bbox.center.x for i in items]
        ys = [i.bbox.center.y for i in items]
        if max(xs) - min(xs) >= max(ys) - min(ys):
            return (f"x-axis tick labels{within}",
                    _x_tick_fix(ctx, parent, items))
        return (f"y-axis tick labels{within}",
                "show fewer ticks (axes(y_options={'count': 4})), shorten "
                "them, or make the plot taller")
    label = ctx.label(parent)
    # `ctx.label` falls back to the bare id for an unnamed node; say what the
    # node is, with its id after it, rather than leading with the id.
    what = (f"labels in {label}" if label != parent
            else f"labels in the {(node.kind if node else None) or 'figure'} ({parent})")
    return (what, "spread them apart, shorten them, or show fewer of them")


#: The angle the hint offers for crowded category labels, in degrees.
_TURN_DEGREES = 45.0

#: Below this sine a label reads as upright: nearly flat text is still laid
#: along the axis, so it needs the horizontal slot and the turn does not apply.
_UPRIGHT_SIN = 0.2


def _x_tick_fix(ctx: LintContext, axis_id: str, items: list[Item]) -> str:
    """The fix for crowded x tick labels, leading with the one that would work.

    A label turned to an angle `a` stacks its lines `line / sin(a)` apart along
    the axis, plus clearance, so what decides whether turning helps is the slot
    each label gets along the axis (axis length over count), not the length of
    the label. When the 45 degree slot fits at this width, turning leads. When
    it does not, the hint names the width at which it would fit and says that
    the turn goes with it: a turn offered at a width where it cannot work sends
    the agent round again. Shortening a label does not change its line height,
    so it is not offered for the turn.

    The estimate is deliberately generous. The overlap test measures the turned
    ink, which spans more than the line box, so it clears at a slot somewhat
    under the estimate; a width a little too large costs some room, while one
    too small leaves the finding in place and sends the agent round again.
    """
    count = sum(1 for item in ctx.items
                if item.is_text and item.node.kind == _TICK_LABEL_KIND
                and axis_id in ctx.ancestors(item.id))
    spines = [ctx.placements[node.id] for node in ctx.nodes.values()
              if node.kind == "spine" and node.id in ctx.placements
              and axis_id in ctx.ancestors(node.id)]
    if not count or not spines:
        return "spread them apart, shorten them, or show fewer of them"
    slot = spines[0].bbox.width / count
    # Every label on one axis shares a font, so the tallest line is the slot's
    # measure. `ascent + descent` is the block's own height, which is what a
    # turned line stacks on, whether or not the label is turned yet.
    line = max(item.prim.ascent + item.prim.descent for item in items)  # type: ignore[attr-defined]
    world = items[0].world
    turned = abs(world.b) / max(math.hypot(world.a, world.b), 1e-9)
    if turned < _UPRIGHT_SIN:
        sine = math.sin(math.radians(_TURN_DEGREES))
        turn = f"rotate them (axes(x_options={{'rotate': {_TURN_DEGREES:g}}}))"
    else:
        sine = turned
        turn = None
    needed = (line + 2 * ctx.min_clearance_mm) / sine
    if slot >= needed:
        if turn is None:
            return "spread them apart, shorten them, or show fewer of them"
        return (f"{turn}, which fits this width (each label has {slot:.1f}mm "
                f"and a turned one needs {needed:.1f}mm)")
    extra = count * (needed - slot)
    prefix = (f"each turned label needs {needed:.1f}mm of axis and has "
              f"{slot:.1f}mm; ")
    if ctx.page is None:
        widen = f"widen the plot by at least {extra:.0f}mm"
    else:
        wide = math.ceil(ctx.page.width + extra)
        widen = f"widen the plot to at least {wide}mm (width={wide})"
    if turn is None:
        return prefix + widen
    return prefix + f"{widen} and {turn}"
