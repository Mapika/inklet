"""The two ways a figure explains its colours: a ramp and a list.

Both are fiddly for the same reason -- they are type and geometry glued
together at a size nobody specified -- so they live here once instead of being
rebuilt, slightly differently, by every modality that needs one.

A colorbar is a colour ramp with an axis against it, and it is built from the
same `axis()` as a plot's own, so its ticks obey the same 1/2/5 rule and its
labels are thinned the same way. The ramp itself is painted as a stack of
bands, because SVG gradients live in `<defs>` and this renderer deliberately
emits no defs; each band is drawn into the next one so that no seam shows.
"""

from __future__ import annotations

from typing import Callable, Iterable, Sequence

from ..core import COLUMN_SINGLE, Affine, Diagram, RectPrim, Vec2, mm
from ..draw.coords import active_theme, as_drawn, drawn_group
from ..draw.shapes import marker
from ..layout import grid as grid_layout, hstack, vstack
from .axis import SPINE_KIND, axis, text_node
from .ramp import Ramp, ramp as make_ramp
from .scale import Scale, _declare_domain, linear

__all__ = ["BANDS", "SWATCH_OF_TYPE", "colorbar", "legend"]

COLORBAR_KIND = "colorbar"
BAND_KIND = "colorband"
LEGEND_KIND = "legend"
LEGEND_LABEL_KIND = "label"

# Bands per ramp. At 128 the step between neighbours is under a couple of dE
# for every palette shipped here, which is the point where a gradient stops
# looking like a staircase; the cost is one <rect> each.
BANDS = 128

_LENGTH_OF_COLUMN = 0.45      # of a single column, for a bar given no length
_THICKNESS_OF_TYPE = 1.4      # a bar much thinner than the type reads as a rule
# A swatch, as a fraction of the *label's* size. Keyed to the label rather
# than to the base type because a legend's names are set small: measured
# against `font_size` the block came out taller than the capitals beside it,
# which makes a key of three entries the heaviest thing on a small panel.
# 0.9 of the small size is about a cap height, so the swatch and the word
# read as one line of type.
SWATCH_OF_TYPE = 0.9

_VERTICAL = ("left", "right")


def colorbar(source, *, domain: tuple[float, float] = (0.0, 1.0),
             scale: Scale | None = None, length: float | str | None = None,
             thickness: float | str | None = None, side: str = "right",
             label: str | None = None, ticks: Sequence | None = None,
             count: int = 5,
             format: Callable[[object], str] | None = None,
             steps: int = BANDS, outline: bool = True,
             thin: bool | None = None,
             kind: str = COLORBAR_KIND, **style) -> Diagram:
    """A continuous ramp with an axis against it.

    `source` is a `Ramp`, a palette, a palette name or a list of colours.
    `side` says which edge carries the numbers, and whether the bar stands up
    (left, right) or lies down (top, bottom). The scale may be any scale --
    a log colorbar is a log scale here, not a special case.

    `ticks` names the values to label, and `count` asks the scale for that many
    instead. Name them whenever the scale is not linear: a symlog key chooses
    round numbers in *value* space, which is not where the eye reads a nonlinear
    bar, and the three that matter -- the baseline, the threshold the key
    changes behaviour at, and the maximum -- are exactly the ones an automatic
    choice tends to miss.

    Naming them is not the same as keeping them: labels that would collide are
    still dropped, silently, because the bar is usually short and the numbers
    on a nonlinear one bunch at an end. Pass `thin=False` to keep every one you
    asked for and let the linter report the collision instead -- a visible
    collision is a better failure than a number that quietly is not there.
    """
    bar = make_ramp(source) if not isinstance(source, Ramp) else source
    theme = active_theme()
    vertical = side in _VERTICAL
    span = (mm(length) if length is not None
            else _LENGTH_OF_COLUMN * COLUMN_SINGLE)
    depth = (mm(thickness) if thickness is not None
             else _THICKNESS_OF_TYPE * theme.font_size)
    if steps < 1:
        raise ValueError(f"a colorbar needs at least one band, got {steps}")

    positions = (span / 2, -span / 2) if vertical else (-span / 2, span / 2)
    measure = (linear(domain, positions) if scale is None
               else scale.with_range(*positions))

    children = list(_bands(bar, steps, span, depth, vertical))
    if outline:
        children.append(_outline(span, depth, vertical))
    edge = (depth / 2 if side in ("right", "bottom") else -depth / 2)
    ruler = as_drawn(axis(measure, side=side, label=label, ticks=ticks,
                          count=count, format=format, thin=thin, spine=False))
    children.append(ruler.translated(edge, 0.0) if vertical
                    else ruler.translated(0.0, edge))
    node = drawn_group(children, kind, style)
    # What the bar claims its ends mean, for the rule that compares it against
    # the picture it stands beside. See `scale._declare_domain`.
    _declare_domain(node, measure)
    return node


