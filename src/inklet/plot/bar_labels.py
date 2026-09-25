"""Value labels on bars and on the segments of stacked bars.

`Panel.bars(labels=...)` calls `bar_labels` with the same arguments it drew
the rectangles with, so every label is positioned from the same slot and span
arithmetic as the rectangle it names (`marks._slot`, `marks._sub_slots`,
`marks._stacked_spans`).

Placement rules:

* `"inside"` centres the label in its rectangle. The label is set in the
  theme ink or the theme paper, whichever has the higher contrast against the
  rectangle's fill.
* `"end"` puts the label just past the far end of the bar (above a positive
  vertical bar, below a negative one) in the theme ink.
* `"auto"` (the default) uses `"inside"` when the label fits inside the
  rectangle with a margin and otherwise `"end"`. For stacked bars only the
  last segment of a stack has a free end, so a segment label that does not
  fit is omitted.

Omitted labels are listed in the returned node's `bar_labels` note, so a test
or a review can find them. Nothing is shrunk: a label is always drawn at the
requested size or not at all.
"""

from __future__ import annotations

from typing import Mapping, Sequence

from ..core import Diagram, DiagramError, mm
from ..draw.coords import active_theme
from ..draw.place import place as draw_place
from . import marks as _marks
from .axis import text_node
from .scale import format_number

__all__ = ["LABEL_POSITIONS", "BAR_LABEL_KIND", "bar_labels", "label_texts"]

#: Accepted values of `Panel.bars(label_position=)`.
LABEL_POSITIONS = ("auto", "inside", "end")

#: Node kind of every bar value label.
BAR_LABEL_KIND = "label"

#: Clear space kept between a label and the two ends of the rectangle it sits
#: in, as a fraction of the label size. Across the bar the label's font box
#: (ascent plus descent, about 1.36 times the size) must fit without margin;
#: the visible glyphs are then about a quarter of the size clear of each edge.
_MARGIN_OF_TYPE = 0.25

#: Gap between the end of a bar and an `"end"` label, as a fraction of the
#: label size.
_END_GAP_OF_TYPE = 0.5


def label_texts(labels, series: Sequence[Sequence[float]]) -> list[list[str | None]]:
    """One string (or None for no label) per value, series-major.

    `labels` is `True` (numbers written with `format_number`), a format string
    containing `{}` such as `"{:.1f}%"`, a callable taking the value, or
    explicit strings in the shape of `heights`: a flat sequence for one series
    or one sequence per series. `None` entries in explicit strings leave that
    value unlabelled.
    """
    if labels is True:
        return [[format_number(v) for v in row] for row in series]
    if isinstance(labels, str):
        if "{" not in labels:
            raise DiagramError(
                'bars(labels=) as a string is a format such as "{:.0f}", '
                f"got {labels!r}")
        return [[labels.format(v) for v in row] for row in series]
    if callable(labels):
        return [[_text_of(labels(v)) for v in row] for row in series]
    given = list(labels)
    if len(series) == 1 and len(given) == len(series[0]) and all(
            item is None or isinstance(item, (str, int, float)) for item in given):
        given = [given]
    if len(given) != len(series) or any(
            len(list(row)) != len(series[0]) for row in given):
        raise DiagramError(
            "bars(labels=) needs one label per value, in the shape of heights")
    return [[_text_of(item) for item in row] for row in given]


def _text_of(item) -> str | None:
    if item is None:
        return None
    return item if isinstance(item, str) else format_number(float(item))


