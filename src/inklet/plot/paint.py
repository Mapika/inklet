"""The paint keywords a plotting mark takes, checked where they are written.

Every data method of `Panel` ends in `**style`, and that dictionary travels
down to a `Style` built long after the call: in a `plot_spec` recipe, when the
document compiles. A misspelt keyword used to surface there, as
`Style.__init__() got an unexpected keyword argument`, with no hint of which
call wrote it or what it should have said. `paint_keywords` checks the
keywords against `Style`'s fields when the method is called -- and, through
`__style_check__`, when a recipe records the call -- and names the fix.

It also reads `dash=`: a named pattern (`DASHES`) or a tuple of millimetres,
given to the mark as `stroke_dash`. `DASHES` is the one table of named dash
patterns; the chart API imports it from here.
"""

from __future__ import annotations

import difflib
import functools
import inspect
import math
from dataclasses import fields
from typing import Callable

from ..core.style import Style

__all__ = ["DASHES", "dash_pattern", "check_style", "is_paint", "keyword_hint",
           "paint_keywords"]

#: Named dash patterns, as `(on, off, ...)` lengths in millimetres.
#: "solid" is accepted too and means no dash.
DASHES: dict[str, tuple[float, ...]] = {
    "dashed": (1.6, 0.8),
    "dotted": (0.3, 0.6),
    "dashdot": (1.6, 0.6, 0.3, 0.6),
}

_STYLE_FIELDS = frozenset(f.name for f in fields(Style))

#: Keywords a mark's `**style` may carry that are not paint: they are read on
#: the way down (`clip` by the panel, `color` as the mark's one paint, `edges`
#: by the box and violin marks, the rest by `inklet.draw.path` and
#: `inklet.draw.place`).
_PASSED_THROUGH = frozenset({
    "clip", "color", "dash", "edges", "kind", "anchor", "origin", "closed", "curves",
    "holes", "filled", "fill_rule",
})

#: Spellings from other plotting libraries, and what inklet calls them.
_FOREIGN = {
    "linewidth": "stroke_width", "lw": "stroke_width", "width": "stroke_width",
    "linestyle": "dash", "ls": "dash", "alpha": "opacity",
    "edgecolor": "stroke", "ec": "stroke", "facecolor": "fill", "fc": "fill",
    "c": "color", "colour": "color", "markersize": "size", "ms": "size",
    "label": "name", "zorder": "front", "dashes": "dash",
}


def dash_pattern(value) -> tuple[float, ...] | None:
    """`dash=` as `stroke_dash`: a name in `DASHES`, "solid"/None, or lengths in mm."""
    if value is None or value == "solid":
        return None
    if isinstance(value, str):
        if value in DASHES:
            return DASHES[value]
        raise ValueError(
            f"unknown dash {value!r}; use one of {', '.join(map(repr, DASHES))}, "
            "'solid', or a tuple of (on, off) lengths in mm")
    try:
        pattern = tuple(float(v) for v in value)
    except (TypeError, ValueError):
        raise ValueError(
            f"dash= is a pattern name or a tuple of lengths in mm, not {value!r}"
        ) from None
    if not pattern or any(not math.isfinite(v) or v < 0 for v in pattern) \
            or not any(pattern):
        raise ValueError(
            f"dash= lengths must be finite, non-negative and not all zero, got {value!r}")
    return pattern


def is_paint(name: str) -> bool:
    """Whether `name` is a keyword a mark may take as paint: a Style field or a pass-through."""
    return name in _STYLE_FIELDS or name in _PASSED_THROUGH


def keyword_hint(name: str, candidates=()) -> str | None:
    """The spelling `name` was probably meant to be: a foreign name, or a close match.

    `candidates` are further valid names for the caller's own keywords.
    """
    better = _FOREIGN.get(name)
    if better is None:
        close = difflib.get_close_matches(
            name, sorted(_STYLE_FIELDS | _PASSED_THROUGH | set(candidates)), n=1, cutoff=0.75)
        better = close[0] if close else None
    return better


def check_style(where: str, style: dict) -> None:
    """Raise a `TypeError` naming any keyword in `style` that is not paint."""
    unknown = sorted(k for k in style if not is_paint(k))
    if not unknown:
        return
    hints = []
    for key in unknown:
        better = keyword_hint(key)
        hints.append(f"{key}= (did you mean {better}=?)" if better else f"{key}=")
    raise TypeError(
        f"{where}() got unknown keyword{'s' if len(unknown) > 1 else ''} "
        f"{', '.join(hints)}; its paint keywords are Style fields such as "
        "stroke, stroke_width, stroke_dash, fill, opacity, plus color= and "
        "dash= ('dashed', 'dotted', 'dashdot' or (on, off) in mm)")


def paint_keywords(func: Callable) -> Callable:
    """Check a mark's `**style` at the call and read its `dash=` keyword.

    The wrapper keeps the method's signature, so recipes still bind against
    it, and exposes `__style_check__(kwargs)` for a recorder to run the same
    check when the call is written rather than when it is replayed.
    """
    named = frozenset(inspect.signature(func).parameters)
    title = func.__name__

    def check(kwargs) -> None:
        style = {k: v for k, v in kwargs.items() if k not in named}
        check_style(title, style)
        if "dash" in style:
            if "stroke_dash" in style:
                raise TypeError(f"{title}() got both dash= and stroke_dash=")
            dash_pattern(style["dash"])
        if isinstance(style.get("stroke_dash"), str):
            dash_pattern(style["stroke_dash"])

    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        check(kwargs)
        if "dash" in kwargs and "dash" not in named:
            pattern = dash_pattern(kwargs.pop("dash"))
            if pattern is not None:
                kwargs["stroke_dash"] = pattern
        elif isinstance(kwargs.get("stroke_dash"), str):
            # stroke_dash="dashed" is the same wish in the other spelling.
            pattern = dash_pattern(kwargs.pop("stroke_dash"))
            if pattern is not None:
                kwargs["stroke_dash"] = pattern
        return func(self, *args, **kwargs)

    wrapper.__style_check__ = check
    return wrapper
