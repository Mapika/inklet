"""Matrix input validation, physical sample geometry, and render-mode selection.

This module builds a drawing without owning a Panel. The caller owns clipping,
its remembered colour scale, and the assembled plot's invalidation.
"""
from __future__ import annotations

from typing import Sequence

from ..core import Diagram, DiagramError, Rect, RectPrim, Vec2
from ..draw.coords import as_drawn
from ..draw.place import place as draw_place
from ..draw.shapes import MARK_KIND
from .raster import _missing_colour, is_missing, raster_matrix, uniform_pitch
from .metadata import declare_domain as _declare_domain
from .scale import Scale
from .._compat import renamed_function


#: How far each matrix cell is grown past its own pitch, as a fraction of it.
#: Enough to bury the antialiased seam under its neighbour, small enough that a
#: cell still reads as square.
_CELL_OVERLAP = 0.06

#: Where `matrix(raster="auto")` stops drawing rectangles. About a 45 x 45
#: field: a vector matrix costs roughly 280 bytes and one DOM node per cell, so
#: this is where the picture passes half a megabyte -- and where, at a column
#: width, a cell is under half a millimetre and has stopped being a thing a
#: reader points at. Below it the vector form is worth its size: the cells stay
#: individually selectable, and `KEY_MISMATCH` can compare their colours
#: against the bar beside them.
_RASTER_ABOVE_CELLS = 2048


def _cell_spans(centres: Sequence[float],
                overlap: float, singleton: float) -> list[tuple[float, float]]:
    """Each cell's centre and its size, in millimetres.

    Evenly spaced samples take the pitch, which is the whole of the old
    behaviour and is kept as its own branch so that a uniform matrix renders
    byte-identically to before rather than to within a float.

    Unevenly spaced ones cannot: a cell there belongs to the interval its
    sample *owns*, which runs to the midpoint of the gap on each side, so a
    long gap draws a wide cell and the sample is not at its centre. Extending
    by half the neighbouring gap at the two ends is the only choice that keeps
    the first and last samples inside the cells that stand for them.
    """
    if len(centres) < 2:
        size = singleton * (1.0 + overlap)
        return [(c, size) for c in centres]
    gaps = [b - a for a, b in zip(centres, centres[1:])]
    reach = max(abs(g) for g in gaps)
    if max(gaps) - min(gaps) <= reach * 1e-9:
        size = abs(gaps[0]) * (1.0 + overlap)
        return [(c, size) for c in centres]
    edges = ([centres[0] - gaps[0] / 2]
             + [(a + b) / 2 for a, b in zip(centres, centres[1:])]
             + [centres[-1] + gaps[-1] / 2])
    return [((lo + hi) / 2, abs(hi - lo) * (1.0 + overlap))
            for lo, hi in zip(edges, edges[1:])]


def _rasterises(raster: bool | str, cells: int, xs: Sequence[float],
                ys: Sequence[float]) -> bool:
    """Whether this matrix is drawn as an image rather than as rectangles.

    `"auto"` also asks whether the samples are evenly spaced, because unevenly
    spaced ones cannot be pixels and the vector path draws them honestly. An
    explicit `raster=True` does not check: it raises in `raster_matrix`, which
    is the right answer to being told to do something that cannot be done.
    """
    if raster is True or raster is False:
        return bool(raster)
    if raster != "auto":
        raise DiagramError(
            f'matrix(raster=) is True, False or "auto", not {raster!r}')
    if cells <= _RASTER_ABOVE_CELLS:
        return False
    return uniform_pitch(xs) is not None and uniform_pitch(ys) is not None


def _cell_grid(rows: Sequence[Sequence[float]], ramp, unit,
               xs: Sequence[tuple[float, float]],
               ys: Sequence[tuple[float, float]], style: dict,
               missing: str | None = None) -> Diagram:
    """The vector matrix: one styled rectangle per cell.

    Cells carry `kind="mark"`, because a cell's position is the data -- without
    it a heatmap is thousands of CROWDING findings about its own neighbours.
    """
    cells = []
    hole = _missing_colour(
        any(is_missing(value) for row in rows for value in row), missing)
    for row, (cy, tall) in zip(rows, ys):
        for value, (cx, wide) in zip(row, xs):
            if is_missing(value):
                shade = hole
            else:
                shade = ramp(value if unit is None else unit.map(value))
            cells.append((Vec2(cx, cy),
                          Diagram(prim=RectPrim(wide, tall), kind=MARK_KIND)
                          .styled(fill=shade, stroke="none")))
    return draw_place(cells, **style)


