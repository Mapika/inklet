"""Offline execution of a native compiled scene with bounded GPU circle layers."""
import base64
import html
import json
import math
from pathlib import Path
import re

from ...core import EllipsePrim
from ...themes.color import parse_color
from ...render.svg import _render_svg


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
        if not isinstance(prim.shape, EllipsePrim) or prim.shape.rx != prim.shape.ry:
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
                            radius=prim.shape.rx, box=[box.x0,box.y0,box.width,box.height]))
        writer.empty('g', [('data-inklet-batch', str(index))])
        return True

    frame = _render_svg(scene, marker_handler=marker_layer, **options)
    payload = json.dumps(dict(schema='inklet.compiled-viewer/1', frame=frame,
                              batches=batches, buffers=buffers, native=native, backend=backend),
                         allow_nan=False, separators=(',', ':')).replace('<', '\\u003c')
    directory = Path(__file__).parent
    replacements = {'/*SCENE*/': payload, '/*RUNTIME*/': (directory/'runtime.js').read_text(),
                    '<!--TITLE-->': html.escape(title)}
    return re.sub(r'/\*SCENE\*/|/\*RUNTIME\*/|<!--TITLE-->',
                  lambda m: replacements[m.group()], (directory/'page.html').read_text())
