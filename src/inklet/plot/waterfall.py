"""Waterfall charts: a running total built up from signed changes.

Each change is a bar floating between the running total before it and the
running total after it, coloured by whether it raised or lowered the total.
A *total* position is a bar standing on the baseline at the running total,
which is how a subtotal or the end value is shown. A thin connector runs
from the end of one bar to the start of the next, at the level they share.

`waterfall_steps` does the arithmetic without drawing; `Panel.waterfall` is
the usual way to draw one.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping, Sequence

from ..core import Diagram, DiagramError
from ..draw.coords import active_theme
from ..draw.path import polyline
from ..draw.place import place as draw_place
from ..draw.shapes import MARK_LINE_KIND
from ..themes.color import mix
from . import marks as _marks
from .label_spread import label_text

__all__ = ["WaterfallStep", "waterfall_steps", "waterfall", "WATERFALL_KINDS"]

WATERFALL_KINDS = ("increase", "decrease", "total")

#: Total bars, as a blend of the ink towards paper: a neutral grey that is
#: darker than either change colour's lightest tints, so it reads as a
#: different kind of bar rather than a third change.
_TOTAL_TINT = 0.45


@dataclass(frozen=True)
class WaterfallStep:
    """One bar of a waterfall: from `start` to `end`, of `kind` "increase",
    "decrease" or "total". A total starts at the baseline."""
    start: float
    end: float
    kind: str

    @property
    def change(self) -> float:
        """`end - start`: the signed change, or the total's own height."""
        return self.end - self.start


def _number(value, index: int) -> float | None:
    if value is None:
        return None
    number = float(value)
    if math.isnan(number):
        return None
    if not math.isfinite(number):
        raise DiagramError(f"waterfall value {index} is not finite: {value!r}")
    return number


def waterfall_steps(values: Sequence, totals: Sequence[int] = (), *,
                    baseline: float = 0.0) -> list[WaterfallStep]:
    """The bars of a waterfall, without drawing them.

    `values` are signed changes. `totals` lists the indices that are totals
    instead: the bar stands on `baseline` at the running total. A total
    whose value is None shows the running total; a total given a number
    sets the running total to that number, for a reported figure that the
    changes before it do not add up to exactly. Changes may not be None.
    """
    wanted = set(int(i) for i in totals)
    if any(i < 0 or i >= len(values) for i in wanted):
        raise DiagramError(f"waterfall totals {sorted(wanted)} are outside the "
                           f"{len(values)} values")
    running = float(baseline)
    steps = []
    for index, raw in enumerate(values):
        value = _number(raw, index)
        if index in wanted:
            if value is not None:
                running = value
            steps.append(WaterfallStep(float(baseline), running, "total"))
            continue
        if value is None:
            raise DiagramError(
                f"waterfall value {index} is missing; only a total may be None")
        end = running + value
        steps.append(WaterfallStep(running, end,
                                   "increase" if value >= 0 else "decrease"))
        running = end
    return steps


#: OKLCH hues the default increase and decrease colours are chosen near.
_GREEN, _RED = 150.0, 30.0


def _colors(color, theme) -> dict[str, str]:
    default = {"increase": _marks.hue_color(theme, _GREEN),
               "decrease": _marks.hue_color(theme, _RED),
               "total": mix(theme.ink, theme.paper, _TOTAL_TINT)}
    if color is None:
        return default
    if isinstance(color, str):
        return {kind: color for kind in WATERFALL_KINDS}
    if isinstance(color, Mapping):
        unknown = set(color) - set(WATERFALL_KINDS)
        if unknown:
            raise DiagramError(
                f"waterfall color keys are {WATERFALL_KINDS}, not {sorted(unknown)}")
        return {**default, **color}
    given = tuple(color)
    if len(given) != 3:
        raise DiagramError(
            "waterfall color= is one colour, a mapping, or three colours "
            f"(increase, decrease, total), got {len(given)}")
    return dict(zip(WATERFALL_KINDS, given))


def _format(labels, value: float, kind: str) -> str:
    if callable(labels):
        return str(labels(value))
    if isinstance(labels, str):
        return labels.format(value)
    text = f"{value:g}"
    if kind == "increase":
        return "+" + text
    if kind == "decrease":
        return "−" + text.lstrip("-")
    return text


def waterfall(panel, at: Sequence, values: Sequence, *, totals=(),
              baseline: float = 0.0, orient: str = "v", width: float = 0.6,
              color=None, connectors: bool = True, labels=None,
              **style) -> tuple[Diagram, list[WaterfallStep], dict[str, str]]:
    """Draw a waterfall on `panel`. See `Panel.waterfall`.

    Returns `(node, steps, colours by kind)`.
    """
    places = list(at)
    if len(places) != len(values):
        raise DiagramError(
            f"waterfall() got {len(places)} positions for {len(values)} values")
    if not places:
        raise DiagramError("waterfall() was given no values")
    indices = []
    for item in totals or ():
        if isinstance(item, int) and not isinstance(item, bool) and item not in places:
            indices.append(item)
        elif item in places:
            indices.append(places.index(item))
        else:
            raise DiagramError(f"waterfall total {item!r} is not one of the positions")
    steps = waterfall_steps(values, indices, baseline=baseline)
    theme = active_theme()
    fills = _colors(color, theme)
    stroke = style.pop("stroke", None)
    stroke_width = style.pop("stroke_width", None)
    position, scale = _marks._axes_of(panel, orient)
    cells: list = []
    lines: list = []
    written: list = []
    previous = None
    link = {"stroke": mix(theme.ink, theme.paper, 0.35),
            "stroke_width": theme.hairline, "stroke_dash": (0.6, 0.4),
            "stroke_linecap": "butt"}
    size = theme.font_size_small
    clear = theme.gap("xs")
    for where, step in zip(places, steps):
        lo, hi = _marks._slot(position, where, width)
        a, b = scale.map(step.start), scale.map(step.end)
        if abs(b - a) > 1e-12:
            cells.append(_marks._rect(
                _marks._point(orient, (lo + hi) / 2, (a + b) / 2),
                *_marks._extent(orient, hi - lo, abs(b - a)),
                fills[step.kind], stroke, stroke_width))
        if connectors and previous is not None:
            level = scale.map(previous[1])
            lines.append(polyline(
                (_marks._point(orient, previous[0], level),
                 _marks._point(orient, lo, level)), kind=MARK_LINE_KIND, **link))
        previous = (hi, step.end)
        if labels is not None and labels is not False:
            shown = step.end if step.kind == "total" else step.change
            text = label_text(_format(None if labels is True else labels,
                                      shown, step.kind), size)
            box = text.bbox
            # Past the end the change points to: above a rise, below a fall.
            forward = step.kind != "decrease"
            tip = scale.map(step.end)
            sign = (-1.0 if orient == "v" else 1.0) * (1.0 if forward else -1.0)
            reach = (box.height if orient == "v" else box.width) / 2 + clear
            centre = _marks._point(orient, (lo + hi) / 2, tip + sign * reach)
            written.append((centre, text))
    if not cells:
        raise DiagramError("waterfall() had nothing to draw: every bar has zero length")
    node = draw_place(lines + cells + written, **style)
    node.notes["waterfall"] = {
        "steps": tuple((s.start, s.end, s.kind) for s in steps),
        "colors": dict(fills)}
    return node, steps, fills