def _batched_cell_grid(rows,ramp,unit,xs,ys,style,missing=None,*,seamless=False):
    """Disjoint cell rectangles batched by exact fill, with no color quantization."""
    from ..core import PathPrim,Subpath
    hole=_missing_colour(any(is_missing(value) for row in rows for value in row),missing)
    buckets={};back={}
    if seamless:
        from ..themes.color import parse_color
        xmin=min(c-w/2 for c,w in xs);xmax=max(c+w/2 for c,w in xs)
        ymin=min(c-h/2 for c,h in ys);ymax=max(c+h/2 for c,h in ys)
    for row,(cy,tall) in zip(rows,ys):
        for value,(cx,wide) in zip(row,xs):
            fill=hole if is_missing(value) else ramp(value if unit is None else unit.map(value))
            box=Rect(cx-wide/2,cy-tall/2,cx+wide/2,cy+tall/2)
            buckets.setdefault(fill,[]).append(Subpath(box.corners,closed=True))
            if seamless:
                # Opaque underpaint fills only the subpixel cracks of the exact
                # foreground. Never change sample boundaries or the outer box.
                parse_color(fill)
                bleed=Rect(max(xmin,box.x0-wide/2),max(ymin,box.y0-tall/2),
                           min(xmax,box.x1+wide/2),min(ymax,box.y1+tall/2))
                back.setdefault(fill,[]).append(Subpath(bleed.corners,closed=True))
    nodes=[]
    for layer in ([back,buckets] if seamless else [buckets]):
        for color,paths in layer.items():
            for k in range(0,len(paths),512):
                nodes.append(Diagram(prim=PathPrim(tuple(paths[k:k+512]),filled=True),
                    kind='matrix-underpaint' if layer is back else MARK_KIND).styled(fill=color,stroke='none'))
    result=Diagram(children=tuple(nodes),kind='vector-matrix',notes={'matrix_batch':{'cells':sum(map(len,rows)),'colors':len(buckets),'batches':len(nodes),'individual_cells':False,'seamless':seamless}})
    return as_drawn(result.styled(**style) if style else result)


def matrix_centers(given: Sequence | None, count: int,
                   scale: Scale, extent: float) -> list[float]:
    """Where each row or column sits, in panel millimetres.

    Given values are data and go through the scale. Given nothing, the
    cells divide the area evenly and the scale is not consulted at all --
    which is what makes `matrix` line up with an axis built from the same
    `count` without the caller computing half a cell anywhere.

    One value more than there are cells means the caller gave the *edges*
    -- 53 week boundaries for 52 weeks -- which is how a histogram, a
    netCDF file and every gridded dataset states its axis. Read as centres
    they would hang the field half a cell off the panel and stretch it by
    one, so they are read as edges and the cells sit between them.
    """
    if given is not None:
        at = [scale.map(v) for v in given]
        if len(at) == count + 1:
            return [(a + b) / 2 for a, b in zip(at, at[1:])]
        return at
    step = extent / count
    return [-extent / 2 + step * (i + 0.5) for i in range(count)]


