"""Measure live cells to a stable fit, then place artwork and route links."""
from __future__ import annotations

from dataclasses import dataclass
from itertools import accumulate
from typing import TYPE_CHECKING, Mapping, NamedTuple

from ..core import Affine, Diagram, DiagramError, Rect, resolve
from ..draw.coords import plot_area
from ..figure import Figure
from ..links import route_all
from .errors import LayoutError
from .spec import ComponentSpec, PlotSpec, themed
from .tracks import allocate_tracks

if TYPE_CHECKING:
    from .compiler import BuildContext, Cell


@dataclass(frozen=True)
class LayoutRequest:
    cells: tuple[Cell, ...]
    columns: tuple[float, ...]
    margin: float
    gap: float
    row_gap: float
    letters: Mapping
    links: tuple
    share_plot_margins: bool


class LayoutResult(NamedTuple):
    content: Diagram
    boxes: dict[str, Rect]
    handles: dict[str, Diagram]
    page_height: float
    passes: int


def plot_margins(node):
    area, box = plot_area(node), node.bbox
    if area is None:
        return (0., 0., 0., 0.)
    return (max(0., area.x0-box.x0), max(0., box.x1-area.x1),
            max(0., area.y0-box.y0), max(0., box.y1-area.y1))


def _decorator(request, context):
    indices = {cell.name: index for index, cell in enumerate(request.cells)}

    def decorate(node, cell):
        if not request.letters:
            return node
        from ..draw.annotate import letters
        options = dict(request.letters)
        if context.preset is not None:
            options.setdefault('style', context.preset.letter_style)
            if context.preset.letter_pad is not None:
                options.setdefault('pad', context.preset.letter_pad)
        start = chr(ord(options.pop('start')) + indices[cell.name])
        with themed(context.theme):
            tagged = letters([node], start=start, **options)[0]
        for name, point in node.anchors.items():
            tagged.anchor(name, node.transform.apply(point))
        return tagged

    return decorate


def _natural_sizes(request, context, x_prefix, height, decorate):
    """Retain authored plot heights and measure fixed artwork with its letters."""
    heights, plots = {}, {}
    for cell in request.cells:
        fixed = isinstance(cell.item, Diagram) or (
            isinstance(cell.item, ComponentSpec) and not cell.item.responsive)
        if height is None or fixed:
            width = (x_prefix[cell.column+cell.colspan]-x_prefix[cell.column]
                     + request.gap*(cell.colspan-1))
            natural = context.build(cell.item, width,
                                    cell.item.height if isinstance(cell.item, PlotSpec) else None)
            node = decorate(natural, cell)
            heights[cell.name] = node.height
            if isinstance(cell.item, PlotSpec):
                plots[cell.name] = (plot_area(node).height, *plot_margins(node)[2:])
    if request.share_plot_margins and height is None:
        # Maxima may belong to different plots; retain all of their furniture.
        # Top and bottom furniture is shared within a row only: a colorbar
        # under one bottom panel must not open the same gap under every row.
        rows = {(c.row, c.rowspan) for c in request.cells if c.name in plots}
        data = max((v[0] for v in plots.values()), default=0.)
        for key in rows:
            members = [c.name for c in request.cells
                       if c.name in plots and (c.row, c.rowspan) == key]
            tallest = data + sum(max(plots[m][n] for m in members) for n in (1, 2))
            for name in members:
                heights[name] = tallest
    return heights, plots


def _row_tracks(request, rows, natural_heights, height):
    return allocate_tracks(
        rows, (1.,)*rows,
        [(c.row, c.rowspan, max(c.min_height, natural_heights.get(c.name, 0)), c.name)
         for c in request.cells],
        None if height is None else height-2*request.margin, request.row_gap, 'height')


