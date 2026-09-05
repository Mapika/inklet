"""A grid of panels that share their axes.

`row` and `column` already line panels up on their plot *areas* rather than on
their bounding boxes, which is the hard half of a multi-panel figure. What was
missing is everything that follows from the panels being the same plot drawn
several times: the inner numbers are repeated furniture, the outer ones are the
only ones anybody reads, and the name of the quantity belongs once, centred on
the region the data occupies rather than on the ragged edge of the labels.

So `facets` owns the axes. It is the one place in `inklet.plot` that adds
furniture to a panel it was handed, and it does that because the decision --
does this panel show its numbers? -- is a property of the *grid*, not of the
panel. A panel cannot know it is in the bottom row.

Two things it deliberately keeps. **Every panel keeps its spine and its
ticks**, so an inner panel is still a plot with a scale on it and not a
floating rectangle; only the numbers go. And the areas stay exactly aligned
column by column and row by row, measured from each panel's `origin` anchor,
so a panel whose numbers happen to be wider does not shove its neighbour out
of line.
"""

from __future__ import annotations

import math
from typing import Sequence

from ..core import Diagram, Rect, Vec2, mm
from ..draw.coords import (active_theme, declare_area, drawn_group,
                           plot_area)
from .axis import AXIS_LABEL_KIND, text_node
from .panel import Panel, _origin_of

__all__ = ["facets"]

FACETS_KIND = "facets"


def facets(panels: Sequence[Panel | Diagram], *, cols: int | None = None,
           share_x: bool = True, share_y: bool = True,
           x_label: str | Diagram | None = None,
           y_label: str | Diagram | None = None,
           gap: float | str | None = None, row_gap: float | str | None = None,
           axes: bool = True, label_pad: float | str | None = None,
           **axis_kwargs) -> Diagram:
    """A grid of panels with one set of axes between them.

    Panels are filled left to right, top to bottom, into `cols` columns --
    about the square root of how many there are, unless you say. Their plot
    areas line up in both directions.

    With `share_x`, only the bottom panel of each column writes its numbers;
    with `share_y`, only the leftmost of each row. Every panel keeps its spine
    and its ticks either way, because a plot without a scale on it is not a
    plot. `x_label` and `y_label` name the quantity once, centred on the block
    of plot areas rather than on the furniture around it:

        grid = inklet.facets([p1, p2, p3, p4], cols=2,
                          x_label="time / s", y_label="dF/F")

    `axes=False` leaves the furniture to you and does the alignment only.
    Anything else -- `count`, `ticks`, `format`, `si`, `minor`, `tick_size` --
    is passed through to every axis this builds, so a grid is styled once.
    """
    items = list(panels)
    if not items:
        raise ValueError("facets() needs at least one panel")
    columns = _columns(cols, len(items))
    theme = active_theme()
    step_x = theme.gap("l") if gap is None else mm(gap)
    step_y = step_x if row_gap is None else mm(row_gap)
    pad = theme.gap("s") if label_pad is None else mm(label_pad)

    if axes:
        _hang_axes(items, columns, share_x, share_y, axis_kwargs)

    cells = [_Cell(item) for item in items]
    _place(cells, columns, step_x, step_y)

    placed = [cell.placed for cell in cells]
    region = _region(cells)
    box = _union(placed) or region
    if x_label is not None:
        placed.append(_name(x_label, theme,
                            Vec2(region.center.x, box.y1 + pad), horizontal=True))
    if y_label is not None:
        placed.append(_name(y_label, theme,
                            Vec2(box.x0 - pad, region.center.y), horizontal=False))
    group = drawn_group(placed, FACETS_KIND)
    # The grid declares the block of areas as its own, the way `row` and
    # `column` do, so a facets grid nested in either is placed by its data
    # region and not by the ragged edge of its labels -- and so `letters`
    # hangs its letter off the top of the data rather than off the top of the
    # x-axis name. It is `region`, exactly: the same rectangle the shared axis
    # names are centred on, which is what makes one function answer both
    # questions. In the frame the cells were placed in, which is the
    # pre-recentring frame `drawn_group` leaves on the group's transform.
    declare_area(group, region)
    return group


def _columns(cols: int | None, count: int) -> int:
    if cols is None:
        return max(1, math.ceil(math.sqrt(count)))
    if cols < 1:
        raise ValueError(f"facets() needs at least one column, got {cols}")
    return cols


def _hang_axes(items: Sequence[Panel | Diagram], columns: int,
               share_x: bool, share_y: bool, kwargs: dict) -> None:
    """Give every panel its two axes, and only the outer ones their numbers.

    A panel already carrying furniture is left alone: `axes=False` is the
    documented way to do that, but a caller who called `p.axis()` first has
    said the same thing more loudly.
    """
    rows = math.ceil(len(items) / columns)
    for index, item in enumerate(items):
        if not isinstance(item, Panel):
            continue
        row, column = divmod(index, columns)
        # The bottom row of *this* column, which is not the last row when the
        # grid does not divide evenly -- the panel above a hole is the one a
        # reader looks under for the numbers.
        bottom = row == rows - 1 or index + columns >= len(items)
        item.axis("bottom", labels=not share_x or bottom, **kwargs)
        item.axis("left", labels=not share_y or column == 0, **kwargs)