def prepare_matrix(values, *, vector, interpolation, raster, overlap, style):
    """Validate mode combinations and snapshot rows before mapping coordinates."""
    if interpolation not in ('nearest','linear'):
        raise ValueError('matrix interpolation must be nearest or linear')
    if interpolation=='linear' and (raster is not True or vector!='cells'):
        raise ValueError('linear interpolation requires raster=True and vector="cells"')
    if vector not in ('cells','batched','seamless'):raise ValueError('matrix vector must be cells, batched or seamless')
    if vector in ('batched','seamless'):
        if raster is True:raise ValueError('batched vector matrices cannot also request raster=True')
        raster=False
        if overlap not in (None,0):raise ValueError('batched matrices need overlap=0 to preserve cell boundaries')
    overlap=(0. if vector in ('batched','seamless') else _CELL_OVERLAP) if overlap is None else overlap
    if vector=='seamless' and any(style.get(k,1)!=1 for k in ('opacity','fill_opacity')):
        raise ValueError('seamless matrices require opaque paint; apply opacity to a containing group')
    clip = style.pop("clip", None)
    rows = [list(row) for row in values]
    if not rows or not rows[0]:
        raise DiagramError("matrix() needs at least one row and one column")
    if len({len(row) for row in rows}) != 1:
        raise DiagramError(
            f"matrix() needs rows of equal length, got "
            f"{sorted({len(row) for row in rows})}"
        )
    return rows, raster, overlap, clip


def default_coloring(rows, ramp, scale, center):
    """The ramp and colour scale a matrix uses when the caller leaves them out.

    Without `scale`, a given `center` or an omitted `ramp` means the scale is
    taken from the data: its extent, or the extent made symmetric about the
    centre when the ramp diverges. Without `ramp`, data on both sides of the
    centre (0 when no `center` is given) get the diverging ramp and everything
    else the sequential one. An explicit ramp with no scale keeps its old
    meaning: values are already fractions of the ramp.
    """
    from .ramp import as_ramp, default_ramp
    from .scale import linear
    ramp = as_ramp(ramp)  # a palette name such as "viridis" works too
    if center is not None and scale is not None:
        raise DiagramError('matrix() takes center= or scale=, not both: '
                           'a scale already fixes where its middle is')
    if center is not None:
        center = float(center)
        if center != center or center in (float('inf'), float('-inf')):
            raise DiagramError(f'matrix(center=) must be a finite number, not {center!r}')
    if scale is None and (ramp is None or center is not None):
        values = [float(v) for row in rows for v in row if not is_missing(v)]
        if not values:
            raise DiagramError('matrix() cannot choose a colour scale: every cell is missing')
        low, high = min(values), max(values)
        middle = center if center is not None else (0.0 if ramp is None and low < 0.0 < high else None)
        if middle is not None:
            reach = max(abs(low - middle), abs(high - middle)) or 1.0
            scale = linear((middle - reach, middle + reach))
        else:
            scale = linear((low, high if high > low else low + 1.0))
    if ramp is None:
        low, high = getattr(scale, 'domain', (0.0, 1.0))
        middle = 0.0 if center is None else center
        ramp = default_ramp(center is not None or min(low, high) < middle < max(low, high))
    return ramp, scale


#: Deprecated spellings, removed in 5.0.
matrix_centres = renamed_function("matrix_centres", matrix_centers, owner="inklet.plot.matrix")
default_colouring = renamed_function("default_colouring", default_coloring, owner="inklet.plot.matrix")


def matrix_layer(rows, ramp, unit, centres_x, centres_y, *,
                 single_x, single_y, scale, interpolation, samples,
                 raster, vector, overlap, missing, style) -> Diagram:
    """Render mapped samples and retain their sampling and colour-scale notes."""
    source_shape=(len(rows),len(rows[0]))
    if interpolation=='linear':
        from .raster import interpolate_matrix
        rows,centres_x,centres_y=interpolate_matrix(rows,centres_x,centres_y,samples,single_x=single_x,single_y=single_y)

    if _rasterises(raster, len(rows) * len(rows[0]), centres_x, centres_y):
        group = raster_matrix(rows, ramp, unit, centres_x, centres_y,
                              missing,single_x=single_x,single_y=single_y)
        if style:
            group = group.styled(**style)
    else:
        xs = _cell_spans(centres_x, overlap, single_x)
        ys = _cell_spans(centres_y, overlap, single_y)
        if vector == "cells":
            group = _cell_grid(rows, ramp, unit, xs, ys, style, missing)
        else:
            group = _batched_cell_grid(rows, ramp, unit, xs, ys, style, missing,
                                       seamless=vector == "seamless")
    _declare_domain(group, scale)
    group.note('matrix_sampling', {'source_shape':source_shape,
               'interpolation':interpolation, 'vector':vector,
               'samples':samples if interpolation=='linear' else 1})
    return group
