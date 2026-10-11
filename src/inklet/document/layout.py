"""Measure live cells to a stable fit, then place artwork and route links."""
from __future__ import annotations

from dataclasses import dataclass, replace
from itertools import accumulate
from typing import TYPE_CHECKING, Mapping, NamedTuple

from ..core import Affine, Diagram, DiagramError, Rect, pt, resolve
from ..core.prims import TextPrim
from ..draw.coords import plot_area
from ..plot.furniture import TITLE_KIND
from ..figure import Figure
from ..links import route_all
from .errors import LayoutError
from .spec import Choice, ComponentSpec, PlotSpec, themed
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
    share_plot_margins: bool | str
    pack: bool = False


class LayoutResult(NamedTuple):
    content: Diagram
    boxes: dict[str, Rect]
    handles: dict[str, Diagram]
    page_height: float
    passes: int
    report: dict


def plot_margins(node):
    area, box = plot_area(node), node.bbox
    if area is None:
        return (0., 0., 0., 0.)
    return (max(0., area.x0-box.x0), max(0., box.x1-area.x1),
            max(0., area.y0-box.y0), max(0., box.y1-area.y1))


def _parts(node, transform=None):
    """(part, its box in the frame `node.bbox` is in) for every node under `node`."""
    transform = node.transform if transform is None else transform @ node.transform
    box = node.local_envelope.transform(transform).bbox()
    yield node, box
    for child in node.children:
        yield from _parts(child, transform)


def _titles(node):
    """The title nodes in a built plot, each with its box in `node.bbox`'s frame."""
    return [(part, box) for part, box in _parts(node)
            if part.kind == TITLE_KIND and box is not None]


def _title_text(part):
    prim = part.prim
    if isinstance(prim, TextPrim):
        return '\n'.join(line.text for line in prim.lines)
    texts = [line.text for child in part.walk() if isinstance(child.prim, TextPrim)
             for line in child.prim.lines]
    return ' '.join(texts) if texts else None


def _ink_without_titles(node):
    """The box around everything in a built plot but its titles."""
    box, skip = None, set()
    for part, here in _parts(node):
        if part.kind == TITLE_KIND:
            skip.update(id(child) for child in part.walk())
        if id(part) in skip or part.prim is None or here is None:
            continue
        box = here if box is None else box.union(here)
    return box


def _wrapped(part, width):
    """The title's text broken into lines no wider than `width` mm, or None."""
    prim = part.prim
    if not isinstance(prim, TextPrim) or width <= 0:
        return None
    from ..typeset import shape
    text = ' '.join(line.text for line in prim.lines)
    try:
        lines = shape(text, font=prim.font_path or prim.font_family, size=prim.font_size,
                      width=width, markup=False).lines
    except Exception:  # a suggestion must never hide the real error
        return None
    if len(lines) < 2 or max(line.advance for line in lines) > width + 1e-6:
        return None
    return '\n'.join(line.text for line in lines)


def _title_offsets(node):
    """Where each title starts relative to its data area's left edge, or None."""
    area = plot_area(node) if node is not None else None
    if area is None:
        return None
    return [extent.x0-area.x0 for _, extent in _titles(node)]


def _title_too_wide(cell, node, box, left, previous=None):
    """The LayoutError for a plot title that cannot fit across its cell, or None.

    A title is furniture like the tick labels: what it reaches past the data
    area is margin. One that cannot fit makes that margin grow by the
    overflow every pass, so the data width the loop would report falls
    towards nothing -- a symptom, not the cause. Two cases are certain:

    - the title is wider than the whole cell;
    - the title starts at a fixed place relative to the data area (the
      same offset as in the `previous` pass's node, as a start-aligned
      title over its own axis labels does), and from there, with the left
      margin `left` already reserved, its far end passes the cell's right
      edge. Margins only grow, so it never will fit.

    The error names the title, its width and the width it has, and a
    spelling broken over lines that fits over the data.
    """
    area = plot_area(node)
    before = _title_offsets(previous)
    for index, (part, extent) in enumerate(_titles(node)):
        text = _title_text(part)
        named = f'title {text!r}' if text else 'title'
        if extent.width > box.width + .01:
            message = (f'cell {cell.name!r}: its {named} is {extent.width:.1f} mm wide, '
                       f'but the cell is only {box.width:.1f} mm wide, so no data width can '
                       'make room for it')
        elif area is not None and before is not None and index < len(before):
            offset = extent.x0-area.x0
            start = max(0., left+offset)
            if abs(offset-before[index]) > .01 or start+extent.width <= box.width+.01:
                continue
            message = (f'cell {cell.name!r}: its {named} is {extent.width:.1f} mm wide, '
                       f'but it starts {start:.1f} mm in from the cell\'s left edge, with this '
                       "plot's axis labels, which leaves it "
                       f'{box.width-start:.1f} mm of the {box.width:.1f} mm cell')
        else:
            continue
        message += '. Shorten it, widen the cell or figure, or break it over lines'
        ink = _ink_without_titles(node)
        room = box.width
        if area is not None and ink is not None:
            # Room over the data alone fits a title whatever its alignment.
            room -= max(0., left, area.x0-ink.x0) + max(0., ink.x1-area.x1)
        wrapped = _wrapped(part, room)
        if wrapped is not None:
            message += f' with \\n, for example {wrapped!r}'
        return LayoutError(message + '.')
    return None