class _Cell:
    """One built panel, with the reach of its furniture from its own origin."""

    __slots__ = ("node", "origin", "area", "left", "right", "top", "bottom",
                 "placed")

    def __init__(self, item: Panel | Diagram) -> None:
        self.node = item.build() if isinstance(item, Panel) else item
        box = self.node.envelope.bbox() or Rect(0.0, 0.0, 0.0, 0.0)
        self.origin = _origin_of(self.node)
        self.area = _area_size(self.node, item, box)
        self.left = self.origin.x - box.x0
        self.right = box.x1 - self.origin.x
        self.top = self.origin.y - box.y0
        self.bottom = box.y1 - self.origin.y
        self.placed = self.node

    def at(self, centre: Vec2) -> None:
        self.placed = self.node.translated(centre.x - self.origin.x,
                                           centre.y - self.origin.y)
        self.origin = centre


def _area_size(node: Diagram, item: Panel | Diagram, box: Rect) -> Vec2:
    """How big this cell's data region is, for `_region` to block out.

    The declared `plot_area` first, because the caller's member is very often
    not a `Panel` at all: `examples/gallery.py` hands `facets` the output of
    `inklet.letters`, and a lettered panel is a `Diagram`. That used to fall
    through to the bounding box, so the grid aligned the areas -- `_origin_of`
    reads the note -- and then centred its axis names on the *boxes*, which is
    the asymmetry `_region` was written to remove, reintroduced for every
    caller who put a letter on a panel first. Gallery's sixteen panels each
    declare a 21.50 x 15.50mm area and each measure 33.7-36.8 x 24.5-29.1mm
    round it, so the two answers differ by half a centimetre.

    The box remains the answer for a member that declares nothing, which is
    the only honest one: a drawing in a grid of plots has no data region and
    its ink is the whole of it.
    """
    area = plot_area(node)
    if area is not None:
        return Vec2(area.width, area.height)
    if isinstance(item, Panel):
        return Vec2(item.width, item.height)
    return Vec2(box.width, box.height)


def _place(cells: Sequence[_Cell], columns: int, step_x: float,
           step_y: float) -> None:
    """Put each area on its column's line and its row's line.

    The offsets are measured from the `origin` anchor -- the centre of the
    plot area -- and the room a column takes is the widest furniture in it on
    each side. That is what keeps the areas aligned when one panel's numbers
    are wider than another's, which is the whole reason `row` exists.
    """
    rows = math.ceil(len(cells) / columns)
    lefts = [max((c.left for c in _column(cells, columns, i)), default=0.0)
             for i in range(columns)]
    rights = [max((c.right for c in _column(cells, columns, i)), default=0.0)
              for i in range(columns)]
    tops = [max((c.top for c in _row(cells, columns, i)), default=0.0)
            for i in range(rows)]
    bottoms = [max((c.bottom for c in _row(cells, columns, i)), default=0.0)
               for i in range(rows)]
    xs, cursor = [], 0.0
    for i in range(columns):
        xs.append(cursor + lefts[i])
        cursor += lefts[i] + rights[i] + step_x
    ys, cursor = [], 0.0
    for i in range(rows):
        ys.append(cursor + tops[i])
        cursor += tops[i] + bottoms[i] + step_y
    for index, cell in enumerate(cells):
        row, column = divmod(index, columns)
        cell.at(Vec2(xs[column], ys[row]))


def _column(cells: Sequence[_Cell], columns: int, index: int):
    return [c for i, c in enumerate(cells) if i % columns == index]


def _row(cells: Sequence[_Cell], columns: int, index: int):
    return [c for i, c in enumerate(cells) if i // columns == index]


def _region(cells: Sequence[_Cell]) -> Rect:
    """The block the plot *areas* occupy, ignoring every bit of furniture.

    This is what a shared axis name is centred on. Centring it on the grid's
    bounding box instead puts it visibly left of the data, because the y labels
    on the first column stick out and nothing balances them on the right --
    the exact asymmetry the backlog entry for this was about.
    """
    box = None
    for cell in cells:
        here = Rect(cell.origin.x - cell.area.x / 2,
                    cell.origin.y - cell.area.y / 2,
                    cell.origin.x + cell.area.x / 2,
                    cell.origin.y + cell.area.y / 2)
        box = here if box is None else box.union(here)
    return box or Rect(0.0, 0.0, 0.0, 0.0)


def _name(label: str | Diagram, theme, at: Vec2, *, horizontal: bool) -> Diagram:
    node = (label if isinstance(label, Diagram)
            else text_node(label, theme.font_size, AXIS_LABEL_KIND))
    if not horizontal:
        node = node.rotated(-90.0)
    box = node.bbox
    reach = (box.height if horizontal else box.width) / 2
    centre = (Vec2(at.x, at.y + reach) if horizontal
              else Vec2(at.x - reach, at.y))
    here = node.transform.apply(node.anchor_point("center"))
    return node.translated(centre.x - here.x, centre.y - here.y)


def _union(items: Sequence[Diagram]) -> Rect | None:
    box = None
    for item in items:
        other = item.envelope.bbox()
        if other is not None:
            box = other if box is None else box.union(other)
    return box
