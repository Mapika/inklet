"""Experimental: pack cells into nested rows and stacks instead of a grid.

Journal figures are rarely one grid. A tall drawing sits beside two stacked
plots, a wide plot spans under three small ones. `document(pack=True)` lays
cells out as a slicing floorplan: the page, in reading order, is split into
a left and right part or a top and bottom part, and so on down to single
cells. Only runs of consecutive cells are grouped, so panel letters still
read left to right and top to bottom.

Each cell is measured at a few widths to learn its height at each width.
A dynamic program over runs of cells and a coarse width grid finds the
arrangement with the shortest page, and a second pass settles the widths of
that arrangement on a fine grid. Plots pay for straying from their authored
aspect ratio, and drawings for width they leave empty, so ties go to layouts
that look like the author's panels.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, replace

from ..core import DiagramError, Rect
from .errors import LayoutError
from .spec import Choice, PlotSpec, themed

_STEP = .5       # mm, fine width grid
_COARSE = 2.5    # mm, width grid while choosing the arrangement
_ASPECT = 4.     # mm of page height per unit of log aspect a plot strays
_STRETCH = 1.25  # a plot this much wider than authored is charged for the rest
_NARROW = .6     # a plot's data is never narrower than this share of authored
_DATA = 15.      # mm, narrowest data region a packed plot is offered
_WASTE = 1.      # empty cell area, charged as page height of the same area
_FLAT = .5       # mm, height change that counts as a drawing growing
_KNEE = 4.       # mm, how closely the knee of a drawing is found
_GROW = 1.5      # a drawing grows to at most this multiple of its least height
_INF = math.inf


@dataclass
class _Option:
    item: object
    heights: list         # page height at each grid width
    costs: list           # penalty, as page height, at each grid width
    draws: list           # width the content is drawn at, per grid width
    measure: object       # drawn width -> exact height
    grows: float          # weight when a fixed page height stretches stacks
    margins: tuple = (0., 0., 0., 0.)
    node: object = None   # drawn width -> undecorated build
    refine: object = None  # drawn width -> True when the estimate was off
    fill: object = None   # (drawn width, height) -> undecorated build given that height


def _drawn(option, width, cell, box, decorate):
    """The build for a placed cell. Responsive content in a box taller than
    it asked for is offered that height, as a grid cell is, and keeps the
    offer only when the result still fits its box."""
    bare = option.node(width)
    node = decorate(bare, cell)
    if option.fill is None or box.height <= node.height+.5:
        return node
    try:
        taller = option.fill(width, box.height-(node.height-bare.bbox.height))
    except (LayoutError, DiagramError, ValueError):
        return node
    offered = decorate(taller, cell)
    if offered.height > box.height+.05 or offered.width > box.width+.05:
        return node
    return offered


def _fits(measure, width):
    try:
        return measure(width)
    except (LayoutError, DiagramError, ValueError):
        return None


def _interp(x, xs, ys):
    if x <= xs[0]:
        return ys[0]
    for n in range(1, len(xs)):
        if x <= xs[n]:
            t = (x-xs[n-1])/(xs[n]-xs[n-1])
            return ys[n-1]+t*(ys[n]-ys[n-1])
    return ys[-1]


def _waste(width, ink, height):
    """Empty width beside content, as page height of the same area."""
    return _WASTE*max(width-ink, 0.)*height


def _plot(item, cell, context, decorate, grid):
    """A plot keeps its authored data height at any width, so one build
    gives its height; its labels set the narrowest cell it fits."""
    try:
        node = decorate(context.build(item, item.width, item.height), cell)
    except (LayoutError, DiagramError, ValueError):
        return None
    furniture, height = node.width-item.width, node.height
    authored = item.width+furniture

    # Labels and keys widen or wrap as data narrows: build the narrowest
    # data region once, and use its height for widths short of authored.
    floor, narrow = authored, height
    least = max(_DATA, _NARROW*item.width)
    for data in (least, (least+item.width)/2):
        if data >= item.width:
            break
        built = _fits(lambda d: decorate(context.build(item, d, item.height), cell), data)
        if built is not None:
            floor, narrow = max(cell.min_width, built.width), max(built.height, height)
            break
    if floor > grid[-1]+1e-6:
        return None
    heights, costs = [], []
    for width in grid:
        if width < floor-1e-6:
            heights.append(_INF)
            costs.append(0.)
            continue
        drawn = max(narrow if width < authored else height, cell.min_height)
        heights.append(drawn)
        # Past a moderate stretch, the extra width reads as empty area.
        stretch = max(0., width-furniture-_STRETCH*item.width)
        costs.append(_ASPECT*abs(math.log(max(width-furniture, 1e-6)/item.width))
                     + _WASTE*stretch*drawn/grid[-1])
    from .layout import plot_margins
    return _Option(item, heights, costs, list(grid), lambda width: narrow if width < authored else height,
                   item.height, plot_margins(node))


def _fixed_art(item, cell, context, decorate, grid):
    node = decorate(context.build(item), cell)
    floor = max(cell.min_width, node.width)
    if floor > grid[-1]+1e-6:
        return None
    height = max(node.height, cell.min_height)
    heights = [height if width >= floor-1e-6 else _INF for width in grid]
    costs = [_waste(width, node.width, height)/grid[-1] if width >= floor-1e-6 else 0. for width in grid]
    return _Option(item, heights, costs, list(grid), lambda width: node.height, 0.,
                   node=lambda width: context.build(item))


def _responsive(item, cell, context, decorate, grid):
    """Content that fills its width: measure a few widths and interpolate.

    Drawings that scale with width are close to linear between samples;
    the chosen width is measured again exactly once the page is settled.
    """
    available = grid[-1]
    letter, seen = [], {}

    def build(width, height=None):
        # Round down, so a cached build never overhangs its cell.
        return context.build(item, math.floor(width*10+1e-6)/10,
                             None if height is None else math.floor(height*10+1e-6)/10)

    def raw(width):
        """(height, ink width) of the cell drawn `width` wide, letter included."""
        key = math.floor(width*10+1e-6)
        if key not in seen:
            try:
                bare = build(width-(letter[0] if letter else 0.))
            except (LayoutError, DiagramError, ValueError):
                seen[key] = None
            else:
                node = decorate(bare, cell)
                if not letter:
                    # The letter's overhang is known only after a build;
                    # a build that overhangs because of it is repeated.
                    letter.append(node.width-bare.width)
                    if node.width > width+.05:
                        return raw(width)
                seen[key] = (node.height, node.width) if node.width <= width+.05 else ('wide', node.width)
        return seen[key]

    # Find the narrowest width that fits: a drawing too wide for its cell
    # reports the width it needs, so try that next.
    width, found = max(cell.min_width, 10.), None
    for _ in range(8):
        value = raw(width)
        if value is not None and value[0] != 'wide':
            found = value
            break
        if width >= available:
            break
        width = min(available, value[1]+.5 if value is not None else max(width*1.4, width+8.))
    if found is None:
        return None
    floor = width
    points = {floor: found}
    for width in ((floor+available)/2, available):
        value = raw(width) if width-floor >= 5. else None
        if value is not None and value[0] != 'wide':
            points[width] = value
    # A drawing that keeps one height as it narrows, then grows as it
    # widens, is set by its fixed-size text and keys at narrow widths: its
    # drawing is smaller than its labels. Never draw it narrower than the
    # width where the drawing starts to set the height.
    ordered = sorted(points)
    rising = [x for x in ordered if points[x][0] > found[0]+_FLAT]
    if rising:
        # Past the knee the height grows about linearly: extend the line
        # through the rising samples back to the flat height, and check it
        # with one build.
        high = rising[0]
        low = max(x for x in ordered if x < high)
        after = rising[1] if len(rising) > 1 else None
        if after is not None and points[after][0] > points[high][0]:
            slope = (points[after][0]-points[high][0])/(after-high)
        else:
            slope = (points[high][0]-points[low][0])/(high-low)
        knee = min(high, max(low, high-(points[high][0]-found[0])/slope))
        if knee-floor > _KNEE/2:
            value = raw(knee)
            if value is not None and value[0] != 'wide':
                floor = knee
                points = {x: v for x, v in points.items() if x >= floor}
                points[floor] = value
    option = _Option(item, [], [], [], None, 0., node=lambda width: build(width-letter[0]),
                     fill=lambda width, height: build(width-letter[0], height))

    def fit():
        xs = sorted(points)
        hs, inks = [points[x][0] for x in xs], [points[x][1] for x in xs]
        # Past a comfortable size a drawing stops growing and sits in its
        # box: text keeps its size, so a huge drawing reads out of scale.
        cap = _GROW*hs[0]
        top = xs[-1]
        for n in range(1, len(xs)):
            if hs[n] > cap:
                top = xs[n-1]+(cap-hs[n-1])/(hs[n]-hs[n-1])*(xs[n]-xs[n-1])
                break
        option.heights, option.costs, option.draws = [], [], []
        for width in grid:
            if width < floor-1e-6:
                option.heights.append(_INF)
                option.costs.append(0.)
                option.draws.append(width)
                continue
            drawn = min(width, top)
            height = max(_interp(drawn, xs, hs), cell.min_height)
            option.heights.append(height)
            option.costs.append(_waste(width, _interp(drawn, xs, inks), height)/available)
            option.draws.append(drawn)
        option.grows = hs[0]
    fit()

    def height(width):
        value = raw(width)
        if value is None or value[0] == 'wide':
            return _interp(width, sorted(points), [points[x][0] for x in sorted(points)])
        points.setdefault(width, value)
        return value[0]

    def refine(width):
        """Measure a drawn width exactly; True if the estimate was off."""
        xs = sorted(points)
        predicted = _interp(width, xs, [points[x][0] for x in xs])
        actual = height(width)
        fit()
        return abs(actual-predicted) > .5
    option.measure, option.refine = height, refine
    return option


def _option(item, cell, context, decorate, grid):
    from .layout import _fixed
    if isinstance(item, PlotSpec):
        return _plot(item, cell, context, decorate, grid)
    if _fixed(item):
        return _fixed_art(item, cell, context, decorate, grid)
    return _responsive(item, cell, context, decorate, grid)


def _options(request, context, decorate, grid):
    found = []
    for cell in request.cells:
        items = cell.item.options if isinstance(cell.item, Choice) else (cell.item,)
        options = [_option(item, cell, context, decorate, grid) for item in items]
        options = [(n, o) for n, o in enumerate(options) if o is not None]
        if not options:
            raise LayoutError(f'cell {cell.name!r} is wider than the page')
        found.append(options)
    return found


def _profiles(found, size):
    """Each cell's best alternative, with its height and cost, per width."""
    profiles = []
    for options in found:
        heights, costs, picks = [], [], []
        for w in range(size):
            pick = min(range(len(options)), key=lambda n: options[n][1].heights[w]+options[n][1].costs[w])
            heights.append(options[pick][1].heights[w])
            costs.append(options[pick][1].costs[w])
            picks.append(pick)
        profiles.append((heights, costs, picks, options))
    return profiles