def _no_room_for_data(cell, box, margins, width, height, node):
    """The LayoutError for a plot whose furniture leaves (almost) no data area.

    Lists what each side's furniture takes. When a title reaches past the
    data further than the other furniture on a side, so that it sets that
    margin, the error names it with its width and the width it has: from
    where it starts to the cell's right edge. That is how a title narrower
    than its cell still fails: a stacked panel's wider tick labels set a
    shared left margin, the title starts at this plot's own labels to the
    right of the cell edge, and its far end no longer fits.
    """
    left, right, top, bottom = margins
    message = (f'cell {cell.name!r} leaves only {width:.2f} × {height:.2f} mm for data after labels: '
               f'of its {box.width:.2f} × {box.height:.2f} mm, the furniture takes '
               f'{left:.2f} mm left, {right:.2f} mm right, {top:.2f} mm above and '
               f'{bottom:.2f} mm below')
    area = plot_area(node) if node is not None else None
    ink = _ink_without_titles(node) if area is not None else None
    causes = []
    if area is not None and ink is not None:
        for part, extent in _titles(node):
            text = _title_text(part)
            named = f'title {text!r}' if text else 'title'
            sets_width = (extent.x1-area.x1 > max(0., ink.x1-area.x1)+.5
                          or area.x0-extent.x0 > max(0., area.x0-ink.x0)+.5)
            if sets_width:
                start = max(0., left+extent.x0-area.x0)
                causes.append(f'The {named} is {extent.width:.1f} mm wide, but it starts '
                              f'{start:.1f} mm in from the cell\'s left edge, which leaves it '
                              f'{box.width-start:.1f} mm; shorten it or break it over lines with \\n')
            elif area.y0-extent.y0 > max(0., area.y0-ink.y0)+.5 and extent.height > box.height/2:
                causes.append(f'The {named} is {extent.height:.1f} mm tall in a '
                              f'{box.height:.1f} mm cell; shorten it or give the figure more height')
    if causes:
        return LayoutError(message + '. ' + '; '.join(causes) + '.')
    return LayoutError(message + '. Increase its size.')


def _decorator(request, context):
    indices = {cell.name: index for index, cell in enumerate(request.cells)}

    def decorate(node, cell):
        if not request.letters:
            return node
        from ..draw.annotate import letters
        options = dict(request.letters)
        options.pop('anchor', None)
        if context.preset is not None:
            options.setdefault('style', context.preset.letter_style)
            if context.preset.letter_pad is not None:
                options.setdefault('pad', context.preset.letter_pad)
        publication = getattr(context, 'publication', None)
        if publication is not None and publication.letter_font_pt is not None:
            options.setdefault('size', pt(publication.letter_font_pt))
        start = chr(ord(options.pop('start')) + indices[cell.name])
        with themed(context.theme):
            tagged = letters([node], start=start, **options)[0]
        for name, point in node.anchors.items():
            tagged.anchor(name, node.transform.apply(point))
        return tagged

    return decorate


def _fixed(item):
    return isinstance(item, Diagram) or (isinstance(item, ComponentSpec) and not item.responsive)


def _min_width(cell, context, decorate):
    """A cell's width floor: its `min_width`, and for fixed artwork the
    measured width of the drawing with its panel letter, which no track may
    cut."""
    if not _fixed(cell.item):
        return cell.min_width
    return max(cell.min_width, decorate(context.build(cell.item), cell).bbox.width)


