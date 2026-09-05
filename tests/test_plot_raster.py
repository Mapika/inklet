"""inklet.plot: a matrix drawn as pixels instead of as rectangles."""

from __future__ import annotations

import math
import struct
import zlib

import pytest

from inklet.core import DiagramError, ImagePrim, resolve
from inklet.draw.coords import as_drawn
from inklet.plot import panel, ramp
from inklet.plot.panel import _RASTER_ABOVE_CELLS
from inklet.plot.png import encode_png
from inklet.plot.raster import LEVELS, MATRIX_KIND, uniform_pitch
from inklet.plot.scale import Linear
from inklet.render.svg import RASTER_KIND

RAMP = ramp("tol-sunset")
UNIT = Linear((0.0, 1.0), (0.0, 1.0))


def field(rows: int, cols: int) -> list[list[float]]:
    return [[(math.sin(i / 3.0) * math.cos(j / 5.0) + 1) / 2
             for j in range(cols)] for i in range(rows)]


def images(node) -> list[ImagePrim]:
    return [p.diagram.prim for p in resolve(as_drawn(node)).values()
            if isinstance(p.diagram.prim, ImagePrim)]


def read_png(data: bytes) -> tuple[int, int, list[list[tuple[int, int, int]]]]:
    """A minimal decoder, so the test does not trust the encoder's own words."""
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    pos, chunks = 8, {}
    idat = b""
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos:pos + 4])
        name = data[pos + 4:pos + 8].decode("ascii")
        body = data[pos + 8:pos + 8 + length]
        (crc,) = struct.unpack(">I", data[pos + 8 + length:pos + 12 + length])
        assert crc == zlib.crc32(data[pos + 4:pos + 8 + length]) & 0xFFFFFFFF
        if name == "IDAT":
            idat += body
        else:
            chunks[name] = body
        pos += 12 + length
    width, height, depth, kind = struct.unpack(">IIBB", chunks["IHDR"][:10])
    assert depth == 8
    raw = zlib.decompress(idat)
    stride = width if kind == 3 else width * 3
    rows, previous = [], bytes(stride)
    at = 0
    for _ in range(height):
        filt = raw[at]
        line = bytearray(raw[at + 1:at + 1 + stride])
        at += 1 + stride
        if filt == 2:
            for i, up in enumerate(previous):
                line[i] = (line[i] + up) & 0xFF
        else:
            assert filt == 0, f"unexpected filter {filt}"
        previous = bytes(line)
        if kind == 3:
            table = chunks["PLTE"]
            rows.append([tuple(table[3 * v:3 * v + 3]) for v in line])
        else:
            rows.append([tuple(line[3 * i:3 * i + 3]) for i in range(width)])
    return width, height, rows


# --- the encoder -------------------------------------------------------------


def test_a_png_round_trips_through_a_reader_that_is_not_ours() -> None:
    pixels = [[(255, 0, 0), (0, 255, 0)], [(0, 0, 255), (8, 8, 8)]]
    width, height, back = read_png(encode_png(pixels))
    assert (width, height) == (2, 2)
    assert back == pixels


def test_few_colours_are_stored_as_a_palette() -> None:
    pixels = [[(1, 2, 3)] * 8 for _ in range(8)]
    data = encode_png(pixels)
    assert b"PLTE" in data
    assert read_png(data)[2] == pixels


def test_many_colours_fall_back_to_truecolour() -> None:
    pixels = [[(i, j, (i * j) % 256) for j in range(20)] for i in range(20)]
    data = encode_png(pixels)
    assert b"PLTE" not in data
    assert read_png(data)[2] == pixels


def test_the_same_pixels_encode_to_the_same_bytes() -> None:
    pixels = [[(i, j, 0) for j in range(6)] for i in range(6)]
    assert encode_png(pixels) == encode_png(pixels)


# --- choosing a path ---------------------------------------------------------


def test_a_small_matrix_stays_vector() -> None:
    p = panel(30, 30, x=(0, 3), y=(0, 3))
    p.matrix(field(4, 4), ramp=RAMP, scale=UNIT)
    assert images(p.build()) == []


def test_a_large_matrix_rasterises_itself() -> None:
    side = int(_RASTER_ABOVE_CELLS ** 0.5) + 4
    p = panel(40, 40, x=(0, side - 1), y=(0, side - 1))
    p.matrix(field(side, side), ramp=RAMP, scale=UNIT)
    assert len(images(p.build())) == 1


def test_raster_can_be_asked_for_and_refused() -> None:
    p = panel(30, 30, x=(0, 3), y=(0, 3))
    p.matrix(field(4, 4), ramp=RAMP, scale=UNIT, raster=True)
    assert len(images(p.build())) == 1
    q = panel(30, 30, x=(0, 3), y=(0, 3))
    q.matrix(field(4, 4), ramp=RAMP, scale=UNIT, raster=False)
    assert images(q.build()) == []


