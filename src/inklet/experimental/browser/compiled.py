"""Adapt measured linked marks to the shared compiled-viewer executor.

Identity and saved state remain owned by BrowserFigure. Contiguous circle runs
are packed without reordering paint; other marks retain their native SVG paint.
"""
import base64
from itertools import groupby
from xml.etree import ElementTree as ET

from ...core.batch import RECORD
from ...themes.color import parse_color


def compiled_marks(payload):
    from . import _marks, _svg_mark

    ns = '{http://www.w3.org/2000/svg}'
    root = ET.Element(ns+'svg', viewBox=f"0 0 {payload['width']} {payload['height']}")
    defs = ET.SubElement(root, ns+'defs')
    batches, buffers, native_marks, native_layers = [], [], [], []
    source_rows = {key: n for n, key in enumerate(payload['row_ids'])}
    for n, layer in enumerate(payload['layers']):
        clip_id = f'linked-compiled-clip-{n}'
        clip = ET.SubElement(defs, ns+'clipPath', id=clip_id)
        ET.SubElement(clip, ns+'rect', dict(zip(('x', 'y', 'width', 'height'), map(str, layer['clip']))))
        group = ET.SubElement(root, ns+'g', {'clip-path': f'url(#{clip_id})'})
        for circles, run in groupby(_marks(layer), lambda m: m['kind'] == 'circle'):
            marks = list(run)
            if not circles:
                for mark in marks:
                    tag, attrs = _svg_mark(mark, layer['color'])
                    attrs['data-inklet-linked'] = str(len(native_marks))
                    native_marks.append(mark['ids'])
                    native_layers.append(layer.get('name'))
                    ET.SubElement(group, ns+tag, attrs)
                continue
            palette, fills, records, identities = [], [], [], []
            palette_indices = {}
            bounds = [float('inf'), float('inf'), -float('inf'), -float('inf')]
            for mark in marks:
                x, y, radius = mark['geometry']
                color = mark.get('color', layer['color'])
                paint = [*parse_color(color), mark.get('opacity', .65)]
                key = tuple(paint)
                if key not in palette_indices:
                    palette_indices[key] = len(palette)
                    palette.append(paint)
                    fills.append(color)
                records.append(RECORD.pack(x, y, radius, palette_indices[key], source_rows[mark['ids'][0]]))
                identities.append(mark['ids'])
                bounds = [min(bounds[0], x-radius), min(bounds[1], y-radius),
                          max(bounds[2], x+radius), max(bounds[3], y+radius)]
            index = len(batches)
            ET.SubElement(group, ns+'g', {'data-inklet-batch': str(index)})
            buffers.append(base64.b64encode(b''.join(records)).decode('ascii'))
            batches.append(dict(buffer=index, count=len(marks), palette=palette, fills=fills,
                                radius=1, vertices=[], fill_rule='nonzero', bounds=[-1, -1, 1, 1],
                                box=[bounds[0]-1, bounds[1]-1, bounds[2]-bounds[0]+2, bounds[3]-bounds[1]+2],
                                row_ids=identities))
            batches[-1]['layer'] = layer.get('name')
    ET.register_namespace('', 'http://www.w3.org/2000/svg')
    return dict(schema='inklet.compiled-viewer/1', frame=ET.tostring(root, encoding='unicode'),
                batches=batches, buffers=buffers, native=[], native_marks=native_marks,
                native_layers=native_layers, backend='svg')
