"""Build dense vector scatter without allocating drawing objects per point."""
from ..core import Diagram, MarkerBatchPrim, ORIGIN, mm
from ..core.batch import RECORD
from ..draw.coords import drawn_group
from ..draw.shapes import marker as make_marker


def scatter_batch(panel, data, sizes, fills, marker, style):
    prototype = make_marker(marker, 1.)
    # The nominal default diameter is independent of the glyph's equal-area
    # footprint; recover it from the circle's diameter.
    default_size = make_marker('circle').prim.rx * 2
    palette = []
    indices = {}
    records = bytearray()
    for source, (point, size, fill) in enumerate(zip(data, sizes, fills)):
        diameter = default_size if size is None else mm(size)
        if fill not in indices:
            indices[fill] = len(palette)
            palette.append(fill)
        at = panel.point(*point)
        records.extend(RECORD.pack(at.x, at.y, diameter, indices[fill], source))
    prim = MarkerBatchPrim(prototype.prim, bytes(records), tuple(palette))
    node = Diagram(prim=prim, kind=prototype.kind)
    node.anchor('origin', ORIGIN)
    kind = style.pop('kind', 'place')
    return drawn_group((node,), kind, style)