def test_uneven_cells_cannot_be_pixels() -> None:
    p = panel(30, 30, x=(0, 10), y=(0, 3))
    with pytest.raises(DiagramError, match="evenly spaced"):
        p.matrix(field(3, 3), ramp=RAMP, scale=UNIT, raster=True,
                 x=[0, 1, 10], y=[0, 1, 2])


def test_uneven_cells_stay_vector_on_their_own() -> None:
    p = panel(30, 30, x=(0, 10), y=(0, 3))
    p.matrix(field(3, 3), ramp=RAMP, scale=UNIT, x=[0, 1, 10], y=[0, 1, 2])
    assert images(p.build()) == []


def test_uniform_pitch_reports_the_gap_or_nothing() -> None:
    assert uniform_pitch([1.0, 3.0, 5.0]) == pytest.approx(2.0)
    assert uniform_pitch([1.0, 3.0, 9.0]) is None


# --- the picture -------------------------------------------------------------


def test_the_image_covers_exactly_the_plot_area() -> None:
    """The cells divide the area edge to edge, so the picture of them does."""
    side = 60
    p = panel(40, 30, x=(0, side - 1), y=(0, side - 1))
    p.matrix(field(side, side), ramp=RAMP, scale=UNIT, raster=True)
    (prim,) = images(p.build())
    assert prim.width == pytest.approx(40.0)
    assert prim.height == pytest.approx(30.0)
    assert p.build().bbox.width == pytest.approx(p.area.width)


def test_one_pixel_per_cell_and_no_resampling() -> None:
    rows, cols = 12, 20
    p = panel(40, 30, x=(0, cols - 1), y=(0, rows - 1))
    p.matrix(field(rows, cols), ramp=RAMP, scale=UNIT, raster=True)
    (prim,) = images(p.build())
    width, height, _ = read_png(prim.data)
    assert (width, height) == (cols, rows)


def rgb(color: str) -> tuple[int, int, int]:
    return tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))


def same(pixel, color: str) -> bool:
    """Equal up to one count in 255: the raster quantises the ramp to LEVELS
    steps, which is finer than the bar that explains it and far finer than
    anything a reader can see."""
    return all(abs(a - b) <= 1 for a, b in zip(pixel, rgb(color)))


def fills(node) -> list[tuple[float, float, str]]:
    """Every vector cell as (x, y, fill), so a raster can be checked against
    the rectangles it replaced rather than against a rule restated here."""
    out = []
    for placed in resolve(as_drawn(node)).values():
        color = placed.style.fill
        if placed.diagram.kind == "mark" and color:
            centre = placed.bbox.center
            out.append((centre.x, centre.y, color))
    return out


def test_the_pixels_land_where_the_rectangles_did() -> None:
    """Row and column order, top to bottom, checked against the vector path
    rather than against a convention written out twice."""
    grid = [[0.0, 0.25], [0.75, 1.0]]
    hot = panel(30, 30, x=(0, 1), y=(0, 1))
    hot.matrix(grid, ramp=RAMP, scale=UNIT, raster=True)
    cold = panel(30, 30, x=(0, 1), y=(0, 1))
    cold.matrix(grid, ramp=RAMP, scale=UNIT, raster=False)

    (prim,) = images(hot.build())
    width, height, pixels = read_png(prim.data)
    for x, y, color in fills(cold.build()):
        col = int((x + prim.width / 2) / prim.width * width)
        row = int((y + prim.height / 2) / prim.height * height)
        assert same(pixels[row][col], color)


def test_an_explicit_y_that_runs_the_other_way_still_lands_right() -> None:
    grid = [[0.0, 0.25], [0.75, 1.0]]
    hot = panel(30, 30, x=(0, 1), y=(0, 1))
    hot.matrix(grid, ramp=RAMP, scale=UNIT, raster=True, x=[0, 1], y=[0, 1])
    cold = panel(30, 30, x=(0, 1), y=(0, 1))
    cold.matrix(grid, ramp=RAMP, scale=UNIT, raster=False, x=[0, 1], y=[0, 1])

    (prim,) = images(hot.build())
    width, height, pixels = read_png(prim.data)
    box = hot.build().bbox
    for x, y, color in fills(cold.build()):
        col = min(width - 1, int((x - box.x0) / box.width * width))
        row = min(height - 1, int((y - box.y0) / box.height * height))
        assert same(pixels[row][col], color)


def test_the_renderer_is_told_not_to_smooth_it() -> None:
    """The kind is the contract with the back ends, so it is worth pinning."""
    assert MATRIX_KIND == RASTER_KIND
    p = panel(30, 30, x=(0, 1), y=(0, 1))
    p.matrix([[0.0, 1.0], [1.0, 0.0]], ramp=RAMP, scale=UNIT, raster=True)
    kinds = [n.diagram.kind for n in resolve(as_drawn(p.build())).values()]
    assert MATRIX_KIND in kinds


