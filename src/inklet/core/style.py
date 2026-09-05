"""Visual attributes. Every field is optional and None means "inherit".

Values here are literals; the theme layer is what turns tokens into them. Code
outside `inklet.themes` should be reading tokens, not hardcoding colours.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, fields, replace

from .units import UnitError, mm

_DASH_SPLIT = re.compile(r"[,\s]+")

# Lengths in millimetres: a bare number, or anything `mm()` parses ("0.5mm",
# "1pt"). Ratios are bare numbers only.
_LENGTH_FIELDS = ("stroke_width", "corner_radius", "font_size", "halo")
_RATIO_FIELDS = ("opacity", "line_height", "fill_opacity", "stroke_opacity")

#: The upright/slanted axis, spelled as CSS spells it. `oblique` is left out:
#: it is a synthetic slant of the upright face, and everything here is measured
#: in a real face that the typesetter resolved.
FONT_STYLES = ("normal", "italic")


class StyleError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Style:
    fill: str | None = None
    stroke: str | None = None
    stroke_width: float | None = None          # mm
    stroke_dash: tuple[float, ...] | None = None  # mm
    stroke_linecap: str | None = None
    stroke_linejoin: str | None = None
    opacity: float | None = None
    # Opacity of the fill and of the stroke on their own. None means "follow
    # `opacity`", which is what every node written so far wants and what a
    # backend already does. Set one and the two stop moving together: a
    # confidence band is a 20% fill under a solid line, which as a single
    # `opacity` needs two nodes drawn on top of each other -- and the second
    # node is what makes the linter read one band as two overlapping shapes.
    # These multiply with `opacity` rather than replacing it, as SVG and PDF
    # both define them, so a group that fades to 50% still fades the band.
    fill_opacity: float | None = None
    stroke_opacity: float | None = None
    # Duplicates `RectPrim.radius`, and only the prim feeds `trace()`. The
    # rule, since two backends had to guess it: the prim wins where it says
    # anything, and this is the fallback for a rect that did not. So
    # `.styled(corner_radius=3)` rounds what is drawn without moving what
    # arrows aim at -- use `RectPrim(radius=)` when the geometry is the point.
    corner_radius: float | None = None         # mm
    font_family: str | None = None
    font_size: float | None = None             # mm; use units.pt() at call sites
    font_weight: str | None = None
    # "normal" or "italic". A companion to `font_weight`, and needed for the
    # same reason: the block was measured in whichever face the typesetter
    # resolved, and a live `<text>` that cannot say which one it was gets
    # re-shaped by the viewer inside a box built for another. Without it a
    # theme could set a role bold but not italic. Inline `//italic//` is
    # unaffected -- that travels per run, as a face.
    font_style: str | None = None
    # Only a TextPrim reads this. Inherited onto a group it would repaint every
    # shape under it, so a group that wants coloured text sets `fill`.
    text_fill: str | None = None
    # Advisory only, and dead by the time a renderer sees it: `inklet.text` has
    # already baked leading into `TextLine.baseline`. Setting it on a node that
    # is already laid out changes nothing.
    line_height: float | None = None           # multiple of font size
    # A halo: this many millimetres of stroke painted *under* the glyphs, so a
    # label keeps its counters over a micrograph or a ribbon diagram without a
    # plate behind it blanking the picture. Read only by a TextPrim, like
    # `text_fill`. The width is the full stroke, half of which the glyph itself
    # covers, so 0.4mm shows 0.2mm of paper around each stem.
    halo: float | None = None                  # mm
    # What the halo is painted in. None means the paper colour, which is what
    # a halo is for; a token or literal overrides it where the type sits on
    # something that is not the page -- white letters haloed in the ink colour
    # over a photograph.
    halo_color: str | None = None

    def __post_init__(self) -> None:
        """Coerce what is coercible and refuse the rest here, not in the renderer.

        `stroke_dash="2,1"` is the SVG idiom and the first thing anyone writes;
        accepting it as a string and failing inside `to_svg` after `lint()`
        said clean is the worst of both. So: sequences of numbers become a
        tuple of floats, a dash string is split on commas or spaces, and
        anything else names itself in the error.
        """
        dash = self.stroke_dash
        if dash is not None:
            object.__setattr__(self, "stroke_dash", _dash(dash))
        for name in _LENGTH_FIELDS:
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _length(name, value))
        for name in _RATIO_FIELDS:
            value = getattr(self, name)
            if value is not None and not _is_number(value):
                raise StyleError(f"{name} must be a number, got {value!r}")
        if self.font_style is not None and self.font_style not in FONT_STYLES:
            raise StyleError(
                f"font_style must be one of {', '.join(FONT_STYLES)}, got "
                f"{self.font_style!r}; a slanted weight is written "
                "font_weight='bold', font_style='italic'"
            )

    def over(self, base: Style | None) -> Style:
        """Resolve self against an inherited style, self winning where set.

        Every field of the result came from a `Style` that was checked when it
        was built, so the result cannot be invalid and the check is skipped.
        That matters because this runs once per node per render, where
        re-validating costs more than the merge itself.
        """
        if base is None:
            return self
        merged = object.__new__(Style)
        for field_ in fields(self):
            mine = getattr(self, field_.name)
            object.__setattr__(merged, field_.name,
                               getattr(base, field_.name) if mine is None else mine)
        return merged

    def with_(self, **kwargs) -> Style:
        return replace(self, **kwargs)

    @property
    def is_empty(self) -> bool:
        return all(getattr(self, f.name) is None for f in fields(self))


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _length(name: str, value) -> float:
    if _is_number(value):
        return float(value)
    if isinstance(value, str):
        try:
            return mm(value)
        except UnitError:
            pass
    raise StyleError(f"{name} must be a length in mm (a number or e.g. "
                     f"'0.5mm', '1pt'), got {value!r}")


def _dash(value) -> tuple[float, ...]:
    if isinstance(value, str):
        parts = [p for p in _DASH_SPLIT.split(value.strip()) if p]
    elif isinstance(value, (list, tuple)):
        parts = list(value)
    else:
        raise StyleError("stroke_dash must be a tuple of lengths in mm, "
                         f"e.g. (1.2, 0.8), got {value!r}")
    out = []
    for part in parts:
        if _is_number(part):
            out.append(float(part))
        elif isinstance(part, str):
            try:
                out.append(mm(part))
            except UnitError:
                raise StyleError(f"stroke_dash has a non-length entry "
                                 f"{part!r} in {value!r}") from None
        else:
            raise StyleError(f"stroke_dash has a non-length entry "
                             f"{part!r} in {value!r}")
    if not out or any(v < 0 for v in out):
        raise StyleError(f"stroke_dash needs non-negative lengths, got {value!r}")
    return tuple(out)


EMPTY_STYLE = Style()