def bar_labels(panel, at: Sequence, heights, *, labels, position: str = "auto",
               width: float = 0.8, baseline: float = 0.0, orient: str = "v",
               stacked: bool | None = None, grouped: bool | None = None,
               gap: float = 0.12, fills: Sequence[str] | None = None,
               bar_fills: Sequence[str] | None = None,
               options: Mapping | None = None) -> Diagram | None:
    """Labels for the rectangles `marks.bars` drew with the same arguments.

    `fills` is one colour per series and `bar_fills` one per category; they
    pick the ink/paper choice for inside labels. `options` accepts `size`
    (mm), `fill` (a fixed text colour), `markup` (default False) and
    `font_weight`. The text itself comes from `labels=`.
    """
    if position not in LABEL_POSITIONS:
        raise DiagramError(
            f"label_position is one of {', '.join(LABEL_POSITIONS)}, "
            f"not {position!r}")
    options = dict(options or {})
    unknown = set(options) - {"size", "fill", "markup", "font_weight"}
    if unknown:
        raise DiagramError(
            f"label_options accepts size, fill, markup and font_weight; "
            f"got {', '.join(sorted(unknown))}")
    theme = active_theme()
    size = theme.font_size_small if options.get("size") is None else mm(options["size"])
    markup = bool(options.get("markup", False))
    fixed = options.get("fill")
    weight = options.get("font_weight")
    places = list(at)
    series = _marks._series(heights)
    texts = label_texts(labels, series)
    if len(series) > 1 and not stacked:
        grouped = True
    position_scale, value_scale = _marks._axes_of(panel, orient)
    margin = _MARGIN_OF_TYPE * size
    end_gap = _END_GAP_OF_TYPE * size
    placed: list = []
    omitted: list[dict] = []
    for index, where in enumerate(places):
        lo, hi = _marks._slot(position_scale, where, width)
        slots = (_marks._sub_slots(lo, hi, len(series), gap) if grouped
                 else [(lo, hi)] * len(series))
        spans = (_marks._stacked_spans(series, index, baseline) if stacked
                 else [(baseline, row[index]) for row in series])
        last = _last_nonzero(series, index) if stacked else None
        for s, (bottom, top) in enumerate(spans):
            text = texts[s][index]
            if text is None or text == "":
                continue
            a, b = value_scale.map(bottom), value_scale.map(top)
            p0, p1 = slots[s]
            along = abs(p1 - p0)
            length = abs(b - a)
            paint = (bar_fills[index] if bar_fills is not None
                     else fills[s] if fills is not None else theme.ink)
            style = {} if weight is None else {"font_weight": weight}
            probe = text_node(text, size, BAR_LABEL_KIND, markup=markup, **style)
            box = probe.bbox
            tw, th = (box.width, box.height)
            need_along, need_length = (tw, th) if orient == "v" else (th, tw)
            if orient == "v":
                fits = (need_along + 2 * margin <= along
                        and need_length <= length)
            else:
                fits = (need_along <= along
                        and need_length + 2 * margin <= length)
            where_to = position
            if stacked and position == "end" and s != last:
                continue                # only the stack's free end has room
            if position == "auto":
                if fits:
                    where_to = "inside"
                elif not stacked or s == last:
                    where_to = "end"
                else:
                    omitted.append({"category": _plain(where), "series": s,
                                    "text": text})
                    continue
            centre_along = (p0 + p1) / 2
            if where_to == "inside":
                ink = fixed or _ink_on(paint, theme)
                centre = _marks._point(orient, centre_along, (a + b) / 2)
                anchor = "center"
            else:
                ink = fixed or theme.ink
                # The far end of the bar: the end away from the baseline,
                # which for a stack is the end of the whole stack.
                tip = b if not stacked else _stack_tip(value_scale, spans, series, index, top >= bottom)
                base = value_scale.map(baseline)
                outward = 1.0 if tip >= base else -1.0
                centre = _marks._point(orient, centre_along, tip + outward * end_gap)
                anchor = _end_anchor(orient, outward)
            node = text_node(text, size, BAR_LABEL_KIND, markup=markup,
                             **style).styled(text_fill=ink)
            placed.append((centre, node, anchor))
    if not placed:
        return None
    groups = {}
    for centre, node, anchor in placed:
        groups.setdefault(anchor, []).append((centre, node))
    parts = [draw_place(items, anchor=anchor, origin=(0, 0), kind="bar-labels")
             for anchor, items in groups.items()]
    out = parts[0] if len(parts) == 1 else draw_place(parts, origin=(0, 0),
                                                      kind="bar-labels")
    out.notes["bar_labels"] = {"drawn": len(placed), "omitted": omitted}
    return out


def _last_nonzero(series, index: int) -> int | None:
    """The series index of the segment at the free end of a stack.

    Only positive stacks are considered: a mixed-sign stack has two free
    ends, and the positive one is the one the total is read from.
    """
    last = None
    for s, row in enumerate(series):
        if row[index] > 0:
            last = s
    if last is None:
        for s, row in enumerate(series):
            if row[index] < 0:
                last = s
    return last


def _stack_tip(value_scale, spans, series, index: int, positive: bool) -> float:
    ends = [top if positive else bottom for (bottom, top), row in zip(spans, series)
            if (row[index] > 0) == positive and row[index] != 0]
    edge = (max if positive else min)(ends) if ends else spans[-1][1]
    return value_scale.map(edge)


def _end_anchor(orient: str, outward: float) -> str:
    """Which side of the label sits on the end point.

    Panel y grows downward on the page, so a mapped value that increases
    means the bar grows downward on the page for vertical bars.
    """
    if orient == "v":
        return "n" if outward > 0 else "s"
    return "w" if outward > 0 else "e"


def _ink_on(fill: str, theme) -> str:
    """Theme ink or paper, whichever reads on `fill` (`Theme.text_on`)."""
    try:
        return theme.text_on(fill)
    except (ValueError, TypeError):
        return theme.ink


def _plain(value):
    return value if isinstance(value, (str, int, float)) else repr(value)