def test_the_colours_are_the_ramp_at_the_declared_scale() -> None:
    scale = Linear((0.0, 10.0), (0.0, 1.0))
    p = panel(30, 30, x=(0, 1), y=(0, 1))
    p.matrix([[0.0, 10.0], [5.0, 0.0]], ramp=RAMP, scale=scale, raster=True)
    (prim,) = images(p.build())
    _, _, pixels = read_png(prim.data)
    assert pixels[0][0] == rgb(RAMP(0.0))
    assert pixels[0][1] == rgb(RAMP(1.0))
    # A mid value lands on the nearest of LEVELS steps, so it may differ from
    # the exact ramp by one count of 255 -- far below anything visible.
    assert all(abs(a - b) <= 1
               for a, b in zip(pixels[1][0], rgb(RAMP(0.5))))


def test_a_nan_cell_is_a_finding_not_a_colour() -> None:
    p = panel(30, 30, x=(0, 1), y=(0, 1))
    with pytest.raises(DiagramError, match="NaN"):
        p.matrix([[0.0, float("nan")], [1.0, 0.0]], ramp=RAMP, scale=UNIT,
                 raster=True)


def test_a_sixty_square_matrix_is_a_few_kilobytes() -> None:
    """The whole reason the path exists. The vector form of the same data is
    two orders of magnitude larger."""
    p = panel(40, 40, x=(0, 59), y=(0, 59))
    p.matrix(field(60, 60), ramp=RAMP, scale=UNIT, raster=True)
    (prim,) = images(p.build())
    assert len(prim.data) < 8_000


def test_quantisation_is_finer_than_the_bar_that_explains_it() -> None:
    from inklet.plot.key import BANDS

    assert LEVELS >= 2 * BANDS


# --- cells with no measurement -----------------------------------------------


def test_a_missing_cell_needs_a_colour_of_its_own() -> None:
    """A hole painted in the ramp's low colour is a lie about the experiment."""
    import inklet
    from inklet.core import DiagramError

    p = inklet.panel(30, 20, x=(0, 3), y=(0, 3))
    with pytest.raises(DiagramError, match="missing="):
        p.matrix([[None, 1.0], [0.5, 0.2]], ramp=inklet.ramp("tol-sunset"),
                 scale=inklet.linear((0.0, 1.0)))


def test_a_vector_matrix_paints_holes_in_the_missing_colour() -> None:
    import inklet
    from inklet.core import resolve
    from inklet.draw.coords import as_drawn

    p = inklet.panel(30, 20, x=(0, 3), y=(0, 3))
    p.matrix([[None, 1.0], [0.5, 0.2]], ramp=inklet.ramp("tol-sunset"),
             scale=inklet.linear((0.0, 1.0)), missing="#dedede")
    fills = [placed.diagram.style.fill
             for placed in resolve(as_drawn(p.build())).values()
             if getattr(placed.diagram.style, "fill", None) is not None]
    assert "#dedede" in fills


def test_a_raster_matrix_keeps_holes_out_of_its_ramp_colours() -> None:
    """`KEY_MISMATCH` compares ramp colours; a hole is not one of them."""
    import inklet

    rows = [[None if (r + c) % 7 == 0 else (r + c) / 8.0 for c in range(8)]
            for r in range(8)]
    p = inklet.panel(30, 20, x=(0, 3), y=(0, 3))
    p.matrix(rows, ramp=inklet.ramp("tol-sunset"), scale=inklet.linear((0.0, 2.0)),
             missing="#dedede", raster=True)
    node = p.build()
    painted = [n.notes["ramp_colours"] for n in _all(node)
               if getattr(n, "notes", {}).get("ramp_colours")]
    assert painted and "#dedede" not in painted[0]


def _all(node):
    yield node
    for child in getattr(node, "children", ()) or ():
        yield from _all(child)


def test_one_position_more_than_cells_is_read_as_edges() -> None:
    """53 week boundaries for 52 weeks: the field fits the area, not area+1."""
    import inklet
    from inklet.draw.coords import as_drawn

    weeks = 52
    rows = [[float(c) for c in range(weeks)] for _ in range(4)]
    edges = [w / weeks for w in range(weeks + 1)]
    p = inklet.panel(58, 20, x=(0.0, 1.0), y=(0, 4))
    p.matrix(rows, ramp=inklet.ramp("tol-sunset"), scale=inklet.linear((0.0, 51.0)),
             x=edges, y=[r / 4 * 4 for r in range(5)], raster=True)
    box = as_drawn(p.build()).bbox
    assert box.width == pytest.approx(58.0, abs=0.01)