def _natural_sizes(request, context, x_prefix, height, decorate):
    """Retain authored plot heights and measure cells with their letters.

    A fixed page height starts from these heights too, so a nested subfigure
    laid out at its natural height is unchanged by its parent. Responsive
    components have no natural height; under a fixed height they only ever
    receive their cell's dimensions, and grow from their minimum.
    """
    heights, plots = {}, {}
    for cell in request.cells:
        if (height is not None and isinstance(cell.item, ComponentSpec)
                and cell.item.responsive):
            continue
        width = (x_prefix[cell.column+cell.colspan]-x_prefix[cell.column]
                 + request.gap*(cell.colspan-1))
        natural = context.build(cell.item, width,
                                cell.item.height if isinstance(cell.item, PlotSpec) else None)
        node = decorate(natural, cell)
        if isinstance(cell.item, PlotSpec) and 'aspect' in cell.item.options:
            # An aspect region fits inside the cell less its furniture, which
            # only the first build reveals: its height is measured from a second.
            left, right = plot_margins(node)[:2]
            node = decorate(context.build(cell.item, width-left-right, cell.item.height), cell)
        heights[cell.name] = node.height
        if isinstance(cell.item, PlotSpec):
            plots[cell.name] = (plot_area(node).height, *plot_margins(node)[2:])
    if request.share_plot_margins:
        # Maxima may belong to different plots; retain all of their furniture.
        # Top and bottom furniture is shared within a row only: a colorbar
        # under one bottom panel must not open the same gap under every row.
        data = _shared_data_heights(request, plots)
        rows = {(c.row, c.rowspan) for c in request.cells if c.name in plots}
        for key in rows:
            members = [c.name for c in request.cells
                       if c.name in plots and (c.row, c.rowspan) == key]
            furniture = sum(max(plots[m][n] for m in members) for n in (1, 2))
            for name in members:
                heights[name] = data[name] + furniture
    return heights, plots


def _shared_data_heights(request, plots):
    """Data height each plot reserves when margins are shared.

    `True` shares data height along a row only, so heights chosen per row
    survive; `'all'` gives every plot the tallest data height in the grid.
    """
    if request.share_plot_margins == 'all':
        tallest = max((v[0] for v in plots.values()), default=0.)
        return {name: tallest for name in plots}
    rows = {}
    for cell in request.cells:
        if cell.name in plots:
            key = cell.row, cell.rowspan
            rows[key] = max(rows.get(key, 0.), plots[cell.name][0])
    return {cell.name: rows[cell.row, cell.rowspan]
            for cell in request.cells if cell.name in plots}


def _row_tracks(request, rows, natural_heights):
    return allocate_tracks(
        rows, (1.,)*rows,
        [(c.row, c.rowspan, max(c.min_height, natural_heights.get(c.name, 0)), c.name)
         for c in request.cells],
        None, request.row_gap, 'height')


def _fit_rows(request, rows, natural, natural_heights, plots, height):
    """Fit natural row heights to a fixed page height.

    Surplus goes to plot rows in proportion to their data heights, so stacked
    plots keep one scale, and to nested grids and responsive components in
    proportion to their natural heights. Text, fixed artwork and cells added
    with ``grow=False`` keep their measured size. With too little room every row shrinks in proportion,
    down to the cell minima; fixed artwork never shrinks.
    """
    available = height-2*request.margin
    surplus = available-sum(natural)-request.row_gap*(rows-1)
    if surplus < -1e-6:
        floors = [(c.row, c.rowspan, max(c.min_height, natural_heights[c.name])
                   if _fixed(c.item) else c.min_height, c.name) for c in request.cells]
        return allocate_tracks(rows, [max(h, 1e-6) for h in natural], floors,
                               available, request.row_gap, 'height')
    weights = [0.]*rows
    for cell in request.cells:
        if not cell.grow or _fixed(cell.item):
            continue
        grow = (plots[cell.name][0] if cell.name in plots
                else natural_heights.get(cell.name, cell.min_height))
        for row in range(cell.row, cell.row+cell.rowspan):
            weights[row] = max(weights[row], grow/cell.rowspan)
    if not any(weights):
        # Only fixed artwork: spread the surplus; cells align their artwork.
        weights = [max(h, 1e-6) for h in natural]
    total = sum(weights)
    targets = [h+surplus*w/total for h, w in zip(natural, weights)]
    return allocate_tracks(
        rows, targets,
        [(c.row, c.rowspan, max(c.min_height, natural_heights.get(c.name, 0)), c.name)
         for c in request.cells],
        available, request.row_gap, 'height')


