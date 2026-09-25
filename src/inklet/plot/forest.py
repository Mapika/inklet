"""Forest plots: one estimate and confidence interval per study or subgroup.

`forest_layout` reads the rows and draws nothing. A row is a study (a point
estimate with its interval), a summary (drawn as a diamond) or a group header
(a label with no estimate). It returns the rows, the x limits and which
intervals run past those limits.

`forest` draws the layout as one panel with a row per entry, top to bottom:
a square per study, sized by its weight when weights are given, on a
horizontal interval line; a diamond per summary, spanning its interval; and a
vertical line at the value of no effect, 1 on a log axis (odds and hazard
ratios) and 0 on a linear one. An interval that runs past the x limits stops
at the limit with an arrowhead. Text columns (the study name, the estimate
formatted as "0.82 (0.61–1.10)", n or any other value) are set left and right
of the plot, one line per row, with an optional header line above them.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from numbers import Real
from typing import Callable, Mapping, Sequence

from ..core import Diagram, DiagramError, Vec2, mm
from ..draw.coords import active_theme
from ..draw.path import polygon, polyline
from ..draw.place import place as draw_place
from ..draw.shapes import (MARK_KIND, MARK_LINE_KIND, _SQUARE_SIDE,
                           marker as make_marker)
from .axis import TICK_LABEL_KIND, text_node
from .scale import linear, log as log_scale, nice_bounds

__all__ = ["forest", "forest_layout", "ForestRow", "ForestLayout",
           "FOREST_KINDS", "FOREST_KEYS"]

#: The kinds of row: a study with an interval, a summary drawn as a diamond,
#: and a group header with a label only.
FOREST_KINDS = ("study", "summary", "header")

#: Column keys every row answers: its label, the estimate and interval as
#: text, the estimate alone, and the weight.
FOREST_KEYS = ("label", "ci", "estimate", "weight")

#: Default row pitch as a multiple of the small type size.
_PITCH_OF_TYPE = 1.6

#: Study square side, in mm: the largest weight gets `_SQUARE_MAX`, others
#: an area in proportion, but never less than `_SQUARE_MIN`. Without weights
#: every square is `_SQUARE`.
_SQUARE = 1.3
_SQUARE_MIN = 0.7
_SQUARE_MAX = 2.4

#: Half the height of a summary diamond, as a fraction of the row pitch.
_DIAMOND_OF_PITCH = 0.3

#: An arrowhead at a clipped interval end: its length and half-width in mm.
_HEAD_LENGTH = 1.0
_HEAD_HALF = 0.55

#: How far a label under a group header is indented, as a multiple of the
#: small type size.
_INDENT_OF_TYPE = 0.8


@dataclass(frozen=True)
class ForestRow:
    """One line of a forest plot.

    `kind` is "study", "summary" or "header". A study or summary has an
    `estimate` and an interval from `low` to `high`; a header has none.
    `weight` sizes a study's square. `values` holds any further columns by
    key, such as `{"n": 412}`. `indent` is set by `forest_layout` for rows
    that follow a header.
    """
    label: str
    estimate: float | None = None
    low: float | None = None
    high: float | None = None
    weight: float | None = None
    kind: str = "study"
    values: Mapping = field(default_factory=dict)
    indent: bool = False


@dataclass(frozen=True)
class ForestLayout:
    """`rows` top to bottom, the x `limits`, the value of `null` (no
    effect), whether the axis is `log`, and `clipped`: `(row index, side)`
    for each interval end past the limits, side "low" or "high"."""
    rows: tuple[ForestRow, ...]
    limits: tuple[float, float]
    null: float
    log: bool
    clipped: tuple[tuple[int, str], ...]


def _missing(value) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value))


def _row(item) -> ForestRow:
    """One input row as a `ForestRow`."""
    if isinstance(item, ForestRow):
        return item
    if isinstance(item, str):
        return ForestRow(label=item, kind="header")
    if isinstance(item, Mapping):
        data = dict(item)
        if "label" not in data:
            raise DiagramError(f"forest row {item!r} has no label")
        kind = data.pop("kind", None)
        if data.pop("header", False):
            kind = "header"
        if data.pop("summary", False):
            kind = "summary"
        fields = {k: data.pop(k) for k in ("label", "estimate", "low", "high",
                                           "weight") if k in data}
        return ForestRow(kind=kind or "study", values=data, **fields)
    if isinstance(item, (tuple, list)) and 1 <= len(item) <= 5:
        if len(item) == 1:
            return ForestRow(label=item[0], kind="header")
        if len(item) < 4:
            raise DiagramError(
                f"forest row {item!r} is (label, estimate, low, high[, weight])")
        return ForestRow(*item)
    raise DiagramError(
        "a forest row is a ForestRow, a mapping, a (label, estimate, low, "
        f"high[, weight]) tuple or a header string, not {item!r}")


def _checked(row: ForestRow, log: bool) -> ForestRow:
    if row.kind not in FOREST_KINDS:
        raise DiagramError(
            f"forest row kind is one of {', '.join(FOREST_KINDS)}, not {row.kind!r}")
    if row.kind == "header":
        return row
    values = (row.estimate, row.low, row.high)
    if any(_missing(v) for v in values):
        raise DiagramError(
            f"forest row {row.label!r} needs an estimate, a low and a high value")
    estimate, low, high = (float(v) for v in values)
    if not low <= estimate <= high:
        raise DiagramError(
            f"forest row {row.label!r}: the interval {low:g} to {high:g} does "
            f"not contain the estimate {estimate:g}")
    if log and low <= 0:
        raise DiagramError(
            f"forest row {row.label!r} has a value of 0 or less, which a log "
            "axis cannot show")
    weight = row.weight
    if not _missing(weight):
        weight = float(weight)
        if weight < 0:
            raise DiagramError(f"forest row {row.label!r} has a negative weight")
    else:
        weight = None
    return ForestRow(label=str(row.label), estimate=estimate, low=low, high=high,
                     weight=weight, kind=row.kind, values=dict(row.values),
                     indent=row.indent)


def _log_bounds(lo: float, hi: float) -> tuple[float, float]:
    """The 1-2-5 values at or outside `lo` and `hi`."""
    def down(v: float) -> float:
        power = 10.0 ** math.floor(math.log10(v) + 1e-12)
        return max(f * power for f in (1.0, 2.0, 5.0) if f * power <= v * (1 + 1e-9))

    def up(v: float) -> float:
        power = 10.0 ** math.floor(math.log10(v) - 1e-12)
        return min(f * power for f in (1.0, 2.0, 5.0, 10.0) if f * power >= v * (1 - 1e-9))

    return down(lo), up(hi)


def forest_layout(rows: Sequence, *, log: bool = False,
                  limits: tuple[float, float] | None = None,
                  null: float | None = None) -> ForestLayout:
    """The rows, limits and clipped interval ends of a forest plot, without
    drawing.

    Each row is a `ForestRow`; a mapping with `label`, `estimate`, `low`,
    `high` and optionally `weight`, `kind` (or `summary=True`,
    `header=True`) and any other keys, which become column values; a tuple
    `(label, estimate, low, high[, weight])`; or a bare string, which is a
    group header. Rows after a header are indented until the next header or
    summary.

    `log=True` puts x on a log axis; `null` defaults to 1 there and to 0 on a
    linear axis. `limits` fixes the x range; interval ends outside it are
    listed in `clipped`. Without it the range is the smallest round range
    that holds every interval and the null value.
    """
    parsed = [_checked(_row(item), log) for item in rows]
    if not parsed:
        raise DiagramError("forest was given no rows")
    if all(r.kind == "header" for r in parsed):
        raise DiagramError("forest has no rows with an estimate")
    # Rows after a header are indented; a summary is not, and closes the
    # group, so an overall summary after the last subtotal lines up with the
    # headers.
    indented: list[ForestRow] = []
    grouped = False
    for row in parsed:
        if row.kind == "header":
            grouped = True
        elif row.kind == "summary":
            grouped = False
        indented.append(ForestRow(**{**row.__dict__, "indent": row.indent or (
            grouped and row.kind == "study")}))
    base = (1.0 if log else 0.0) if null is None else float(null)
    if log and base <= 0:
        raise DiagramError(f"forest null must be positive on a log axis, got {base!r}")
    if limits is None:
        lows = [r.low for r in indented if r.kind != "header"] + [base]
        highs = [r.high for r in indented if r.kind != "header"] + [base]
        lo, hi = min(lows), max(highs)
        if log:
            lo, hi = _log_bounds(lo, hi)
            if hi <= lo:
                hi = lo * 10
        else:
            if hi == lo:
                lo, hi = lo - 1, hi + 1
            lo, hi = nice_bounds(lo, hi, 4)
    else:
        lo, hi = (float(v) for v in limits)
        if not hi > lo:
            raise DiagramError(f"forest limits must run low to high, got {limits!r}")
        if log and lo <= 0:
            raise DiagramError(f"forest limits must be positive on a log axis, got {limits!r}")
    clipped: list[tuple[int, str]] = []
    for index, row in enumerate(indented):
        if row.kind == "header":
            continue
        if row.low < lo:
            clipped.append((index, "low"))
        if row.high > hi:
            clipped.append((index, "high"))
    return ForestLayout(rows=tuple(indented), limits=(lo, hi), null=base,
                        log=log, clipped=tuple(clipped))


def _number(value, digits: int) -> str:
    if value is None:
        return ""
    if isinstance(value, bool) or not isinstance(value, Real):
        return str(value)
    if float(value).is_integer() and abs(value) < 1e15 and isinstance(value, int):
        return str(value)
    return f"{float(value):.{digits}f}"


def _column(spec, measure: str, digits: int) -> tuple[str, Callable, str]:
    """`(header, text of a row, align)` for one column spec."""
    align = None
    if isinstance(spec, str):
        header, key = None, spec
    elif isinstance(spec, (tuple, list)) and len(spec) in (2, 3):
        header, key = spec[0], spec[1]
        if len(spec) == 3:
            align = spec[2]
    else:
        raise DiagramError(
            "a forest column is a key or a (header, key or function[, align]) "
            f"tuple, not {spec!r}")
    if align not in (None, "left", "right"):
        raise DiagramError(f'forest column align is "left" or "right", not {align!r}')
    if callable(key):
        function = key

        def text(row: ForestRow) -> str:
            value = function(row)
            return "" if value is None else str(value)

        return ("" if header is None else str(header)), text, align or "right"

    def text(row: ForestRow) -> str:
        if key == "label":
            return row.label
        if row.kind == "header":
            return ""
        if key == "ci":
            return (f"{row.estimate:.{digits}f} "
                    f"({row.low:.{digits}f}\u2013{row.high:.{digits}f})")
        if key == "estimate":
            return f"{row.estimate:.{digits}f}"
        if key == "weight":
            return "" if row.weight is None else f"{row.weight:g}"
        return _number(row.values.get(key), digits)

    defaults = {"label": "Study", "ci": f"{measure} (95% CI)",
                "estimate": measure, "weight": "Weight"}
    if header is None:
        header = defaults.get(key, str(key))
    return str(header), text, align or ("left" if key == "label" else "right")


def forest(rows: Sequence, *, log: bool = False,
           limits: tuple[float, float] | None = None, null: float | None = None,
           left: Sequence = ("label",), right: Sequence = ("ci",),
           headers: bool = True, measure: str = "Estimate", digits: int = 2,
           label: str | None = None, ticks: Sequence[float] | None = None,
           width: float | str = 36, row_height: float | str | None = None,
           color: str | None = None, summary_color: str | None = None,
           size: float | str | None = None, summary_line: bool = False,
           gap: float | str | None = None, count: int = 5) -> Diagram:
    """A forest plot: one estimate and confidence interval per row, with
    aligned text columns beside it.

        inklet.forest([
            "Adults",
            {"label": "Ahmed 2019", "estimate": 0.72, "low": 0.55, "high": 0.94,
             "weight": 18.2, "n": 812},
            {"label": "Berg 2020", "estimate": 0.91, "low": 0.62, "high": 1.33,
             "weight": 9.4, "n": 355},
            {"label": "Overall", "estimate": 0.79, "low": 0.66, "high": 0.95,
             "summary": True},
        ], log=True, measure="OR", right=["ci", "n"], label="Odds ratio")

    Rows are listed top to bottom; see `forest_layout` for the accepted row
    forms. A study is a square on its interval line, a summary a diamond
    across its interval, and a header a label in bold with the rows after it
    indented. The squares are all `size` mm across, or, when rows carry
    weights, sized so their areas follow the weights (largest 2.4 mm).

    `log=True` uses a log x axis and puts the line of no effect at 1;
    otherwise it is at 0. `null=` moves it. `limits=(low, high)` fixes the x
    range, and an interval that runs past it ends in an arrowhead at the
    limit; a square outside the range is not drawn. `ticks=` sets the tick
    values and `label` names the axis.

    `left` and `right` are the text columns on each side of the plot, from
    left to right. A column is a key -- `"label"`, `"ci"` (the estimate and
    interval as "0.72 (0.55–0.94)", with `digits` decimals), `"estimate"`,
    `"weight"` or any key of the row mappings -- or a tuple `(header, key)`
    or `(header, function of the ForestRow)`, optionally with `"left"` or
    `"right"` alignment as a third item. The label column is left-aligned
    and the others right-aligned. `headers=True` writes a header line over
    the columns; `measure` is used in the default headers ("OR (95% CI)").

    `width` is the plot width and `row_height` the pitch of the rows in mm
    (default 1.6 times the small type size). `color` is the ink of the
    studies and `summary_color` of the diamonds. `summary_line=True` draws a
    dashed line at the last summary's estimate. `gap` is the space between
    columns.

    Returns one diagram whose plot area is the rows (including the header
    line), so `letters` and `row` place it like a panel. It carries a
    `forest` note with the limits, the null value and the clipped ends.
    """
    layout = forest_layout(rows, log=log, limits=limits, null=null)
    from .panel import panel

    theme = active_theme()
    small = theme.font_size_small
    pitch = _PITCH_OF_TYPE * small if row_height is None else mm(row_height)
    if pitch <= 0:
        raise DiagramError("forest row_height must be positive")
    space = theme.gap("s") if gap is None else mm(gap)
    ink = color or theme.ink
    summary_ink = summary_color or ink
    lead = 1 if headers else 0
    count_rows = len(layout.rows)
    lo, hi = layout.limits
    scale = log_scale((lo, hi)) if layout.log else linear((lo, hi))
    # Row k sits at y = k, top to bottom; the header line at -1.
    p = panel(width, pitch * (count_rows + lead), x=scale,
              y=linear((count_rows - 0.5, -0.5 - lead)))
    area = p.area

    def at(index: float) -> float:
        return p.y.map(index)

    # The line of no effect, over the data rows only.
    top, bottom = at(-0.5), at(count_rows - 0.5)
    x_null = p.x.map(layout.null)
    under = [polyline(((x_null, top), (x_null, bottom)), kind=MARK_LINE_KIND,
                      stroke=theme.muted, stroke_width=theme.stroke)]
    if summary_line:
        summaries = [r for r in layout.rows if r.kind == "summary"]
        if summaries and lo <= summaries[-1].estimate <= hi:
            x_sum = p.x.map(summaries[-1].estimate)
            under.append(polyline(((x_sum, top), (x_sum, bottom)),
                                  kind=MARK_LINE_KIND, stroke=summary_ink,
                                  stroke_width=theme.hairline,
                                  stroke_dash=(1.0, 0.8)))
    p.under(draw_place(under, origin=(0, 0), kind="forest-reference"), clip=False)

    weights = [r.weight for r in layout.rows
               if r.kind == "study" and r.weight is not None]
    biggest = max(weights) if weights else 0.0
    fixed = _SQUARE if size is None else mm(size)
    clipped = set(layout.clipped)
    items: list = []
    for index, row in enumerate(layout.rows):
        if row.kind == "header":
            continue
        y = at(index)
        low = max(row.low, lo)
        high = min(row.high, hi)
        xa, xb = p.x.map(low), p.x.map(high)
        cut_low, cut_high = (index, "low") in clipped, (index, "high") in clipped
        if row.kind == "summary":
            half = _DIAMOND_OF_PITCH * pitch
            inside = lo <= row.estimate <= hi
            xe = p.x.map(min(max(row.estimate, lo), hi))
            a = xa + (_HEAD_LENGTH if cut_low else 0.0)
            b = xb - (_HEAD_LENGTH if cut_high else 0.0)
            if inside:
                items.append(polygon(((a, y), (xe, y - half), (b, y), (xe, y + half)),
                                     kind=MARK_KIND, fill=summary_ink, stroke="none"))
            else:
                items.append(polyline(((a, y), (b, y)), kind=MARK_LINE_KIND,
                                      stroke=summary_ink, stroke_width=theme.stroke))
            for cut, tip, sign in ((cut_low, xa, -1.0), (cut_high, xb, 1.0)):
                if cut:
                    items.append(_head(tip, y, sign, summary_ink))
            continue
        a = xa + (_HEAD_LENGTH if cut_low else 0.0)
        b = xb - (_HEAD_LENGTH if cut_high else 0.0)
        if b > a:
            items.append(polyline(((a, y), (b, y)), kind=MARK_LINE_KIND,
                                  stroke=ink, stroke_width=theme.stroke,
                                  stroke_linecap="butt"))
        for cut, tip, sign in ((cut_low, xa, -1.0), (cut_high, xb, 1.0)):
            if cut:
                items.append(_head(tip, y, sign, ink))
        if lo <= row.estimate <= hi:
            if row.weight is not None and biggest > 0:
                side = max(_SQUARE_MIN, _SQUARE_MAX * math.sqrt(row.weight / biggest))
            else:
                side = fixed
            items.append((Vec2(p.x.map(row.estimate), y),
                          make_marker("square", side / _SQUARE_SIDE, fill=ink,
                                      stroke="none")))
    p.draw(draw_place(items, origin=(0, 0), kind="forest"), clip=False)
    p.axis("bottom", label=label, ticks=ticks, count=count)

    # Text columns: one node per row, set flush left or flush right in a
    # column as wide as its widest entry.
    indent = _INDENT_OF_TYPE * small
    texts: list = []

    def cells(column) -> tuple[list, Diagram | None, float]:
        header, text, align = column
        found = []
        for index, row in enumerate(layout.rows):
            content = text(row)
            if not content:
                continue
            is_label = content == row.label
            bold = is_label and row.kind in ("header", "summary")
            node = text_node(content, small, TICK_LABEL_KIND, markup=False,
                             features={"tnum": True},
                             **({"font_weight": "bold"} if bold else {}))
            shift = indent if (row.indent and is_label and align == "left") else 0.0
            found.append((index, node, shift))
        head = (text_node(header, small, TICK_LABEL_KIND, markup=False,
                          font_weight="bold") if headers and header else None)
        widest = max([n.bbox.width + s for _, n, s in found]
                     + ([head.bbox.width] if head is not None else []), default=0.0)
        return found, head, widest

    def set_column(column, found, head, x0: float, span: float) -> None:
        align = column[2]
        for index, node, shift in found + ([(-1, head, 0.0)] if head is not None else []):
            w = node.bbox.width
            cx = x0 + shift + w / 2 if align == "left" else x0 + span - w / 2
            texts.append((Vec2(cx, at(index)), node))

    cursor = area.x0 - space
    for column in reversed([_column(c, measure, digits) for c in left]):
        found, head, span = cells(column)
        set_column(column, found, head, cursor - span, span)
        cursor -= span + space
    cursor = area.x1 + space
    for column in [_column(c, measure, digits) for c in right]:
        found, head, span = cells(column)
        set_column(column, found, head, cursor, span)
        cursor += span + space
    if texts:
        p.over(draw_place(texts, origin=(0, 0), kind="forest-columns"), clip=False)
    node = p.build()
    node.notes["forest"] = {"limits": layout.limits, "null": layout.null,
                            "log": layout.log, "clipped": list(layout.clipped),
                            "rows": [(r.kind, r.label) for r in layout.rows]}
    return node


def _head(tip: float, y: float, sign: float, ink: str) -> Diagram:
    """An arrowhead with its tip at `(tip, y)`, pointing left (-1) or right."""
    base = tip - sign * _HEAD_LENGTH
    return polygon(((tip, y), (base, y - _HEAD_HALF), (base, y + _HEAD_HALF)),
                   kind=MARK_KIND, fill=ink, stroke="none")
