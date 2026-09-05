"""Boolean-mask plumbing shared by the cutout and the silhouette tracer.

Three operations do all the work, and they are here rather than in NumPy
because NumPy has none of them and SciPy is not a dependency this library is
willing to take on for four hundred lines of code.

The flood fill is span-based: it advances a whole horizontal run at a time and
seeds only the *starts* of runs on the rows above and below, so the Python loop
runs once per span rather than once per pixel. On a 12-megapixel photograph
that is the difference between milliseconds and a minute.
"""

from __future__ import annotations

from typing import Any, Iterable

from .deps import numpy

__all__ = [
    "flood", "border_seeds", "fill_holes", "largest_component", "tight_bounds",
    "MAX_COMPONENTS",
]

# A noisy chroma key can shatter into tens of thousands of specks. Past this
# many we keep the largest found so far rather than scanning all of them; the
# scan order is raster order, so the cut-off is deterministic.
MAX_COMPONENTS = 4096


def flood(passable: Any, seeds: Iterable[tuple[int, int]]) -> Any:
    """4-connected fill of `passable` starting from `seeds`, as a boolean mask."""
    np = numpy()
    height, width = passable.shape
    filled = np.zeros((height, width), dtype=bool)
    stack = [(int(y), int(x)) for y, x in seeds]
    while stack:
        y, x = stack.pop()
        if filled[y, x] or not passable[y, x]:
            continue
        open_run = passable[y] & ~filled[y]
        blocked = np.flatnonzero(~open_run)
        before = blocked[blocked < x]
        after = blocked[blocked > x]
        x0 = int(before[-1]) + 1 if before.size else 0
        x1 = int(after[0]) - 1 if after.size else width - 1
        filled[y, x0:x1 + 1] = True
        for ny in (y - 1, y + 1):
            if not 0 <= ny < height:
                continue
            span = passable[ny, x0:x1 + 1] & ~filled[ny, x0:x1 + 1]
            index = np.flatnonzero(span)
            if index.size == 0:
                continue
            # Only the first pixel of each contiguous run needs a seed; the
            # rest of the run is swallowed when that seed is expanded.
            starts = index[np.r_[True, np.diff(index) > 1]]
            stack.extend((ny, x0 + int(start)) for start in starts)
    return filled


def border_seeds(height: int, width: int) -> list[tuple[int, int]]:
    """Every pixel on the frame, in raster order."""
    seeds = [(0, x) for x in range(width)]
    seeds += [(height - 1, x) for x in range(width)]
    seeds += [(y, 0) for y in range(1, height - 1)]
    seeds += [(y, width - 1) for y in range(1, height - 1)]
    return seeds


def fill_holes(mask: Any) -> Any:
    """Close interior holes by flooding the background inward from the frame.

    A mouse's eye keyed out as background is a hole in the mask, and a contour
    tracer would happily walk into it. Anything the background cannot reach
    from outside is part of the subject by definition.
    """
    outside = flood(~mask, border_seeds(*mask.shape))
    return ~outside


def largest_component(mask: Any) -> Any | None:
    """The biggest connected blob, or None if the mask is empty.

    Dust, JPEG ringing and a stray caption all survive a chroma key as small
    islands. The subject is the large one; keeping only it is what stops a
    speck in the corner from defining the asset's bounding box.
    """
    np = numpy()
    remaining = mask.copy()
    left = int(remaining.sum())
    best: Any | None = None
    best_size = 0
    width = mask.shape[1]
    for _ in range(MAX_COMPONENTS):
        if left <= best_size:
            break  # nothing unvisited could beat what we already have
        flat = remaining.reshape(-1)
        first = int(flat.argmax())
        if not bool(flat[first]):
            break
        component = flood(remaining, [divmod(first, width)])
        size = int(component.sum())
        if size > best_size:
            best, best_size = component, size
        remaining &= ~component
        left -= size
    return best


def tight_bounds(mask: Any) -> tuple[int, int, int, int] | None:
    """Inclusive (y0, x0, y1, x1) of the True pixels, or None when there are none."""
    np = numpy()
    rows = np.flatnonzero(mask.any(axis=1))
    if rows.size == 0:
        return None
    cols = np.flatnonzero(mask.any(axis=0))
    return (int(rows[0]), int(cols[0]), int(rows[-1]), int(cols[-1]))