def _cell_boxes(request, x_prefix, heights):
    y_prefix = tuple(accumulate(heights, initial=0.))
    return {c.name: Rect(
        request.margin+x_prefix[c.column]+request.gap*c.column,
        request.margin+y_prefix[c.row]+request.row_gap*c.row,
        request.margin+x_prefix[c.column+c.colspan]+request.gap*(c.column+c.colspan-1),
        request.margin+y_prefix[c.row+c.rowspan]+request.row_gap*(c.row+c.rowspan-1))
        for c in request.cells}


def _measure_cells(request, context, boxes, margins, decorate, previous=None):
    """Build every cell inside its margins; `previous` holds the last pass's
    nodes, which say what furniture set the margins when no room is left."""
    nodes = {}
    for cell in request.cells:
        box = boxes[cell.name]
        left, right, top, bottom = margins[cell.name]
        width, height = box.width-left-right, box.height-top-bottom
        if isinstance(cell.item, PlotSpec):
            # Tracks are sums of floats; a plot authored at the minimum must fit.
            if width < 5-1e-6 or height < 5-1e-6:
                raise _no_room_for_data(cell, box, margins[cell.name], width, height,
                                        (previous or {}).get(cell.name))
            nodes[cell.name] = context.build(cell.item, round(width, 6), round(height, 6))
            too_wide = _title_too_wide(cell, nodes[cell.name], box, left,
                                       (previous or {}).get(cell.name))
            if too_wide is not None:
                raise too_wide
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


def _extrapolate(margins, measured, steps):
    """Jump margins that approach their fixed point geometrically.

    A label centered over the data grows its margin by half of any narrowing
    of the data, so each pass halves the remaining error. Once two passes
    shrink the step by the same ratio, the limit follows directly; the next
    pass checks it.
    """
    out = {}
    for name, values in measured.items():
        step = tuple(b-a for a, b in zip(margins[name], values))
        last = steps.get(name) or (None, None)
        ratios = tuple(now/before if before and abs(before) > 1e-9 else None
                       for now, before in zip(step, last[0] or step))
        steps[name] = (step, ratios)
        jumped = list(values)
        if last[0] is not None and last[1] is not None:
            for n, (now, ratio, previous) in enumerate(zip(step, ratios, last[1])):
                if (ratio is not None and previous is not None and .2 < ratio < .9
                        and abs(ratio-previous) < .05 and abs(now) >= .005):
                    jumped[n] = values[n]+now*ratio/(1-ratio)
        if jumped != list(values):
            steps[name] = None
        out[name] = tuple(jumped)
    return out


def _stacks(plots, edge):
    """Group plots whose `edge` grid line matches and whose rows touch.

    Aligning a data edge matters where panels stand directly above one
    another. Plots on one grid line with other content between them are not
    a stack, so a key beside one never narrows the other.
    """
    group = {cell.name: cell.name for cell in plots}

    def find(name):
        while group[name] != name:
            name = group[name]
        return name

    for n, a in enumerate(plots):
        for b in plots[n+1:]:
            if (edge(a) == edge(b) and a.row <= b.row+b.rowspan
                    and b.row <= a.row+a.rowspan):
                group[find(a.name)] = find(b.name)
    return {cell.name: find(cell.name) for cell in plots}


def _share_margins(request, measured, margins):
    plots = [cell for cell in request.cells if isinstance(cell.item, PlotSpec)]
    if request.share_plot_margins:
        # Left and right furniture is shared by stacked cells that start or
        # end on the same vertical grid line, so their data edges line up;
        # a wide label never squeezes a cell that shares neither line.
        left_of = _stacks(plots, lambda c: c.column)
        right_of = _stacks(plots, lambda c: c.column+c.colspan)
    else:
        left_of = right_of = _stacks(plots, lambda c: (c.column, c.colspan))
    row_of = {cell.name: (cell.row, cell.rowspan) for cell in plots}
    lefts, rights, rows = {}, {}, {}
    for cell in plots:
        left, right, top, bottom = measured[cell.name]
        lefts[left_of[cell.name]] = max(lefts.get(left_of[cell.name], 0.), left)
        rights[right_of[cell.name]] = max(rights.get(right_of[cell.name], 0.), right)
        a, b = rows.get(row_of[cell.name], (0., 0.))
        rows[row_of[cell.name]] = max(a, top), max(b, bottom)
    for cell in plots:
        if request.share_plot_margins == 'all':
            # One physical x scale across the grid.
            sides = tuple(max(measured[c.name][n] for c in plots) for n in (0, 1))
        else:
            sides = lefts[left_of[cell.name]], rights[right_of[cell.name]]
        # Top and bottom furniture is shared along a row: each row track
        # holds its own furniture around the row's common data height.
        values = (*sides, *rows[row_of[cell.name]])
        # Monotonic margins prevent tick-thinning oscillations.
        measured[cell.name] = tuple(max(a, b) for a, b in zip(values, margins[cell.name]))


