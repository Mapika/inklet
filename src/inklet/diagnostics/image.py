"""What colour is the photograph under this caption?

Every other backdrop in the linter is a colour someone wrote down. A raster is
not: paper-white type over a dark micrograph -- the universal journal style --
has no `fill` anywhere for `LOW_CONTRAST` to read, so the rule judged it against
the page and reported the one annotation the figure was certain to get right.

The honest answer needs the pixels, which means Pillow, which is an optional
dependency. So this module has exactly two behaviours and no third:

* Pillow importable -- open the source once, shrink it to a thumbnail, average
  the pixels the text actually covers, and hand back that colour.
* Pillow absent -- return `None`, and the rule says nothing. A guess about a
  photograph nobody can open is worth less than silence.

Which of the two happened is visible from outside via `available()`, because a
diagnostic list that quietly depends on what is installed would otherwise be
impossible to explain.

Everything is cached on the source path, keyed by the file's size and mtime, so
a page with forty captions over one micrograph reads the file once.
"""

from __future__ import annotations

import os
from typing import Any

from ..core import Affine, ImagePrim, Rect

__all__ = ["available", "average_colour", "clear_cache"]

#: Longest side of the thumbnail every average is taken from. A caption sits on
#: a region measured in millimetres, and its mean colour is stable long before
#: the pixels are: 256 keeps a 4000px micrograph's dark field dark and its
#: bright grain bright, and costs one decode instead of forty.
_THUMBNAIL = 256

#: Fewer thumbnail pixels than this under the text and the average is noise
#: rather than a measurement, so the rule is told nothing instead.
_MIN_SAMPLES = 4

#: {(path, size, mtime): thumbnail}, and the same key for the failures, so an
#: unreadable file is opened once and not once per caption.
_THUMBS: dict[tuple[str, int, int], Any] = {}
#: {(thumbnail key, integer pixel box): "#rrggbb"}
_MEANS: dict[tuple[tuple[str, int, int], tuple[int, int, int, int]], str] = {}


def available() -> bool:
    """Whether the pixels can be read at all -- i.e. whether Pillow imports."""
    return _pillow() is not None


def clear_cache() -> None:
    """Forget every decoded thumbnail. For tests that rewrite a source file."""
    _THUMBS.clear()
    _MEANS.clear()


def _pillow():
    try:
        from PIL import Image  # noqa: PLC0415 -- optional, imported on demand
    except Exception:          # ImportError, or a broken install
        return None
    return Image


def average_colour(prim: ImagePrim, world: Affine, box: Rect) -> str | None:
    """Mean colour of the raster under a world-space box, as `#rrggbb`.

    `None` whenever the answer would be invented: no Pillow, no readable file,
    no pixel grid recorded, or a box that covers too little of the image to
    average. The caller treats all of those the same way -- it stops checking.
    """
    source = _key(prim.source)
    image = None if source is None else _thumbnail(source)
    if image is None or prim.width <= 0 or prim.height <= 0:
        return None
    crop = _pixel_box(prim, world, box, image.size)
    if crop is None:
        return None
    cached = _MEANS.get((source, crop))
    if cached is not None:
        return cached
    mean = _mean_of(image, crop)
    if mean is not None:
        _MEANS[(source, crop)] = mean
    return mean


def _mean_of(image, crop: tuple[int, int, int, int]) -> str | None:
    """One BOX-filtered pixel is the arithmetic mean of the region, computed by
    Pillow in C rather than by a Python loop over a crop."""
    Image = _pillow()
    if Image is None:
        return None
    try:
        patch = image.crop(crop).resize((1, 1), Image.Resampling.BOX)
        r, g, b = patch.getpixel((0, 0))[:3]
    except Exception:
        return None
    return f"#{r:02x}{g:02x}{b:02x}"


def _pixel_box(prim: ImagePrim, world: Affine, box: Rect,
               size: tuple[int, int]) -> tuple[int, int, int, int] | None:
    """The text's world box in thumbnail pixel coordinates, clamped to it.

    `ImagePrim` is centred on its local origin with y growing downward, which
    is also how a raster is indexed, so the mapping is a scale and a shift with
    no flip anywhere. The box's four corners are mapped rather than its extent,
    because a rotated caption's axis-aligned box is not axis-aligned in the
    image's frame.
    """
    try:
        inverse = world.inverse()
    except Exception:
        return None            # a degenerate transform: nothing to sample
    local = [inverse.apply(corner) for corner in box.corners]
    width, height = size
    xs = [(p.x + prim.width / 2) / prim.width * width for p in local]
    ys = [(p.y + prim.height / 2) / prim.height * height for p in local]
    left = max(0, int(min(xs)))
    top = max(0, int(min(ys)))
    right = min(width, int(max(xs)) + 1)
    bottom = min(height, int(max(ys)) + 1)
    if right - left < 1 or bottom - top < 1:
        return None
    if (right - left) * (bottom - top) < _MIN_SAMPLES:
        return None
    return (left, top, right, bottom)


def _key(source: str) -> tuple[str, int, int] | None:
    """Identity of a file as its contents, cheaply: path, size and mtime."""
    try:
        stat = os.stat(source)
    except OSError:
        return None
    return (source, stat.st_size, int(stat.st_mtime_ns))


def _thumbnail(key: tuple[str, int, int]):
    """The source shrunk to `_THUMBNAIL` on its long side, RGB, memoised.

    A failed open is memoised too: the alternative is a figure with one broken
    image path paying a filesystem error per caption on it.
    """
    if key in _THUMBS:
        return _THUMBS[key]
    Image = _pillow()
    thumb = None
    if Image is not None:
        try:
            with Image.open(key[0]) as handle:
                handle.draft("RGB", (_THUMBNAIL, _THUMBNAIL))  # JPEG shortcut
                copy = handle.convert("RGB")
            copy.thumbnail((_THUMBNAIL, _THUMBNAIL), Image.Resampling.BOX)
            thumb = copy
        except Exception:
            thumb = None       # not an image, not readable, truncated: say so once
    _THUMBS[key] = thumb
    return thumb
