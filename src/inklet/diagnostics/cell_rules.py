"""Diagnostics for a size or position a document could not honour.

The layout keeps every size the author set where it can. Where it cannot, it
leaves a note on the placed cell or on the bars, and these rules say so: the
cell, the authored value, the value it was drawn at and the cause. The layout
never resizes a plot to make a page fit; it reports the conflict instead.
"""
from __future__ import annotations

from collections.abc import Mapping

from ..core import Rect
from .rules import Diagnostic, LintContext

# The note keys are spelled out here rather than imported from the layout and
# plot modules, which both import the diagnostics package's neighbours.
OVERHANG_NOTE = "axis_title_overhang"
WIDTH_NOTE = "plot_width_overridden"
BAR_WIDTH_NOTE = "bar_width_scale"


def _noted(ctx: LintContext, key: str) -> dict[str, list]:
    """{node id: findings} for nodes carrying the note, at their deepest holder.

    A wrapper with one child inherits the child's notes (`carry_notes`), so a
    note turns up on every such wrapper above it; only the deepest holder is
    reported.
    """
    noted: dict[str, list] = {}
    for node_id, node in ctx.nodes.items():
        notes = getattr(node, "notes", None)
        found = notes.get(key) if isinstance(notes, Mapping) else None
        if isinstance(found, list):
            found = [item for item in found if isinstance(item, Mapping)]
            if found:
                noted[node_id] = found
        elif isinstance(found, Mapping):
            noted[node_id] = [found]
    wrappers = {step for node_id in noted for step in ctx.ancestors(node_id)}
    return {node_id: items for node_id, items in noted.items() if node_id not in wrappers}


def _box(ctx: LintContext, node_id: str) -> Rect | None:
    placed = ctx.placements.get(node_id)
    return None if placed is None else placed.bbox


def _cell(ctx: LintContext, node_id: str) -> str:
    node = ctx.nodes.get(node_id)
    name = getattr(node, "name", None)
    return f"cell {name!r}" if name else "cell"


def rule_axis_title_overhang(ctx: LintContext) -> list[Diagnostic]:
    """A plot's y-axis title longer than the plot, and what it runs into."""
    out: list[Diagnostic] = []
    for node_id, findings in sorted(_noted(ctx, OVERHANG_NOTE).items()):
        for found in findings:
            label = found.get("label", "label")
            length = float(found.get("length", 0.0))
            plot = float(found.get("plot", 0.0))
            above = float(found.get("above", 0.0))
            below = float(found.get("below", 0.0))
            hits = [str(hit) for hit in found.get("hits") or ()]
            reaches = []
            if above > .05:
                reaches.append(f"{above:.1f} mm above the plot")
            if below > .05:
                reaches.append(f"{below:.1f} mm below it")
            hit_text = (" and ".join(hits) if hits else "its neighbours")
            out.append(Diagnostic(
                code="AXIS_TITLE_OVERHANG",
                severity="warning",
                message=(f"{_cell(ctx, node_id)}: the y-axis title {label!r} is {length:.1f} mm long, "
                         f"but the plot is {plot:.1f} mm tall, so it reaches {' and '.join(reaches) or 'past the plot'} "
                         f"and runs into {hit_text}; the plot keeps its {plot:.1f} mm height"),
                targets=(node_id,),
                where=_box(ctx, node_id),
                hint=("shorten the title or break it over lines with \\n, give the plot more "
                      "height, or leave a clear gap above and below it"),
            ))
    return out


#: How much narrower than authored a plot in a shared row may be drawn before
#: it is reported. Plots in a grid are routinely given one nominal width that
#: each cell's own tick labels then trim by a few millimetres; that is the
#: layout working, not a broken promise. Losing more than this is.
WIDTH_TOLERANCE = .15


def rule_plot_width_overridden(ctx: LintContext) -> list[Diagnostic]:
    """A plot drawn much narrower than the width its author set."""
    out: list[Diagnostic] = []
    for node_id, findings in sorted(_noted(ctx, WIDTH_NOTE).items()):
        for found in findings:
            authored = float(found.get("authored", 0.0))
            actual = float(found.get("actual", 0.0))
            if actual >= authored*(1 - WIDTH_TOLERANCE):
                continue
            cell = float(found.get("cell", 0.0))
            furniture = float(found.get("furniture", 0.0))
            out.append(Diagnostic(
                code="PLOT_WIDTH_OVERRIDDEN",
                severity="warning",
                message=(f"{_cell(ctx, node_id)}: its plot is authored {authored:.1f} mm wide "
                         f"but is drawn {actual:.1f} mm wide, because the cell is {cell:.1f} mm "
                         f"and the plot's furniture takes {furniture:.1f} mm of it"),
                targets=(node_id,),
                where=_box(ctx, node_id),
                hint=("give its column more room, for example columns=[1, 0.25] for a narrow "
                      "side plot, make the plot narrower, or make the page wider"),
            ))
    return out


def rule_bar_width_scale(ctx: LintContext) -> list[Diagnostic]:
    """Bars whose width in data units is wider than the axis they stand on."""
    out: list[Diagnostic] = []
    for node_id, findings in sorted(_noted(ctx, BAR_WIDTH_NOTE).items()):
        for found in findings:
            width = float(found.get("width", 0.0))
            span = float(found.get("span", 0.0))
            count = int(found.get("count", 1))
            axis = "y" if found.get("orient") == "h" else "x"
            pitch = span / max(count - 1, 1)
            node = ctx.nodes.get(node_id)
            name = getattr(node, "name", None)
            bars = f"bars {name!r}" if name else "the bars"
            out.append(Diagnostic(
                code="BAR_WIDTH_OUT_OF_SCALE",
                severity="warning",
                message=(f"{bars} have width={width:g} in {axis} data units, but the {axis} axis "
                         f"spans only {span:.4g}: each bar is wider than the axis and runs out of "
                         f"the plot, which makes the page taller than the plot's height"),
                targets=(node_id,),
                where=_box(ctx, node_id),
                hint=(f"width= on a continuous axis is in {axis} data units, the axis the bars "
                      f"stand on; about {pitch:.3g}, the spacing of the bars, gives one bar per "
                      f"slot"),
            ))
    return out


__all__ = ["rule_axis_title_overhang", "rule_plot_width_overridden", "rule_bar_width_scale"]