def _floor(heights):
    return next((w for w, h in enumerate(heights) if h < _INF), len(heights))


def _beside(a, b, size, gap, rate, around=None):
    """Side by side at each width: min over splits of the taller side.

    The shorter side leaves a hole as tall as the difference, charged as
    empty area. `around(width)` limits the splits to a window.
    """
    (ha, ca), (hb, cb) = a, b
    fa, fb = _floor(ha), _floor(hb)
    heights, costs, firsts = [_INF]*size, [0.]*size, [0]*size
    for width in range(fa+gap+fb, size):
        low, high = fa, width-gap-fb
        if around is not None:
            middle, radius = around(width)
            # A coarse split can round past a fine floor; keep the nearest
            # split that fits rather than none.
            middle = min(max(middle, low), high)
            low, high = max(low, middle-radius), min(high, middle+radius)
        best = _INF
        for left in range(low, high+1):
            right = width-gap-left
            x, y = ha[left], hb[right]
            if x > y:
                height, cost = x, ca[left]+cb[right]+(x-y)*right*rate
            else:
                height, cost = y, ca[left]+cb[right]+(y-x)*left*rate
            # A hair of cost for lopsided splits breaks ties toward even widths.
            cost += 1e-4*abs(left-right)
            if height+cost < best:
                best, heights[width], costs[width], firsts[width] = height+cost, height, cost, left
    return heights, costs, firsts


