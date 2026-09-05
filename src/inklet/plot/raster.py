"""The other way to draw a matrix: one pixel per cell instead of one node.

A heatmap is the one plot whose vector form does not scale. Every other mark
here costs a node per *datum a reader can point at*; a matrix costs a node per
cell, and a 60 x 60 field is 3,600 rectangles and roughly a megabyte of SVG for
a picture 40mm wide, where each cell is two thirds of a millimetre and nobody
is pointing at anything.

So above a size threshold the cells are encoded as a PNG exactly as big as the
grid -- one pixel per cell, no resampling -- and placed as a single image the
width of the plot area. The edges then land exactly where the vector cells did,
because the image is scaled by an integer-free affine onto the same rectangle
and the renderer is asked for nearest-neighbour sampling. The same 60 x 60
matrix is about a kilobyte.

Two things are given up and both are stated in `Panel.matrix`'s docstring: the
cells stop being individually selectable in an editor, and `KEY_MISMATCH` can
no longer compare the *colours* against a colorbar, because there are no longer
any mark fills to sample. The declared domain still crosses over, so the half
of that rule which catches two domains over one ramp keeps working.

The node carries two things a reader of the tree would otherwise have lost
with the rectangles: `ramp`, the ramp object itself, and `ramp_colours`, the
distinct colours the matrix actually painted, low value first. `scale_domain`
comes from `Panel.matrix` as it does for the vector path. Together they are
what the vector cells' fills were -- enough for `KEY_MISMATCH` to compare a
rasterised matrix against the colorbar standing beside it.

Colour is quantised to `LEVELS` steps of the ramp before encoding, which is
what keeps the palette inside PNG's 256 entries. At 256 levels the step is
finer than the 128 bands the colorbar beside it is drawn in, so the quantisation
cannot make the picture and its key disagree by anything visible.
"""

from __future__ import annotations

from typing import Sequence

from ..core import Affine, Diagram, DiagramError, ImagePrim, Vec2
from ..themes.color import parse_color
from .png import encode_png
from .scale import _annotate

__all__ = ["LEVELS", "MATRIX_KIND", "raster_matrix", "uniform_pitch"]

#: The kind the SVG and PDF back ends look for to turn off smoothing. Agreed
#: with `inklet.render.svg.RASTER_KIND`: a raster whose pixels *are* the data must
#: not be resampled bilinearly, because a filter that invents intermediate
#: colours on a ramped matrix is inventing intermediate values.
MATRIX_KIND = "raster-matrix"

#: Quantisation steps through the ramp. Twice `plot.key.BANDS`, so the image is
#: finer than the bar that explains it, and inside PNG's palette limit.
LEVELS = 256

_EVEN = 1e-9


def uniform_pitch(centres: Sequence[float]) -> float | None:
    """The common spacing of a set of cell centres, or None if they vary.

    The raster path needs one: a pixel is a fixed fraction of the image and
    cannot be wider than its neighbour. Unevenly sampled data stays vector,
    where each cell can own the interval it actually stands for.
    """
    if len(centres) < 2:
        return abs(centres[0]) * 2.0 if centres else None
    gaps = [b - a for a, b in zip(centres, centres[1:])]
    reach = max(abs(g) for g in gaps)
    if reach <= 0 or max(gaps) - min(gaps) > reach * 1e-9:
        return None
    return abs(gaps[0])