def _bands(bar: Ramp, steps: int, span: float, depth: float,
           vertical: bool) -> Iterable[Diagram]:
    """The ramp as opaque slices, low value first.

    Every slice but the last is drawn a whole band too long, into the space the
    next one will cover. Two rectangles that merely abut are antialiased
    independently, and a pixel on the join gets a fraction of each and a
    fraction of the background -- which shows up as a pale rule across the bar,
    once per band. Overlapping by a whole band puts every seam inside solid
    colour instead, and painting low to high means the overhang is always
    covered by the slice that owns it.
    """
    step = span / steps
    for index in range(steps):
        t = (index + 0.5) / steps
        start = -span / 2 + step * index
        end = min(start + step * 2, span / 2) if index < steps - 1 else start + step
        middle = (start + end) / 2
        extent = end - start
        if vertical:
            # t grows up the page and y grows down it, so the slice for the
            # smallest value sits at the bottom.
            prim, at = RectPrim(depth, extent), Vec2(0.0, -middle)
        else:
            prim, at = RectPrim(extent, depth), Vec2(middle, 0.0)
        yield Diagram(
            prim=prim, kind=BAND_KIND,
            transform=Affine.translation(at.x, at.y),
        ).styled(fill=bar(t), stroke="none")


def _outline(span: float, depth: float, vertical: bool) -> Diagram:
    width, height = (depth, span) if vertical else (span, depth)
    return Diagram(prim=RectPrim(width, height), kind=SPINE_KIND)


def legend(entries: Sequence[tuple[str, object]], *, columns: int = 1,
           swatch: float | str | None = None, gap: float | str | None = None,
           row_gap: float | str | None = None, title: str | None = None,
           markup: bool = True, kind: str = LEGEND_KIND, **style) -> Diagram:
    """Swatches and their names.

    An entry is `(name, colour)` -- painted as a square swatch -- or
    `(name, diagram)`, which uses that diagram as the swatch, so a scatter's
    legend can show the very marker the scatter used.

    Names read inklet's inline markup, because a key is the one place a figure
    must be able to write `ChR2 (//n// = 12)` or `//Notch1//^{+/-}`, and no
    journal with a style guide will take that `n` in roman. `markup=False`
    sets them exactly as typed, for names that arrive from a data file rather
    than from the figure's source.

    The literal case survives the default anyway, which is why the default can
    be markup at all: a delimiter with no partner is ordinary text, so
    `Notch1**`, `dpp**` and `*CO` all read as themselves. What the parser eats
    is a *matched* pair, and a matched `//...//` in a series name is an
    italic request far more often than it is a filename.
    """
    if not entries:
        raise ValueError("a legend needs at least one entry")
    theme = active_theme()
    size = (SWATCH_OF_TYPE * theme.font_size_small if swatch is None
            else mm(swatch))
    # Half an em, not a whole one: a swatch is a piece of the same line as the
    # word it names, and a full space between them reads as two columns.
    inner = theme.gap("xs") if gap is None else mm(gap)
    between = theme.gap("xs") if row_gap is None else mm(row_gap)

    # A series name is written in the figure's own source -- it is the caption
    # for one curve -- so it is prose and reads markup, like the title above it
    # and the axis name beside it. The data case that argued for literal names
    # (`Notch1**`, `*CO`) is unaffected: those delimiters have no partner, and
    # an unpartnered delimiter is ordinary text. `markup=False` is there for
    # the name that really did come out of a column header.
    rows = [
        hstack([_swatch(value, size), text_node(str(name), theme.font_size_small,
                                                LEGEND_LABEL_KIND, markup=markup)],
               gap=inner, align="center")
        for name, value in entries
    ]
    body = (vstack(rows, gap=between, align="left") if columns == 1
            else grid_layout(rows, cols=columns, col_gap=inner * 2,
                             row_gap=between, align="left"))
    if title is not None:
        body = vstack([text_node(title, theme.font_size_small, LEGEND_LABEL_KIND),
                       body], gap=between, align="left")
    node = Diagram(children=(body,), kind=kind)
    return node.styled(**style) if style else node


def _swatch(value, size: float) -> Diagram:
    if isinstance(value, Diagram):
        return value
    return marker("square", size, fill=value, stroke="none")