def _stack(a, b, row_gap):
    (ha, ca), (hb, cb) = a, b
    return [x+row_gap+y for x, y in zip(ha, hb)], [x+y for x, y in zip(ca, cb)]


def _arrange(profiles, size, gap, row_gap, rate):
    """Shortest slicing layout of every run of cells, on a width grid."""
    count = len(profiles)
    best = {}
    for n, (heights, costs, _, _) in enumerate(profiles):
        best[n, n+1] = (heights, costs, None)
    for length in range(2, count+1):
        for i in range(count-length+1):
            j = i+length
            heights, costs, how = [_INF]*size, [0.]*size, [None]*size
            for k in range(i+1, j):
                a, b = best[i, k][:2], best[k, j][:2]
                for kind, (hs, cs, *first) in (('stack', (*_stack(a, b, row_gap),)),
                                               ('beside', _beside(a, b, size, gap, rate))):
                    for w in range(size):
                        if hs[w]+cs[w] < heights[w]+costs[w]:
                            heights[w], costs[w] = hs[w], cs[w]
                            how[w] = (kind, k, first[0][w] if first else None)
            best[i, j] = (heights, costs, how)
    return best


def _structure(best, i, j, width):
    """The arrangement chosen for run [i, j) at `width`, with coarse widths."""
    if j == i+1:
        return ['cell', i, width]
    kind, k, first = best[i, j][2][width]
    if kind == 'stack':
        return ['stack', _structure(best, i, k, width), _structure(best, k, j, width), width]
    return ['beside', _structure(best, i, k, first), _structure(best, k, j, width-first-best['gap']),
            width, first]