def _cell_boxes(request, x_prefix, heights):
    y_prefix = tuple(accumulate(heights, initial=0.))
    return {c.name: Rect(
        request.margin+x_prefix[c.column]+request.gap*c.column,
        request.margin+y_prefix[c.row]+request.row_gap*c.row,
        request.margin+x_prefix[c.column+c.colspan]+request.gap*(c.column+c.colspan-1),
        request.margin+y_prefix[c.row+c.rowspan]+request.row_gap*(c.row+c.rowspan-1))
        for c in request.cells}


def _measure_cells(request, context, boxes, margins, decorate):
    nodes = {}
    for cell in request.cells:
        box = boxes[cell.name]
        left, right, top, bottom = margins[cell.name]
        width, height = box.width-left-right, box.height-top-bottom
        if isinstance(cell.item, PlotSpec):
            if width < 5 or height < 5:
                raise LayoutError(f'cell {cell.name!r} leaves only {width:.2f} × {height:.2f} mm for data after labels. Increase its size.')
            nodes[cell.name] = context.build(cell.item, round(width, 6), round(height, 6))
        else:
            if width <= 0 or height <= 0:
                raise LayoutError(f'cell {cell.name!r} has no space after panel letters')
            nodes[cell.name] = context.build(cell.item, width, height)
    undecorated = {name: node.bbox for name, node in nodes.items()}
    nodes = {cell.name: decorate(nodes[cell.name], cell) for cell in request.cells}
    measured = {name: plot_margins(node) for name, node in nodes.items()}
    if request.letters:
        for cell in request.cells:
            if isinstance(cell.item, PlotSpec):
                continue
            a, b = undecorated[cell.name], nodes[cell.name].bbox
            measured[cell.name] = tuple(max(0., v, old) for v, old in zip(
                (a.x0-b.x0, b.x1-a.x1, a.y0-b.y0, b.y1-a.y1), margins[cell.name]))
    return nodes, measured


def _share_margins(request, measured, margins, per_row=False):
    columns, rows = {}, {}
    plots = [cell for cell in request.cells if isinstance(cell.item, PlotSpec)]
    for cell in plots:
        left, right, top, bottom = measured[cell.name]
        a, b = columns.get((cell.column, cell.colspan), (0., 0.))
        columns[cell.column, cell.colspan] = max(a, left), max(b, right)
        a, b = rows.get((cell.row, cell.rowspan), (0., 0.))
        rows[cell.row, cell.rowspan] = max(a, top), max(b, bottom)
    shared = (tuple(max((measured[c.name][n] for c in plots), default=0.) for n in range(4))
              if request.share_plot_margins else None)
    for cell in plots:
        if shared is None:
            values = (*columns[cell.column, cell.colspan], *rows[cell.row, cell.rowspan])
        elif per_row:
            # Equal data areas need equal left/right furniture everywhere, but
            # only equal top/bottom furniture along a row: each automatic row
            # track grows by its own furniture around the common data height.
            values = (*shared[:2], *rows[cell.row, cell.rowspan])
        else:
            values = shared
        # Monotonic margins prevent tick-thinning oscillations.
        measured[cell.name] = tuple(max(a, b) for a, b in zip(values, margins[cell.name]))


def _grow_natural_heights(request, plots, measured, heights):
    if request.share_plot_margins:
        # Measured margins are already shared, per row for automatic heights.
        tallest = max(v[0] for v in plots.values())
        required = {name: tallest+measured[name][2]+measured[name][3] for name in plots}
    else:
        required = {name: values[0]+measured[name][2]+measured[name][3]
                    for name, values in plots.items()}
    if not any(heights[name] < value-1e-6 for name, value in required.items()):
        return False
    for name, value in required.items():
        heights[name] = max(heights[name], value)
    return True


