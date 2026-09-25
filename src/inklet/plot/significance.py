"""Significance brackets for many pairs of groups at once.

`format_p` turns a p-value into the text a bracket carries, and draws
nothing. `Panel.brackets` takes a list of `(group_a, group_b, p or text)`
comparisons, sorts them so the shortest spans come first and draws each with
`Panel.bracket`. A bracket with no height given clears everything already
drawn between its ends, including the brackets drawn before it, so nested
and overlapping comparisons stack upward in order of span and disjoint ones
stay on the lowest level they fit.

No test is run: the author supplies the p-values.
"""

from __future__ import annotations

import math
from numbers import Real
from typing import Callable, Sequence

from ..core import Diagram, DiagramError

__all__ = ["format_p", "P_FORMATS", "STARS"]

#: Accepted values of `format_p(style=)` and `Panel.brackets(format=)`.
P_FORMATS = ("stars", "p")

#: Upper p-value bounds and their stars, most significant first.
STARS = ((1e-4, "****"), (1e-3, "***"), (1e-2, "**"), (5e-2, "*"))


def format_p(p: float, style: str | Callable = "stars", *,
             stars: Sequence[tuple[float, str]] = STARS, ns: str = "ns",
             smallest: float = 1e-3, digits: int = 2,
             prefix: str = "//P// = ") -> str:
    """A p-value as text: stars or a number.

    `style="stars"` gives the stars of the first bound in `stars` that p is
    below (by default `****` below 0.0001, `***` below 0.001, `**` below
    0.01 and `*` below 0.05) and `ns` otherwise. `style="p"` gives `prefix`
    and p to `digits` significant figures, such as "P = 0.012", or
    "P < 0.001" below `smallest`. The default prefix sets the P in italic
    with inklet's `//italic//` markup. A function of p may be given instead.
    """
    if isinstance(p, bool) or not isinstance(p, Real) or math.isnan(p):
        raise DiagramError(f"a p-value is a number, not {p!r}")
    p = float(p)
    if not 0 <= p <= 1:
        raise DiagramError(f"a p-value is between 0 and 1, got {p!r}")
    if callable(style):
        return str(style(p))
    if style == "stars":
        for bound, text in stars:
            if p < bound:
                return text
        return ns
    if style == "p":
        if p < smallest:
            return prefix.replace("=", "<", 1) + f"{smallest:g}"
        if p == 0:
            return prefix + "0"
        places = max(0, digits - 1 - math.floor(math.log10(p)))
        return prefix + f"{p:.{places}f}"
    raise DiagramError(
        f'p-value format is "stars", "p" or a function, not {style!r}')


def comparisons_in_order(panel, comparisons: Sequence, side: str) -> list:
    """`(a, b, value)` triples sorted by span on the page, shortest first,
    then by the span's start. Spans are measured on x for `side` "n" or
    "s" and on y otherwise."""
    scale = panel.x if side in ("n", "s") else panel.y
    out = []
    for number, item in enumerate(comparisons):
        if not isinstance(item, (tuple, list)) or len(item) != 3:
            raise DiagramError(
                f"a comparison is (group_a, group_b, p or text), not {item!r}")
        a, b, value = item
        lo, hi = sorted((scale.map(a), scale.map(b)))
        out.append((hi - lo, lo, number, (a, b, value)))
    out.sort(key=lambda t: t[:3])
    return [t[3] for t in out]


def label_of(value, style, **options) -> str | Diagram:
    """The bracket text for one comparison: text as given, or a p-value
    formatted by `format_p`."""
    if isinstance(value, (str, Diagram)):
        return value
    return format_p(value, style, **options)


def _leaf_boxes(nodes) -> list:
    """The placed box of every leaf under `nodes`, in panel millimetres."""
    from ..core import group as make_group, resolve

    if not nodes:
        return []
    return [placed.bbox for placed in resolve(make_group(list(nodes))).values()
            if placed.diagram.prim is not None and placed.bbox is not None]


def level(panel, a, b, side: str, clear: float, tick: float) -> float | None:
    """Where the bracket over `a`..`b` goes, in data, or None to leave it to
    `Panel.bracket`.

    `Panel.bracket` keeps `clear` between the bracket line and whatever is
    under it, which lets a tick at a shared end land on the line of the
    bracket below. Here earlier brackets are cleared by `clear` plus the
    tick length, so the ticks of stacked brackets stay clear of each other,
    while the data keeps the ordinary clearance.
    """
    horizontal = side in ("n", "s")
    along = panel.x if horizontal else panel.y
    across = panel.y if horizontal else panel.x
    lo, hi = sorted((along.map(a), along.map(b)))
    eps = 1e-6

    def within(box) -> bool:
        return (box.x1 >= lo - eps and box.x0 <= hi + eps) if horizontal else \
            (box.y1 >= lo - eps and box.y0 <= hi + eps)

    data = [x for x in _leaf_boxes(list(panel._under) + list(panel._content)) if within(x)]
    marks = [x for x in _leaf_boxes(panel._brackets) if within(x)]
    area = panel.area
    if side == "n":
        at = min([area.y1] + [x.y0 - clear for x in data]
                 + [x.y0 - clear - tick for x in marks])
    elif side == "s":
        at = max([area.y0] + [x.y1 + clear for x in data]
                 + [x.y1 + clear + tick for x in marks])
    elif side == "e":
        at = max([area.x0] + [x.x1 + clear for x in data]
                 + [x.x1 + clear + tick for x in marks])
    else:
        at = min([area.x1] + [x.x0 - clear for x in data]
                 + [x.x0 - clear - tick for x in marks])
    try:
        value = across.invert(at)
    except Exception:
        return None
    return value if isinstance(value, (int, float)) else None
