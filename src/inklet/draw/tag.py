"""Measured colored labels for diagrams and scientific illustrations."""
from __future__ import annotations
import math
from numbers import Real
from dataclasses import replace
from ..core import Diagram, mm


def tag(content: str | Diagram, *, size=None, font=None, weight=None,
        color: str | None = None, fill: str | None = None,
        pad=(0.9, 0.35), radius=0.3, stroke="none", stroke_width=0.15,
        markup: bool = True) -> Diagram:
    """A label plate sized from shaped text, with no font stretching.

    ``pad`` is one length or ``(horizontal, vertical)`` lengths, in mm.
    A Diagram can supply richly styled content. Text color is chosen for
    contrast against ``fill`` unless stated. All text remains editable.
    ``size``, ``font`` and ``weight`` apply to string content only.
    """
    from .. import text, current_theme, box
    from ..layout import pad as padding
    from ..themes import contrast_ratio
    if not isinstance(content, (str, Diagram)):
        raise TypeError("tag content must be text or a Diagram")
    if isinstance(content, Diagram) and any(v is not None for v in (size, font, weight)):
        raise ValueError("tag size, font and weight apply to string content; style the Diagram first")
    if isinstance(pad, (str, Real)):
        px = py = mm(pad)
    else:
        try:
            px, py = (mm(v) for v in pad)
        except (TypeError, ValueError):
            raise ValueError("tag pad must be a length or (horizontal, vertical)") from None
    r = mm(radius)
    sw = mm(stroke_width)
    if not all(math.isfinite(v) and v >= 0 for v in (px, py, r, sw)):
        raise ValueError("tag padding, radius and stroke_width must be finite and non-negative")
    background = fill or current_theme().accent
    ink = color or max(("#111111", "#ffffff"), key=lambda c: contrast_ratio(c, background))
    inner = text(content, size=size, font=font, weight=weight, markup=markup,
                 text_fill=ink) if isinstance(content, str) else content
    node = box(padding(inner, py, px), pad=0, radius=r,
               fill=background, stroke=stroke, stroke_width=sw)
    node = replace(node, kind="label-tag")
    node.notes['tag'] = dict(padding=(px, py), text_width=inner.bbox.width,
                             text_height=inner.bbox.height)
    return node