def _place_cells(cells, nodes, boxes, margins):
    placed, handles = [], {}
    for cell in cells:
        node, box = nodes[cell.name].copy(), boxes[cell.name]
        actual = node.bbox
        if actual.width > box.width+.02 or actual.height > box.height+.02:
            raise LayoutError(f'cell {cell.name!r} contains {actual.width:.2f} × {actual.height:.2f} mm '
                              f'but has {box.width:.2f} × {box.height:.2f} mm. Increase its cell size.')
        if isinstance(cell.item, PlotSpec):
            area = plot_area(node)
            left, _, top, _ = margins[cell.name]
            dx, dy = box.x0+left-area.x0, box.y0+top-area.y0
        else:
            dx, dy = box.center.x-actual.center.x, box.center.y-actual.center.y
            if cell.align in ('w', 'nw', 'sw'):
                dx = box.x0-actual.x0
            elif cell.align in ('e', 'ne', 'se'):
                dx = box.x1-actual.x1
            if cell.align in ('n', 'nw', 'ne'):
                dy = box.y0-actual.y0
            elif cell.align in ('s', 'sw', 'se'):
                dy = box.y1-actual.y1
        handles[cell.name] = node
        # Always wrap: a zero-offset translated() would lose the cell boundary.
        placed.append(Diagram(children=(node,), transform=Affine.translation(dx, dy),
                              kind='document-cell', name=cell.name).carry_notes(node))
    return Diagram(children=tuple(placed), kind='document-content'), handles


def _route_links(content, handles, links, theme):
    if not links:
        return content

    def endpoint(value):
        if not isinstance(value, str):
            raise TypeError('document link endpoints must be cell or cell:anchor strings')
        name, sep, anchor = value.partition(':')
        if name not in handles:
            raise DiagramError(f'unknown link cell {name!r}')
        return handles[name].at(anchor) if sep else handles[name]

    # Figure.link supplies theme-aware labels, plates and arrow defaults.
    builder = Figure(theme=theme)
    for a, b, options in links:
        builder.link(endpoint(a), endpoint(b), **options)
    connectors = route_all(builder._links, resolve(content))
    return Diagram(children=(content, connectors), kind='document-content')


def layout_document(request: LayoutRequest, context: BuildContext,
                    width: float, height: float | None) -> LayoutResult:
    if not request.cells:
        raise LayoutError('cannot compile an empty document')
    decorate = _decorator(request, context)
    rows = max(c.row+c.rowspan for c in request.cells)
    widths = allocate_tracks(
        len(request.columns), request.columns,
        [(c.column, c.colspan, c.min_width, c.name) for c in request.cells],
        width-2*request.margin, request.gap, 'width')
    x_prefix = tuple(accumulate(widths, initial=0.))
    natural_heights, natural_plots = _natural_sizes(request, context, x_prefix, height, decorate)
    heights = _row_tracks(request, rows, natural_heights, height)
    boxes = _cell_boxes(request, x_prefix, heights)
    margins = {c.name: (0., 0., 0., 0.) for c in request.cells}
    # Tick selection depends on width; grow furniture and tracks to a stable fit.
    for iteration in range(24):
        nodes, measured = _measure_cells(request, context, boxes, margins, decorate)
        _share_margins(request, measured, margins, per_row=height is None)
        if (height is None and natural_plots
                and _grow_natural_heights(request, natural_plots, measured, natural_heights)):
            heights = _row_tracks(request, rows, natural_heights, None)
            boxes = _cell_boxes(request, x_prefix, heights)
            margins = measured
            continue
        if all(max(abs(a-b) for a, b in zip(measured[n], margins[n])) < .005 for n in margins):
            break
        margins = measured
    else:
        raise LayoutError('plot furniture did not settle after 24 measurement passes')
    content, handles = _place_cells(request.cells, nodes, boxes, margins)
    with themed(context.theme):
        content = _route_links(content, handles, request.links, context.theme)
    page_height = (height if height is not None else
                   2*request.margin+sum(heights)+request.row_gap*(rows-1))
    return LayoutResult(content, boxes, handles, page_height, iteration+1)