def _settle(node, profiles, size, gap, row_gap, rate, scale, out):
    """Fine heights and costs of a fixed arrangement at every width."""
    if node[0] == 'cell':
        result = profiles[node[1]][:2]
    else:
        a = _settle(node[1], profiles, size, gap, row_gap, rate, scale, out)
        b = _settle(node[2], profiles, size, gap, row_gap, rate, scale, out)
        if node[0] == 'stack':
            result = _stack(a, b, row_gap)
        else:
            share, radius = node[4]/max(node[3], 1), math.ceil(2*scale)
            heights, costs, firsts = _beside(a, b, size, gap, rate,
                                             lambda width: (round(width*share), radius))
            out[id(node)] = firsts
            result = heights, costs
    return result


def _place(node, width, profiles, firsts, gap):
    """Leaves ('cell', index, alternative, grid width) at their fine widths."""
    if node[0] == 'cell':
        return ('cell', node[1], profiles[node[1]][2][width], width)
    if node[0] == 'stack':
        return ('stack', _place(node[1], width, profiles, firsts, gap),
                _place(node[2], width, profiles, firsts, gap), width)
    left = firsts[id(node)][width]
    return ('beside', _place(node[1], left, profiles, firsts, gap),
            _place(node[2], width-left-gap, profiles, firsts, gap), width)


def _leaves(node):
    if node[0] == 'cell':
        yield node
    else:
        yield from _leaves(node[1])
        yield from _leaves(node[2])