def _grow_natural_heights(request, plots, measured, heights):
    if request.share_plot_margins:
        # Measured margins are already shared, per row for automatic heights.
        data = _shared_data_heights(request, plots)
        required = {name: data[name]+measured[name][2]+measured[name][3] for name in plots}
    else:
        required = {name: values[0]+measured[name][2]+measured[name][3]
                    for name, values in plots.items()}
    # Margins settle to .005 mm; growing rows for less would chase the last
    # digits of a margin that converges geometrically, one pass at a time.
    if not any(heights[name] < value-.005 for name, value in required.items()):
        return False
    for name, value in required.items():
        heights[name] = max(heights[name], value)
    return True


def _to_cell_corner(node, box, dx, dy):
    """Move a cell's panel letter to the cell's top-left corner.

    The letter sits left of its content, so moving it up and left never
    meets the content; each move is clamped to those two directions.
    """
    content, letter = node.children
    ink = letter.bbox
    shift_x = min(0., box.x0-dx-ink.x0)
    shift_y = min(0., box.y0-dy-ink.y0)
    return replace(node, children=(content, letter.translated(shift_x, shift_y)))


def _fractions(align):
    """Where a compass `align` puts a slack: 0 at the start, 1 at the end, else centred."""
    fx = 0. if align in ('w', 'nw', 'sw') else 1. if align in ('e', 'ne', 'se') else .5
    fy = 0. if align in ('n', 'nw', 'ne') else 1. if align in ('s', 'sw', 'se') else .5
    return fx, fy


def _place_cells(cells, nodes, boxes, margins, corner_letters=False):
    placed, handles = [], {}
    for cell in cells:
        node, box = nodes[cell.name].copy(), boxes[cell.name]
        actual = node.bbox
        if actual.width > box.width+.02 or actual.height > box.height+.02:
            raise LayoutError(f'cell {cell.name!r} contains {actual.width:.2f} × {actual.height:.2f} mm '
                              f'but has {box.width:.2f} × {box.height:.2f} mm. Increase its cell size.')
        fx, fy = _fractions(cell.align)
        if isinstance(cell.item, PlotSpec):
            # A plot's data region fills its cell less furniture, so the only slack
            # is an aspect's; the furniture moves with the region it surrounds.
            area = plot_area(node)
            left, right, top, bottom = margins[cell.name]
            slack_x = max(0., box.width-left-right-area.width)
            slack_y = max(0., box.height-top-bottom-area.height)
            dx = box.x0+left+slack_x*fx-area.x0
            dy = box.y0+top+slack_y*fy-area.y0
        else:
            dx = box.x0+(box.width-actual.width)*fx-actual.x0
            dy = box.y0+(box.height-actual.height)*fy-actual.y0
        if corner_letters:
            node = _to_cell_corner(node, box, dx, dy)
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
    """Lay out the grid, choosing among each `choose()` cell's alternatives.

    Choices are settled one cell at a time, in page order, by coordinate
    descent: a cell switches alternative only when that shortens the page's
    natural height by more than 0.1 mm, so ties keep the author's preferred
    (earlier) alternative. Passes repeat until nothing changes. Alternatives
    that cannot fit are skipped. Under a fixed page height, the natural
    height is still what is minimized, leaving the most room to distribute.
    """
    if not request.cells:
        raise LayoutError('cannot compile an empty document')
    if request.pack:
        from .packing import pack_document
        return pack_document(request, context, width, height)
    choices = [n for n, c in enumerate(request.cells) if isinstance(c.item, Choice)]
    if not choices:
        return _layout_once(request, context, width, height)
    picks = {n: 0 for n in choices}
    tried = {}

    def attempt(picks):
        key = tuple(sorted(picks.items()))
        if key not in tried:
            cells = tuple(replace(c, item=c.item.options[picks[n]]) if n in picks else c
                          for n, c in enumerate(request.cells))
            try:
                tried[key] = _layout_once(replace(request, cells=cells), context, width, height)
            except LayoutError as error:
                tried[key] = error
        return tried[key]

    def score(result):
        return result.report['natural_height'] if isinstance(result, LayoutResult) else float('inf')

    best = attempt(picks)
    for _ in range(4):
        changed = False
        for n in choices:
            for option in range(len(request.cells[n].item.options)):
                if option == picks[n]:
                    continue
                candidate = attempt(picks | {n: option})
                if score(candidate) < score(best)-.1:
                    best, picks, changed = candidate, picks | {n: option}, True
        if not changed:
            break
    if isinstance(best, LayoutError):
        raise best
    best.report['choices'] = {request.cells[n].name: request.cells[n].item.names[picks[n]]
                              for n in choices}
    return best


