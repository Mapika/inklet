"""Reusable scientific diagram components with named connection points.

These return ordinary Diagrams: compose them with stacks/grids and connect
`component.at('input')` or `component.at('output')` after layout.
"""
from __future__ import annotations

import math
from .core import Diagram, DiagramError, Vec2, mm
from .draw.coords import active_theme

__all__ = ['feature_matrix', 'sequence', 'database']


def _positive(value, name):
    value = mm(value)
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f'{name} must be finite and positive')
    return value


def _nonnegative(value, name):
    value = mm(value)
    if not math.isfinite(value) or value < 0:
        raise ValueError(f'{name} must be finite and non-negative')
    return value


def _label(value):
    import inklet
    return value.copy() if isinstance(value, Diagram) else inklet.text(str(value), markup=False)


def _ports(node):
    b = node.local_bbox
    node.anchor('input', Vec2(b.x0, 0))
    node.anchor('output', Vec2(b.x1, 0))
    return node


def sequence(items, *, pitch=None, gap=None, stem=0, baseline=False, **style):
    """A row of text or diagram symbols with `item-0`, ... and input/output ports.

    An explicit `pitch` aligns a sequence with matrix columns. Otherwise the
    widest symbol plus the theme gap determines the pitch. Symbols are copied,
    so the same marker may safely occur more than once.
    """
    import inklet
    nodes = [_label(item) for item in items]
    if not nodes:
        raise DiagramError('sequence requires at least one symbol')
    th = active_theme()
    gap = th.gap('xs') if gap is None else _nonnegative(gap, 'gap')
    pitch = max(n.width for n in nodes)+gap if pitch is None else _positive(pitch,'pitch')
    stem = mm(stem)
    if not math.isfinite(stem) or stem < 0:
        raise ValueError('stem must be finite and non-negative')
    xs = [(i-(len(nodes)-1)/2)*pitch for i in range(len(nodes))]
    parts = [((x,0), node) for x,node in zip(xs,nodes)]
    if stem:
        for x,node in zip(xs,nodes):
            parts.append(inklet.polyline([(x,node.height/2),(x,node.height/2+stem)],**style))
    if baseline:
        y = max(n.height for n in nodes)/2+stem
        parts.append(inklet.polyline([(xs[0]-pitch/2,y),(xs[-1]+pitch/2,y)],**style))
    node = inklet.drawn(parts,kind='sequence')
    for i,x in enumerate(xs):node.anchor(f'item-{i}',Vec2(x,0))
    return _ports(node)


def feature_matrix(values, *, row_labels=None, column_labels=None, cell=4,
                   ramp=None, label=None, highlight_rows=(), gap=None, **style):
    """A matrix with text/diagram headers and named row/column connection points.

    `row-0`, ... lie on the left edge of the complete row headers; `column-0`,
    ... lie above the column headers. `cell` is the physical square-cell size.
    Values are row-major and colours use the ordinary panel.matrix ramp.
    """
    import inklet
    rows = [tuple(row) for row in values]
    if not rows or not rows[0] or any(len(row)!=len(rows[0]) for row in rows):
        raise DiagramError('feature_matrix needs a non-empty rectangular array')
    nr,nc = len(rows),len(rows[0])
    row_labels = None if row_labels is None else tuple(row_labels)
    column_labels = None if column_labels is None else tuple(column_labels)
    if row_labels is not None and len(row_labels)!=nr:
        raise DiagramError('feature_matrix needs one row label per row')
    if column_labels is not None and len(column_labels)!=nc:
        raise DiagramError('feature_matrix needs one column label per column')
    cell = _positive(cell,'cell');th=active_theme()
    gap = th.gap('xs') if gap is None else _nonnegative(gap, 'gap')
    highlights=tuple(highlight_rows)
    if any(not isinstance(i,int) or isinstance(i,bool) or not 0<=i<nr for i in highlights):
        raise DiagramError('highlight_rows must contain valid row indices')
    w,h = nc*cell,nr*cell
    p=inklet.panel(w,h)
    p.matrix(rows,ramp=inklet.ramp(['#fff',th.accent]) if ramp is None else ramp,raster=False)
    p.outline(**style)
    parts=[p.build()]
    ys=[-h/2+(i+.5)*cell for i in range(nr)]
    xs=[-w/2+(i+.5)*cell for i in range(nc)]
    if row_labels is not None:
        for y,value in zip(ys,row_labels):
            text=_label(value);parts.append(((-w/2-gap-text.width/2,y),text))
    if column_labels is not None:
        for x,value in zip(xs,column_labels):
            text=_label(value);parts.append(((x,-h/2-gap-text.height/2),text))
    for i in highlights:
        parts.append(((0,ys[i]),inklet.box(width=w,height=cell,pad=0,radius=0,
                                          fill='none',stroke=th.accent,stroke_width=th.stroke)))
    if label is not None:parts.append(((0,0),_label(label)))
    node=inklet.drawn(parts,kind='feature-matrix')
    b=node.local_bbox
    for i,y in enumerate(ys):node.anchor(f'row-{i}',Vec2(b.x0,y))
    for i,x in enumerate(xs):node.anchor(f'column-{i}',Vec2(x,b.y0))
    node.anchor('matrix-nw',Vec2(-w/2,-h/2))
    node.anchor('matrix-se',Vec2(w/2,h/2))
    return _ports(node)


def database(content, *, width=None, height=None, pad=None, **style):
    """A labelled cylinder with input/output ports on its vertical sides."""
    import inklet
    th=active_theme();text=_label(content)
    pad=th.gap('s') if pad is None else _nonnegative(pad, 'pad')
    w=max(text.width+2*pad,18) if width is None else _positive(width,'width')
    cap=min(w*.12,3)
    h=max(text.height+2*pad+2*cap,14) if height is None else _positive(height,'height')
    if h<=2*cap:raise ValueError('database height must leave room between its end caps')
    # Lower half of an ellipse, with straight sides and a closed top.
    left,right,top,bottom=-w/2,w/2,-h/2+cap,h/2-cap
    k=.55228475
    curves=[((left,top),(left,top),(left,bottom),(left,bottom)),
            ((left,bottom),(left,bottom+k*cap),(-k*w/2,bottom+cap),(0,bottom+cap)),
            ((0,bottom+cap),(k*w/2,bottom+cap),(right,bottom+k*cap),(right,bottom)),
            ((right,bottom),(right,bottom),(right,top),(right,top)),
            ((right,top),(right,top),(left,top),(left,top))]
    paint=dict(fill=th.paper,stroke=th.ink,stroke_width=th.stroke)
    paint.update(style)
    body=inklet.path(curves=curves,closed=True,**paint)
    lid=inklet.circle(width=w,height=2*cap,pad=0,**paint)
    node=inklet.drawn([body,((0,top),lid),((0,cap/2),text)],kind='database')
    return _ports(node)
