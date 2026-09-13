"""Measured labels arranged along a bounded vertical rail."""
from __future__ import annotations

import math
from ..core import Diagram, Vec2, mm


def label_column(labels, targets, *, x, bounds, side='right', gap=1,
                 leader_color='#777777', leader_width=.2) -> Diagram:
    """Place measured label Diagrams beside points without vertical overlap.

    ``targets`` are (x, y) pairs in the drawing frame. ``x`` is the near edge
    of the label column; ``bounds=(top,bottom)`` limits the full text extent.
    ``side='right'`` puts labels to the right of the rail, ``'left'`` to its
    left. Labels retain their original size and their association with each
    target. Leaders end at the measured label edge.

    Minimizes squared vertical displacement while preserving target order,
    using bounded isotonic regression. Raises when the labels cannot fit;
    does not shrink text or hide labels. This only avoids label–label overlap
    within the column, not other scene content. Returns absolute coordinates,
    with input-order target/label boxes in ``notes['label_column']``.
    """
    from ..draw import as_drawn, polyline
    labels = tuple(labels)
    targets = tuple(v if isinstance(v, Vec2) else Vec2(*v) for v in targets)
    if len(labels) != len(targets):
        raise ValueError('label_column needs one target per label')
    if side not in ('left', 'right'):
        raise ValueError('label_column side must be left or right')
    x, gap, width = mm(x), mm(gap), mm(leader_width)
    top, bottom = (mm(v) for v in bounds)
    if not all(math.isfinite(v) for v in (x, gap, width, top, bottom)) or gap < 0 or width <= 0 or bottom < top:
        raise ValueError('label_column needs finite bounds and positive leader width, nonnegative gap')
    if any(not math.isfinite(v.x) or not math.isfinite(v.y) for v in targets):
        raise ValueError('label_column targets must be finite')
    if any(not isinstance(v, Diagram) or v.bbox is None for v in labels):
        raise ValueError('label_column labels must be nonempty Diagrams')
    if not labels:
        return Diagram(kind='label-column', notes={'label_column': []})
    order = sorted(range(len(labels)), key=lambda k: (targets[k].y, k))
    heights = [labels[k].bbox.height for k in order]
    if not all(math.isfinite(h) for h in heights):
        raise ValueError('label_column labels must have finite extents')
    if sum(heights) + gap * (len(labels)-1) > bottom-top + 1e-9:
        raise ValueError('label_column labels do not fit within bounds; enlarge the column')
    offsets = [0.]
    for a, b in zip(heights, heights[1:]):
        offsets.append(offsets[-1] + (a+b)/2 + gap)
    # Pool adjacent violations of the ordered, clearance-adjusted centers.
    blocks = []
    for j, k in enumerate(order):
        blocks.append([targets[k].y-offsets[j], 1])
        while len(blocks)>1 and blocks[-2][0]/blocks[-2][1] > blocks[-1][0]/blocks[-1][1]:
            total, count = blocks.pop()
            blocks[-1][0] += total; blocks[-1][1] += count
    lo, hi = top+heights[0]/2, bottom-heights[-1]/2-offsets[-1]
    levels = [max(lo, min(hi, total/count)) for total, count in blocks for _ in range(count)]
    placed, leaders, notes = [], [], [None]*len(labels)
    for j, k in enumerate(order):
        box = labels[k].bbox
        cy = levels[j]+offsets[j]
        node = labels[k].translated(x-(box.x0 if side=='right' else box.x1), cy-box.center.y)
        end = Vec2(x, cy)
        elbow = Vec2(x-gap if side=='right' else x+gap, cy)
        if leader_color is not None:
            leaders.append(as_drawn(polyline([targets[k], elbow, end], stroke=leader_color,
                                            stroke_width=width, fill='none')))
        placed.append(node)
        b = node.bbox
        notes[k] = {'target': (targets[k].x, targets[k].y), 'box': (b.x0,b.y0,b.x1,b.y1)}
    return Diagram(children=tuple(leaders+placed), kind='label-column', notes={'label_column': notes})
