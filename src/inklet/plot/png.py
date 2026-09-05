"""A PNG writer, because a generated heatmap has no file to point at.

`Panel.matrix(raster=True)` needs an encoded image in memory. Pillow would do
it, but the base install is deliberately dependency-free and the image this
module has to write is the easy case of the format: no interlacing, no alpha,
one byte per sample, and -- for a matrix mapped through a ramp -- at most a
couple of hundred distinct colours. That is forty lines of `zlib` and `struct`,
and shipping them means a heatmap is not a reason to install anything.

Writing it here rather than reaching for Pillow when it happens to be present
also keeps the output *the same file* on every machine. An optional encoder is
an optional set of bytes, and "byte-identical SVG on repeat runs" would quietly
become "on repeat runs with the same extras installed".

Indexed colour when the picture has 256 colours or fewer, which every ramped
matrix does once its values are quantised, and truecolour otherwise. A 60x60
indexed image is about a kilobyte.
"""

from __future__ import annotations

import struct
import zlib
from typing import Sequence

__all__ = ["encode_png"]

_SIGNATURE = b"\x89PNG\r\n\x1a\n"

#: Deflate level. 9 on an image this small costs microseconds and the size
#: difference against the default is real: the index plane of a smooth ramp is
#: a long run of near-repeats, which is exactly what the slower search finds.
_LEVEL = 9

_COLOR_INDEXED = 3
_COLOR_RGB = 2


def encode_png(rows: Sequence[Sequence[tuple[int, int, int]]]) -> bytes:
    """A PNG of `rows` of `(r, g, b)` triples, top row first.

    Deterministic: the palette is ordered by first appearance scanning the
    image in reading order, so the same array encodes to the same bytes on
    every machine and in every run.
    """
    height = len(rows)
    if height == 0 or len(rows[0]) == 0:
        raise ValueError("cannot encode an empty image")
    width = len(rows[0])
    if any(len(row) != width for row in rows):
        raise ValueError("every row of a PNG must be the same length")

    palette = _palette(rows)
    if palette is None:
        return _write(width, height, _COLOR_RGB, None, _rgb_planes(rows))
    return _write(width, height, _COLOR_INDEXED, palette,
                  _index_planes(rows, palette))


def _palette(rows) -> list[tuple[int, int, int]] | None:
    """The distinct colours in reading order, or None past 256 of them."""
    seen: dict[tuple[int, int, int], None] = {}
    for row in rows:
        for pixel in row:
            seen[pixel] = None
            if len(seen) > 256:
                return None
    return list(seen)


def _index_planes(rows, palette: Sequence[tuple[int, int, int]]) -> bytes:
    """Scanlines of palette indices, each with a filter byte.

    Filter 0 (None) throughout: the other four predict a byte from its
    neighbours, which pays off for photographic bytes and costs on an index
    plane, where the difference between index 7 and index 8 is not a smaller
    number than 8 is.
    """
    index = {color: i for i, color in enumerate(palette)}
    out = bytearray()
    for row in rows:
        out.append(0)
        out.extend(index[pixel] for pixel in row)
    return bytes(out)


def _rgb_planes(rows) -> bytes:
    """Scanlines of RGB triples, filtered Up.

    A matrix that overflows the palette is a smooth field, where each row
    resembles the one above it far more than a byte resembles its left
    neighbour. Filter 2 subtracts that row, which is the cheapest predictor
    that actually helps here.
    """
    out = bytearray()
    previous = bytes(len(rows[0]) * 3)
    for row in rows:
        raw = bytearray()
        for r, g, b in row:
            raw.extend((r & 0xFF, g & 0xFF, b & 0xFF))
        out.append(2)
        out.extend((value - prior) & 0xFF for value, prior in zip(raw, previous))
        previous = bytes(raw)
    return bytes(out)


def _write(width: int, height: int, color_type: int,
           palette: Sequence[tuple[int, int, int]] | None,
           scanlines: bytes) -> bytes:
    header = struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0)
    parts = [_SIGNATURE, _chunk(b"IHDR", header)]
    if palette is not None:
        table = bytearray()
        for r, g, b in palette:
            table.extend((r & 0xFF, g & 0xFF, b & 0xFF))
        parts.append(_chunk(b"PLTE", bytes(table)))
    parts.append(_chunk(b"IDAT", zlib.compress(scanlines, _LEVEL)))
    parts.append(_chunk(b"IEND", b""))
    return b"".join(parts)


def _chunk(tag: bytes, payload: bytes) -> bytes:
    body = tag + payload
    return struct.pack(">I", len(payload)) + body + struct.pack(
        ">I", zlib.crc32(body) & 0xFFFFFFFF)