def _layout_once(request, context, width, height):
    decorate = _decorator(request, context)
    rows = max(c.row+c.rowspan for c in request.cells)
    widths = allocate_tracks(
        len(request.columns), request.columns,
        [(c.column, c.colspan, _min_width(c, context, decorate), c.name) for c in request.cells],
        width-2*request.margin, request.gap, 'width')
    x_prefix = tuple(accumulate(widths, initial=0.))
    natural_heights, natural_plots = _natural_sizes(request, context, x_prefix, height, decorate)
    heights = _row_tracks(request, rows, natural_heights)
    if height is not None:
        heights = _fit_rows(request, rows, heights, natural_heights, natural_plots, height)
    boxes = _cell_boxes(request, x_prefix, heights)
    margins = {c.name: (0., 0., 0., 0.) for c in request.cells}
    steps, nodes = {}, None
    # Tick selection depends on width; grow furniture and tracks to a stable fit.
    for iteration in range(24):
        nodes, measured = _measure_cells(request, context, boxes, margins, decorate, nodes)
        _share_margins(request, measured, margins)
        if natural_plots and _grow_natural_heights(request, natural_plots, measured, natural_heights):
            heights = _row_tracks(request, rows, natural_heights)
            if height is not None:
                heights = _fit_rows(request, rows, heights, natural_heights, natural_plots, height)
            boxes = _cell_boxes(request, x_prefix, heights)
            margins = measured
            continue
        if all(max(abs(a-b) for a, b in zip(measured[n], margins[n])) < .005 for n in margins):
            break
        margins = _extrapolate(margins, measured, steps)
    else:
        raise LayoutError('plot furniture did not settle after 24 measurement passes')
    content, handles = _place_cells(request.cells, nodes, boxes, margins,
                                    request.letters.get('anchor') == 'cell')
    with themed(context.theme):
        content = _route_links(content, handles, request.links, context.theme)
    page_height = (height if height is not None else
                   2*request.margin+sum(heights)+request.row_gap*(rows-1))
    report = _layout_report(request, heights, widths, natural_heights, boxes, handles)
    natural = _row_tracks(request, rows, natural_heights)
    report['natural_height'] = 2*request.margin+sum(natural)+request.row_gap*(rows-1)
    return LayoutResult(content, boxes, handles, page_height, iteration+1, report)


def _layout_report(request, heights, widths, natural_heights, boxes, handles):
    """What set each row track, and the space each cell leaves unused.

    A cell sets its rows when its natural height, or its `min_height`, fills
    them: shortening it is the only way to shorten those rows. A plot fills
    its cell unless an aspect leaves slack; other content, and an aspect plot,
    is measured against its box.
    """
    rows = []
    for index, height in enumerate(heights):
        binding = []
        for cell in request.cells:
            if not cell.row <= index < cell.row+cell.rowspan:
                continue
            span = sum(heights[cell.row:cell.row+cell.rowspan])+request.row_gap*(cell.rowspan-1)
            natural = natural_heights.get(cell.name, 0.)
            need = max(natural, cell.min_height)
            if need >= span-.05:
                binding.append(cell.name if natural >= cell.min_height else f'{cell.name} (min_height)')
        rows.append({'height': height, 'set_by': binding})
    cells = {}
    for cell in request.cells:
        box = boxes[cell.name]
        if isinstance(cell.item, PlotSpec) and 'aspect' not in cell.item.options:
            cells[cell.name] = {'unused_width': 0., 'unused_height': 0.}
            continue
        ink = handles[cell.name].bbox
        cells[cell.name] = {'unused_width': max(0., box.width-ink.width),
                            'unused_height': max(0., box.height-ink.height)}
    return {'rows': rows, 'columns': list(widths), 'cells': cells, 'choices': {}}