def raster_matrix(rows: Sequence[Sequence[float]], ramp, unit,
                  xs: Sequence[float], ys: Sequence[float],
                  missing: str | None = None) -> Diagram:
    """One `ImagePrim` covering the whole grid, one pixel per cell.

    `xs` and `ys` are the cell centres in panel millimetres and `unit` is the
    scale re-ranged to 0..1 -- the same two things the vector path works from,
    so the two draw the same picture. `missing` is the colour for cells with
    no measurement, and its pixel is a 257th colour: `encode_png` drops to
    truecolour past a palette, so a hole costs bytes but never a ramp step.
    """
    pitch_x, pitch_y = uniform_pitch(xs), uniform_pitch(ys)
    if pitch_x is None or pitch_y is None:
        raise DiagramError(
            "matrix(raster=True) needs evenly spaced cells: a pixel cannot be "
            "wider than its neighbour. Leave raster to its default, or to "
            "False, and the vector path will give each sample the interval it "
            "owns."
        )
    # Reading order down the page. Data may run either way -- a y scale maps
    # upward, so row 0 of the array is usually the *bottom* of the area -- and
    # a PNG's first scanline is its top one.
    grid = list(rows)
    if len(ys) > 1 and ys[1] < ys[0]:
        grid = grid[::-1]
        ys = list(ys)[::-1]
    if len(xs) > 1 and xs[1] < xs[0]:
        grid = [list(row)[::-1] for row in grid]
        xs = list(xs)[::-1]

    colours = tuple(ramp(level / (LEVELS - 1)) for level in range(LEVELS))
    stops = tuple(_rgb(c) for c in colours)
    levels = [[None if is_missing(value) else _level(value, unit)
               for value in row] for row in grid]
    hole = _rgb(_missing_colour(
        any(level is None for row in levels for level in row), missing))
    pixels = [[hole if level is None else stops[level] for level in row]
              for row in levels]

    width = pitch_x * len(xs)
    height = pitch_y * len(ys)
    centre = Vec2((xs[0] + xs[-1]) / 2.0, (ys[0] + ys[-1]) / 2.0)
    prim = ImagePrim(
        source="matrix", width=width, height=height,
        # No `pixel_size`: it is what `LOW_DPI` measures, and the question it
        # asks -- would this print sharply -- has no meaning for an image whose
        # pixels are the samples. A 60 x 60 experiment at 40mm is 38dpi and is
        # not under-resolved; it is 60 measurements.
        data=_png(pixels),
    )
    node = Diagram(prim=prim, kind=MATRIX_KIND,
                   transform=Affine.translation(centre.x, centre.y))
    # What the vector path leaves in the tree as cell fills, left here as two
    # notes instead, because a rule that compares a key against the picture
    # beside it has nothing else to read once the cells are pixels.
    _annotate(node, "ramp", ramp)
    _annotate(node, "ramp_colours", _painted(levels, colours))
    return node


def is_missing(value) -> bool:
    """Whether a cell holds no measurement: `None`, or a NaN.

    Both spellings arrive in real data -- `None` from a database or a hand
    written table, NaN from numpy -- and neither is a value the ramp can
    colour, so the matrix has to be told what to draw instead.
    """
    return value is None or (isinstance(value, float) and value != value)


def _missing_colour(any_hole: bool, missing: str | None) -> str:
    """The colour for a hole, or a refusal to invent one."""
    if missing is not None:
        return missing
    if any_hole:
        raise DiagramError(
            "matrix() was given a cell with no value (None or NaN) and no "
            "missing= colour to draw it in. Pass missing='#dedede' -- a tone "
            "that is not on the ramp -- so a hole reads as no measurement "
            "rather than as the low end of the scale."
        )
    return "#000000"                     # never reached by any pixel


def _painted(levels: Sequence[Sequence[int]],
             colours: Sequence[str]) -> tuple[str, ...]:
    """The distinct colours this matrix actually drew, low value first.

    The raster analogue of the vector path's cell fills: the same set, in the
    same order a colorbar's bands are read in, so `KEY_MISMATCH` can ask the
    same question of a rasterised matrix that it asks of a drawn one.
    """
    used = sorted({level for row in levels for level in row
                   if level is not None})
    return tuple(colours[level] for level in used)


def _level(value: float, unit) -> int:
    """Which of `LEVELS` steps of the ramp a value lands on.

    Clamped, exactly as a ramp clamps: a value past the end of the scale is
    drawn in the end colour by the vector path too, and the two must agree.
    """
    t = float(value) if unit is None else unit.map(value)
    if not t == t:                                   # NaN: no colour to give it
        raise DiagramError("matrix() cannot colour a NaN")
    return max(0, min(LEVELS - 1, int(t * (LEVELS - 1) + 0.5)))


def _rgb(color: str) -> tuple[int, int, int]:
    return parse_color(color)


def _png(pixels) -> bytes:
    if not pixels or not pixels[0]:
        raise DiagramError("matrix() needs at least one row and one column")
    return encode_png(pixels)