def _solve(profiles, count, gap, row_gap, step, available):
    """Choose an arrangement on a coarse grid, then settle it on the fine one."""
    rate = _WASTE*step/available
    # A coarse step that divides the gap keeps gaps exact, so an arrangement
    # that fits the coarse grid fits the fine one: floors only round up.
    target = _COARSE/step
    steps = [d for d in range(1, gap+1) if gap % d == 0] or [max(1, round(target))]
    scale = min(steps, key=lambda d: (abs(math.log(d/target)), -d))
    coarse = count//scale
    small = [([p[0][k*scale] for k in range(coarse+1)], [p[1][k*scale] for k in range(coarse+1)],
              None, None) for p in profiles]
    best = _arrange(small, coarse+1, gap//scale, row_gap, rate*scale)
    if math.isfinite(best[0, len(profiles)][0][coarse]):
        best['gap'] = gap//scale
        tree = _settled(best, profiles, count, gap, row_gap, rate, scale, coarse)
        if tree:
            return tree
    # The last partial coarse step can be what fits; the fine grid is exact.
    best = _arrange(profiles, count+1, gap, row_gap, rate)
    if not math.isfinite(best[0, len(profiles)][0][count]):
        raise LayoutError('the cells cannot be packed into the page width')
    best['gap'] = gap
    return _settled(best, profiles, count, gap, row_gap, rate, 1, count)


def _settled(best, profiles, count, gap, row_gap, rate, scale, coarse):
    """The chosen arrangement at fine widths, or None if it no longer fits."""
    structure = _structure(best, 0, len(profiles), coarse)
    firsts = {}
    heights, _ = _settle(structure, profiles, count+1, gap, row_gap, rate, scale, firsts)
    if not math.isfinite(heights[count]):
        return None
    return _place(structure, count, profiles, firsts, gap)


def _heights(node, profiles, step, row_gap, found):
    """Measure settled widths exactly: (height, growth weight) per node."""
    if node[0] == 'cell':
        _, index, alt, width = node
        option = profiles[index][3][alt][1]
        height = option.measure(option.draws[width])
        found[id(node)] = (height, option.grows)
        return found[id(node)]
    a = _heights(node[1], profiles, step, row_gap, found)
    b = _heights(node[2], profiles, step, row_gap, found)
    if node[0] == 'beside':
        found[id(node)] = (max(a[0], b[0]), max(a[1], b[1]))
    else:
        found[id(node)] = (a[0]+row_gap+b[0], a[1]+b[1])
    return found[id(node)]


def _boxes(node, x, y, height, step, gap, row_gap, found, out):
    if node[0] == 'cell':
        out[node[1]] = (Rect(x, y, x+node[3]*step, y+height), node[2], node[3])
        return
    first, second = node[1], node[2]
    if node[0] == 'beside':
        _boxes(first, x, y, height, step, gap, row_gap, found, out)
        _boxes(second, x+(first[3]+gap)*step, y, height, step, gap, row_gap, found, out)
        return
    (a, grow_a), (b, grow_b) = found[id(first)], found[id(second)]
    surplus = height-a-b-row_gap
    weights = (grow_a, grow_b) if grow_a+grow_b > 0 else (a, b)
    top = a+surplus*weights[0]/sum(weights)
    _boxes(first, x, y, top, step, gap, row_gap, found, out)
    _boxes(second, x, y+top+row_gap, height-top-row_gap, step, gap, row_gap, found, out)


def _describe(node, cells):
    if node[0] == 'cell':
        return cells[node[1]].name
    joiner = ' | ' if node[0] == 'beside' else ' / '
    parts = [_describe(child, cells) for child in node[1:3]]
    return '(' + joiner.join(parts) + ')'


def pack_document(request, context, width, height):
    from .layout import (LayoutResult, _decorator, _extrapolate, _measure_cells, _place_cells,
                         _route_links)
    decorate = _decorator(request, context)
    available = width-2*request.margin
    count = max(1, round(available/_STEP))
    step = available/count
    grid = [n*step for n in range(count+1)]
    gap = math.ceil(request.gap/step-1e-9)
    found = _options(request, context, decorate, grid)
    # Estimates between samples can be off; measure the widths chosen and
    # solve again until the chosen layout's estimates hold.
    for _ in range(6):
        profiles = _profiles(found, count+1)
        tree = _solve(profiles, count, gap, request.row_gap, step, available)
        revised = False
        for leaf in _leaves(tree):
            option = profiles[leaf[1]][3][leaf[2]][1]
            if option.refine and option.refine(option.draws[leaf[3]]):
                revised = True
        if not revised:
            break
    found = {}
    natural = _heights(tree, profiles, step, request.row_gap, found)[0]
    if height is not None and natural > height-2*request.margin+1e-6:
        raise LayoutError(f'packed cells need {natural+2*request.margin:.2f} mm of height; '
                          f'the page has {height:.2f} mm')
    inner = natural if height is None else height-2*request.margin
    placed = {}
    _boxes(tree, request.margin, request.margin, inner, step, gap, request.row_gap, found, placed)
    options = [profiles[n][3][placed[n][1]][1] for n in range(len(request.cells))]
    cells = tuple(replace(c, item=options[n].item) for n, c in enumerate(request.cells))
    authored, request = request, replace(request, cells=cells)
    boxes = {c.name: placed[n][0] for n, c in enumerate(cells)}
    for n, c in enumerate(cells):
        # A plot beside a taller neighbor fills its box only so far: past
        # that its marks stretch, so it keeps the top of the box instead.
        if isinstance(c.item, PlotSpec):
            box = boxes[c.name]
            most = _GROW*options[n].measure(options[n].draws[placed[n][2]])
            if box.height > most+1e-6:
                boxes[c.name] = Rect(box.x0, box.y0, box.x1, box.y0+most)
    # Drawings and responsive content keep the build measured for the width
    # they are drawn at and sit in their box by `align`; plots fill theirs.
    nodes = {c.name: _drawn(options[n], options[n].draws[placed[n][2]], c, boxes[c.name], decorate)
             for n, c in enumerate(cells) if not isinstance(c.item, PlotSpec)}
    margins = {c.name: (0., 0., 0., 0.) for c in cells}
    plots = replace(request, cells=tuple(c for c in cells if isinstance(c.item, PlotSpec)))
    current = {c.name: options[n].margins for n, c in enumerate(cells) if isinstance(c.item, PlotSpec)}
    steps, iteration = {}, 0
    for iteration in range(24 if plots.cells else 0):
        built, measured = _measure_cells(plots, context, boxes, current, decorate)
        # Monotonic margins prevent tick-thinning oscillations.
        measured = {n: tuple(max(a, b) for a, b in zip(measured[n], current[n])) for n in current}
        if all(max(abs(a-b) for a, b in zip(measured[n], current[n])) < .005 for n in current):
            break
        current = _extrapolate(current, measured, steps)
    else:
        if plots.cells:
            raise LayoutError('plot furniture did not settle after 24 measurement passes')
    if plots.cells:
        nodes |= built
        margins |= current
    content, handles = _place_cells(cells, nodes, boxes, margins,
                                    request.letters.get('anchor') == 'cell')
    with themed(context.theme):
        content = _route_links(content, handles, request.links, context.theme)
    page = 2*request.margin+natural
    report = {'rows': [], 'columns': [], 'choices': {}, 'natural_height': page,
              'packing': _describe(tree, cells), 'cells': {}}
    for cell in request.cells:
        box = boxes[cell.name]
        ink = handles[cell.name].bbox
        report['cells'][cell.name] = (
            {'unused_width': 0., 'unused_height': 0.} if isinstance(cell.item, PlotSpec) else
            {'unused_width': max(0., box.width-ink.width), 'unused_height': max(0., box.height-ink.height)})
    report['choices'] = {c.name: c.item.names[profiles[n][3][placed[n][1]][0]]
                         for n, c in enumerate(authored.cells) if isinstance(c.item, Choice)}
    return LayoutResult(content, boxes, handles, page if height is None else height,
                        iteration+1, report)
