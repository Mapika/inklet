"""Offline execution of a native compiled scene with bounded GPU marker layers."""
import base64
import html
import json
import math
from pathlib import Path
import re

from ...core import EllipsePrim, RectPrim, PathPrim
from ...themes.color import parse_color
from ...render.svg import _render_svg


def _simple_polygon(points):
    # A distance to every edge is valid only when every edge bounds the fill.
    # Self-intersections can separate two filled winding regions and would
    # produce false antialiased seams, so keep those shapes in native SVG.
    def cross(a, b, c):
        return (b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0])

    edges = list(zip(points, points[1:] + points[:1]))
    for j, (a, b) in enumerate(edges):
        for k in range(j+1, len(edges)):
            if k == j+1 or (j == 0 and k == len(edges)-1):
                continue
            c, d = edges[k]
            if (max(a[0], b[0]) < min(c[0], d[0]) or max(c[0], d[0]) < min(a[0], b[0])
                    or max(a[1], b[1]) < min(c[1], d[1]) or max(c[1], d[1]) < min(a[1], b[1])):
                continue
            if cross(a,b,c)*cross(a,b,d) <= 0 and cross(c,d,a)*cross(c,d,b) <= 0:
                return False
    return sum(a[0]*b[1]-a[1]*b[0] for a,b in edges) != 0


def _marker_geometry(shape):
    """Keep exact unit geometry; curved/open/compound paths stay native."""
    if isinstance(shape, EllipsePrim) and shape.rx == shape.ry and shape.rx > 0:
        return dict(radius=shape.rx, vertices=[], fill_rule='nonzero',
                    bounds=[-shape.rx, -shape.ry, shape.rx, shape.ry])
    if isinstance(shape, RectPrim) and shape.radius == 0:
        x, y = shape.width / 2, shape.height / 2
        points = [(-x, -y), (x, -y), (x, y), (-x, y)]
        rule = 'nonzero'
    elif isinstance(shape, PathPrim) and shape.filled and len(shape.subpaths) == 1:
        sub = shape.subpaths[0]
        if not sub.closed or sub.curves:
            return None
        points = [(p.x, p.y) for p in sub.points]
        rule = shape.fill_rule
    else:
        return None
    # Remove repeated edge endpoints before calculating distances in the shader.
    points = [p for k, p in enumerate(points) if p != points[k-1]]
    if not 3 <= len(points) <= 16 or not all(math.isfinite(v) for p in points for v in p):
        return None
    xs, ys = zip(*points)
    if min(xs) == max(xs) or min(ys) == max(ys):
        return None
    if not _simple_polygon(points):
        return None
    return dict(radius=0, vertices=points, fill_rule=rule,
                bounds=[min(xs), min(ys), max(xs), max(ys)])


def to_html(scene, *, title='Inklet figure', backend='auto', **options):
    if backend not in ('auto', 'webgl2', 'canvas', 'svg'):
        raise ValueError("scene viewer backend must be 'auto', 'webgl2', 'canvas' or 'svg'")
    if not isinstance(title, str):
        raise TypeError('viewer title must be a string')
    options.setdefault('text', 'outline')
    options.setdefault('precision', 6)
    options.setdefault('background', 'white')
    batches = []
    buffers = []
    buffer_ids = {}
    native = []

    def marker_layer(prim, style, writer):
        reason = None
        geometry = _marker_geometry(prim.shape)
        if geometry is None:
            reason = 'marker shape requires native SVG'
        elif style.stroke not in (None, 'none') and style.stroke_width != 0:
            reason = 'marker outlines require native SVG'
        colors = []
        if reason is None:
            try:
                for value in prim.palette:
                    fill = (style.fill or '#000000') if value is None else value
                    colors.append([0,0,0,0] if fill=='none' else
                                  [*parse_color(fill), 1 if style.fill_opacity is None else style.fill_opacity])
            except (ValueError, TypeError):
                reason = 'paint requires native SVG'
        if reason is not None or not len(prim):
            native.append(dict(count=len(prim), reason=reason or 'empty layer'))
            return False
        box = prim.envelope().bbox().pad(1.)
        if not all(math.isfinite(v) for v in (box.x0,box.y0,box.width,box.height)):
            raise ValueError('browser marker extent must be finite')
        index = len(batches)
        key = id(prim.data)
        if key not in buffer_ids:
            buffer_ids[key] = len(buffers)
            buffers.append(base64.b64encode(prim.data).decode('ascii'))
        batches.append(dict(buffer=buffer_ids[key], count=len(prim),
                            palette=colors, fills=[style.fill if c is None else c for c in prim.palette],
                            **geometry, box=[box.x0,box.y0,box.width,box.height]))
        writer.empty('g', [('data-inklet-batch', str(index))])
        return True

    frame = _render_svg(scene, marker_handler=marker_layer, **options)
    payload = json.dumps(dict(schema='inklet.compiled-viewer/1', frame=frame,
                              batches=batches, buffers=buffers, native=native, backend=backend),
                         allow_nan=False, separators=(',', ':')).replace('<', '\\u003c')
    directory = Path(__file__).parent
    replacements = {'/*SCENE*/': payload, '/*RUNTIME*/': '\n'.join((directory/name).read_text() for name in ('spatial.js', 'runtime.js')),
                    '<!--TITLE-->': html.escape(title)}
    return re.sub(r'/\*SCENE\*/|/\*RUNTIME\*/|<!--TITLE-->',
                  lambda m: replacements[m.group()], (directory/'page.html').read_text())
