"""Flow layout: stacks, grids, padding and frames.

This module exists so that an author never types a coordinate. Two rules carry
the weight.

**Packing uses envelope extents, not bounding boxes.** `hstack` asks each item
for `extent(EAST)` and `extent(WEST)` -- the support function of its envelope --
and puts the next item's west extent exactly `gap` past its neighbour's east
one. For an axis-aligned query on a leaf, an envelope and a bounding box agree
by construction (a `Rect` here *is* four extent queries). They stop agreeing the
moment a child carries a rotation, because a bbox can only be rotated by hulling
its corners, which overstates: two 40x10 ellipses turned 45 degrees pack into
58.3mm by their envelopes and 70.7mm by hulled boxes. Oblique stack directions
diverge the same way -- two circles stacked along the diagonal reach
20 + 10*sqrt(2), not 40. Cross-axis alignment is free to use bounding boxes,
since those are derived from the same extents.

**Combinators wrap, never rewrite.** Every function returns a fresh parent whose
children are the caller's own objects, so a handle taken before layout still
resolves inside the result. Nothing here mutates its inputs.

One convention holds throughout: a laid-out diagram comes back with its bounding
box centred on its origin, exactly like a primitive, so it drops into the next
stack without an anchor-correction step. `align_to` is the escape hatch when you
want some other point at the origin.
"""

from __future__ import annotations

import math
from typing import Iterable, Sequence

from ..core import (
    EAST, IDENTITY, SOUTH,
    Affine, Diagram, DiagramError, EllipsePrim, PhantomPrim, Rect, RectPrim,
    TextPrim, Vec2, mm,
)
from ..draw.coords import ORIGIN_ANCHOR, needs_diagram, placed_anchor

__all__ = [
    "BOX_PAD", "align_to", "beside", "box", "flow", "frame", "grid", "hstack",
    "overlay", "pad", "placed_anchor", "spacer", "stack", "vstack",
]

Length = float | int | str

# Default padding for `box`, in mm. Geometry, not style: the theme is still the
# only thing allowed to have an opinion about ink.
BOX_PAD = 2.0

_AXIS_EPS = 1e-12

# Cross-axis vocabularies. "start"/"end" are the axis-neutral spellings and are
# accepted everywhere; the compass words are only accepted on the axis they
# describe, so `hstack(align="left")` is an error rather than a silent centre.
_Y_ALIGN = {"top": "start", "n": "start", "start": "start",
            "center": "center", "c": "center",
            "bottom": "end", "s": "end", "end": "end"}
_X_ALIGN = {"left": "start", "w": "start", "start": "start",
            "center": "center", "c": "center",
            "right": "end", "e": "end", "end": "end"}
# "origin" aligns the frame rather than the box. Everything `inklet.draw` builds
# is shifted onto its own origin and records where the author's (0, 0) went as
# an `origin` anchor; lining those up is what holds several absolute-coordinate
# groups in register. An item without the anchor was never shifted, so its own
# local origin is the point -- the same reading `as_drawn` takes.
_ORIGIN_ALIGN = {"origin": "origin"}
_H_STACK_ALIGN = _Y_ALIGN | {"baseline": "baseline"} | _ORIGIN_ALIGN
_V_STACK_ALIGN = _X_ALIGN | _ORIGIN_ALIGN
_FREE_ALIGN = {"start": "start", "center": "center", "c": "center",
               "end": "end", "baseline": "baseline"} | _ORIGIN_ALIGN


# -- shared helpers -------------------------------------------------------


def _prepare(items: Iterable[Diagram], what: str) -> list[Diagram]:
    """Materialise the input and refuse the three mistakes that would otherwise
    surface far from their cause: one diagram where a list was wanted, a
    non-diagram, and the same object twice."""
    if isinstance(items, Diagram):
        raise TypeError(
            f"{what} takes a list of diagrams, not one diagram; "
            f"write {what}([a, b])"
        )
    result = list(items)
    seen: set[int] = set()
    for i, item in enumerate(result):
        if not isinstance(item, Diagram):
            raise TypeError(
                f"{what} item {i} is a {type(item).__name__}, not a Diagram"
            )
        if id(item) in seen:
            raise DiagramError(
                f"{what} was handed the same Diagram object twice (item {i}); "
                "use .copy() to place the same shape more than once"
            )
        seen.add(id(item))
    return result


def _box_of(item: Diagram) -> Rect | None:
    """Bounding box in the parent's frame, or None for an empty diagram.

    `Diagram.bbox` raises for empty nodes, which is right for an author but
    wrong here: layout treats an empty item as something to skip."""
    return item.envelope.bbox()


def _union_box(items: Iterable[Diagram]) -> Rect | None:
    box = None
    for item in items:
        other = _box_of(item)
        if other is not None:
            box = other if box is None else box.union(other)
    return box


def _centered(children: list[Diagram], kind: str,
              notes_from: Diagram | None = None) -> Diagram:
    """Wrap placed children in one node, shifted so the result is centred on
    its own origin. One node, not two: the offset rides on the group's own
    transform rather than on another `.placed()` wrapper.

    A wrapper round *one* child inherits that child's notes, moved into the
    wrapper's frame (core M19) -- padding a panel must not lose the plot area
    a row is about to line it up on. `notes_from` names the content where the
    children are content plus furniture, as `frame` has them. Many children
    and no `notes_from` inherit nothing, for the reason `registered_point`
    refuses the same question: a stack of five panels has five plot areas and
    no shared one.
    """
    box = _union_box(children)
    transform = IDENTITY if box is None else Affine.translation(
        -box.center.x, -box.center.y)
    node = Diagram(children=tuple(children), transform=transform, kind=kind)
    source = notes_from or (children[0] if len(children) == 1 else None)
    carry = getattr(node, "carry_notes", None)
    if source is not None and callable(carry):
        carry(source)
    return node


def _rect_anchor(box: Rect, name: str, extra: tuple[str, ...] = ()) -> Vec2:
    """Compass point of a rectangle, with y growing downward as core has it.

    `extra` names alignments the caller handles itself, so they appear in the
    error rather than being reported as unknown."""
    mid = box.center
    table = {
        "center": mid, "c": mid,
        "n": Vec2(mid.x, box.y0), "s": Vec2(mid.x, box.y1),
        "w": Vec2(box.x0, mid.y), "e": Vec2(box.x1, mid.y),
        "nw": Vec2(box.x0, box.y0), "ne": Vec2(box.x1, box.y0),
        "sw": Vec2(box.x0, box.y1), "se": Vec2(box.x1, box.y1),
    }
    if name not in table:
        raise ValueError(
            f"{name!r} is not a compass anchor; use one of: "
            f"{', '.join(sorted(set(table) | set(extra)))}"
        )
    return table[name]


def _resolve_align(value: str, table: dict[str, str], what: str,
                   other: dict[str, str] | None = None,
                   other_what: str = "") -> str:
    if isinstance(value, str) and value in table:
        return table[value]
    hint = ""
    if isinstance(value, str):
        if other is not None and value in other:
            hint = f" ({value!r} aligns {other_what}.)"
        elif value == "baseline":
            hint = (" (baselines only line up across a horizontal stack, where"
                    " items sit side by side.)")
    raise ValueError(
        f"{value!r} is not a valid alignment for {what}; "
        f"use one of: {', '.join(sorted(table))}.{hint}"
    )


def _gap(value: Length, table: dict[str, str]) -> float:
    """A gap in millimetres, with the one likely mistake named.

    `vstack(items, "left")` reads as English and puts an alignment where the
    gap goes; `mm` can only report that "left" is not a length, four frames
    down, which is a long way from the missing keyword."""
    if isinstance(value, str) and value.strip().lower() in table:
        raise ValueError(
            f"a stack's second argument is the gap in millimetres, and "
            f"{value!r} is an alignment; write align={value!r}"
        )
    return mm(value)


def _axis(direction: Vec2) -> tuple[Vec2, Vec2, str]:
    """Unit stack direction, unit cross direction, and which vocabulary applies.

    The cross axis points south for any horizontal stack and east for any
    vertical one, so "top" means up whether you stacked east or west."""
    if not isinstance(direction, Vec2):
        raise TypeError(
            f"stack direction must be a Vec2, not {type(direction).__name__}"
            f" ({direction!r}); use hstack/vstack, or inklet.Vec2(1, 0) to stack "
            "along an axis of your own"
        )
    if direction.length == 0.0:
        raise ValueError("direction must not be the zero vector")
    unit = direction.normalized()
    if abs(unit.y) < _AXIS_EPS:
        return unit, SOUTH, "horizontal"
    if abs(unit.x) < _AXIS_EPS:
        return unit, EAST, "vertical"
    return unit, unit.perp(), "oblique"


def _align_context(axis: str) -> tuple[dict[str, str], str,
                                       dict[str, str] | None, str]:
    if axis == "horizontal":
        return _H_STACK_ALIGN, "a horizontal stack", _X_ALIGN, "a vertical stack"
    if axis == "vertical":
        return _V_STACK_ALIGN, "a vertical stack", _Y_ALIGN, "a horizontal stack"
    return _FREE_ALIGN, "a stack along an oblique direction", None, ""


def _baseline_point(node: Diagram, into: Affine) -> Vec2 | None:
    """Where the first line of text sits, in the frame `into` maps out of.

    Depth-first in the same order as `walk()`, so "first" means the first text
    a reader would meet. Returns None for a subtree with no text in it."""
    world = into @ node.transform
    prim = node.prim
    if isinstance(prim, TextPrim) and prim.lines:
        return world.apply(Vec2(0.0, prim.first_baseline))
    for child in node.children:
        found = _baseline_point(child, world)
        if found is not None:
            return found
    return None


def _frame_point(item: Diagram) -> Vec2:
    """Where the item's drawn frame sits, in the parent's coordinates.

    `inklet.draw` shifts everything it builds onto its own origin and leaves an
    `origin` anchor behind saying where the author's (0, 0) went. Anything with
    no such anchor was never shifted, so its own local origin *is* the frame --
    the reading `draw.as_drawn` takes, and the one that makes an undrawn shape
    line up with a drawn one instead of raising."""
    if ORIGIN_ANCHOR in item.anchors:
        return item.transform.apply(item.anchors[ORIGIN_ANCHOR])
    return item.transform.apply(Vec2(0.0, 0.0))


def _cross_offset(item: Diagram, cross: Vec2, mode: str) -> float:
    """How far to slide an item along the cross axis to land on the align line
    at cross-coordinate zero."""
    if mode == "origin":
        return -_frame_point(item).dot(cross)
    if mode == "baseline":
        point = _baseline_point(item, IDENTITY)
        if point is not None:
            return -point.dot(cross)
        # No text anywhere in there. Centring is what the eye expects of a
        # plain shape sitting beside a label.
        mode = "center"
    if mode == "start":
        return item.extent(-cross)
    if mode == "end":
        return -item.extent(cross)
    return -(item.extent(cross) - item.extent(-cross)) / 2.0


# -- stacking -------------------------------------------------------------


def stack(items: Iterable[Diagram], direction: Vec2, gap: Length = 0.0,
          align: str = "center") -> Diagram:
    """Pack items along `direction`, each one `gap` past the last.

    The spacing is measured with envelope extents: item n+1 is placed so that
    its reach backward along the axis clears item n's reach forward by exactly
    `gap`. That is what makes a rotated shape sit close instead of being held
    off by the empty corners of its box.

    `align` positions each item across the axis: "top"/"n", "center"/"c",
    "bottom"/"s" or "baseline" for a horizontal stack, "left"/"w", "center"/"c"
    or "right"/"e" for a vertical one, and "start"/"center"/"end" for any
    direction at all. A negative `gap` overlaps.

    "origin" is accepted on any axis and aligns the drawn frame rather than the
    box -- across a row of sparklines drawn in data coordinates it lines up
    their y = 0, the way "baseline" lines up type. It reads the `origin` anchor
    every `inklet.draw` shape carries, and falls back to an item's own local
    origin when it has none.

    Empty items occupy no space and consume no gap -- `hstack([a, hstack([]),
    b])` measures the same as `hstack([a, b])`. Use `spacer()` for a gap you
    want to be real. An empty `items` gives back an empty diagram.
    """
    return _stack(items, direction, gap, align, "stack")


def _stack(items: Iterable[Diagram], direction: Vec2, gap: Length,
           align: str, called: str) -> Diagram:
    """The body of `stack`, told which of its three doors it was called at, so
    a complaint names the function the author actually typed."""
    unit, cross, axis = _axis(direction)
    table, what, other, other_what = _align_context(axis)
    mode = _resolve_align(align, table, what, other, other_what)
    step = _gap(gap, table)
    entries = _prepare(items, called)

    placed: list[Diagram] = []
    front: float | None = None
    for item in entries:
        if item.is_empty:
            placed.append(item)
            continue
        back = item.extent(-unit)
        along = 0.0 if front is None else front + step + back
        front = along + item.extent(unit)
        offset = unit * along + cross * _cross_offset(item, cross, mode)
        placed.append(item.placed(Affine.translation(offset.x, offset.y)))
    return _annotated(_centered(placed, "stack"), step, unit)


def _annotated(node: Diagram, gap: float, unit: Vec2 | None = None) -> Diagram:
    """Record the gap the author asked for, on the node that applied it.

    Nothing downstream can recover it from geometry. Two labels 0.50mm apart
    look crowded to `inklet.lint` whether that half-millimetre was `th.gap("2xs")`
    asked for by name or a number that slipped -- and the difference is the
    whole finding, because one of them is a decision and the other is a
    mistake.

    It goes in `Diagram.notes` (core M17), which survives `replace`, a restyle
    and a `build`, so the rule reads it off the *built* tree -- the only tree a
    rule ever sees. `notes` is not part of equality, so a stack still compares
    equal to one built the same way. `node.note(...)` mutates and returns the
    node, which is safe here only because the node was made three lines ago and
    nobody else has it yet. Read it back with
    `getattr(node, "notes", {}).get("gap")`.

    Falls back to the plain-attribute idiom on a core that predates M17, so
    this file builds either way.
    """
    if hasattr(node, "note"):
        node.note("gap", gap)
        if unit is not None:
            node.note("gap_axis", unit)
        return node
    object.__setattr__(node, "stack_gap", gap)          # pre-M17 core
    if unit is not None:
        object.__setattr__(node, "stack_axis", unit)
    return node


def hstack(items: Iterable[Diagram], gap: Length = 0.0,
           align: str = "center") -> Diagram:
    """Left to right. `align` is "top"/"n", "center"/"c", "bottom"/"s",
    "baseline", or "origin" to line up the drawn frames."""
    return _stack(items, EAST, gap, align, "hstack")


def vstack(items: Iterable[Diagram], gap: Length = 0.0,
           align: str = "center") -> Diagram:
    """Top to bottom. `align` is "left"/"w", "center"/"c", "right"/"e", or
    "origin" to line up the drawn frames."""
    return _stack(items, SOUTH, gap, align, "vstack")


def beside(a: Diagram, b: Diagram, direction: Vec2, gap: Length = 0.0) -> Diagram:
    """`b` placed alongside `a` in `direction`, centred across the axis."""
    return stack([a, b], direction, gap=gap)


def overlay(items: Iterable[Diagram], align: str = "center") -> Diagram:
    """Stack items on top of each other, first one at the bottom.

    `align` names the compass point of each item's box that they share:
    "center" by default, but "s" to sit them on a common baseline of boxes, or
    "nw" to line up their top-left corners.

    `align="origin"` lines up the *frames* instead of the boxes: every item is
    put back where it was drawn, so several `place(..., origin=(0, 0))` groups
    over one drawing stay in register. That is the alignment to reach for
    whenever the coordinates mean something -- geometry, its east-anchored
    labels and its west-anchored labels come out as one picture rather than
    three centred on their own differing widths. The result keeps an `origin`
    anchor of its own, so it composes into a further `place` the same way.
    """
    entries = _prepare(items, "overlay")
    if align == "origin":
        return _overlaid_frames(entries)
    placed: list[Diagram] = []
    for item in entries:
        box = _box_of(item)
        if box is None:
            placed.append(item)
            continue
        point = _rect_anchor(box, align, extra=("origin",))
        placed.append(item.placed(Affine.translation(-point.x, -point.y)))
    return _centered(placed, "overlay")


def _overlaid_frames(entries: list[Diagram]) -> Diagram:
    """`overlay(align="origin")`: every item's drawn frame on one point.

    Deliberately built like `draw.drawn_group` rather than like the compass
    branch -- the group has to *keep* the shared frame as its own `origin`
    anchor, or overlaying two registered groups would produce a third that no
    longer knows where its coordinates are.
    """
    placed = []
    for item in entries:
        point = _frame_point(item)
        placed.append(item.placed(Affine.translation(-point.x, -point.y)))
    node = _centered(placed, "overlay")
    # Anchors are stored in the node's own frame, before its transform, which
    # is the frame the children were just moved into: the shared origin is
    # (0, 0) there, exactly as `draw.drawn_group` records it.
    node.anchor(ORIGIN_ANCHOR, Vec2(0.0, 0.0))
    return node


# -- grid -----------------------------------------------------------------


def flow(items: Iterable[Diagram], columns: int = 2, gap: Length = 0.0,
         col_gap: Length | None = None, align: str = "left") -> Diagram:
    """Pack items *down* columns rather than across rows.

    `grid` is row-major: a row is as tall as its tallest cell, so every shorter
    item in that row leaves a band of white paper under it. That is right when
    the cells belong together in rows -- a table -- and wrong when they are
    simply a sequence that has to fit on a page. Eighteen panels of assorted
    heights cost 127mm of blank paper that way, half a journal page.

    Each column is a *contiguous run* of the sequence, and the cuts are chosen
    to make the tallest column as short as possible. Contiguity is the part
    that matters: it is the only packing where reading down the columns gives
    back the order the items were written in. Sending each item to whichever
    column is currently shortest packs marginally tighter on some inputs and
    reorders the sequence on most -- eighteen panels came out lettered
    a, b, c, e, d, f, which is not a figure anyone can read.

    The cuts are exact rather than greedy, by dynamic programming over split
    points. That is O(n^2 * columns) on a sequence that is a page of panels,
    and it is what lets the promise above be unconditional.

    Columns are laid out with `vstack` and then `hstack`ed, which means the
    ordinary alignment rules apply and every item keeps its own width. Nothing
    here computes a coordinate.
    """
    kept = [item for item in _prepare(items, "flow") if not item.is_empty]
    if columns < 1:
        raise DiagramError(f"flow needs at least one column, got {columns}")
    if not kept:
        return Diagram(kind="flow")     # same as an empty `grid`: no bbox at all
    down = mm(gap)
    across = down if col_gap is None else mm(col_gap)
    bounds = _balanced_runs([item.height for item in kept], columns, down)
    lanes = [kept[start:stop] for start, stop in zip((0, *bounds), bounds)]
    packed = [vstack(lane, gap=down, align=align) for lane in lanes if lane]
    if len(packed) == 1:
        return packed[0]
    return hstack(packed, gap=across, align="top")


def _balanced_runs(heights: Sequence[float], columns: int,
                   gap: float) -> list[int]:
    """Where to cut a sequence into `columns` contiguous runs of even height.

    Returns the end index of each run, so `bounds[-1] == len(heights)` always
    and an unused column comes back as an empty run.

    `best[k][i]` is the tallest column achievable by splitting `heights[i:]`
    into k runs; `best[0][n]` is zero and `best[0][i < n]` is infinite, which is
    what forces the last run to reach the end without a special case for it.
    """
    n = len(heights)
    columns = max(1, min(columns, n)) if n else 1
    prefix = [0.0]
    for height in heights:
        prefix.append(prefix[-1] + height + gap)

    def run(start: int, stop: int) -> float:
        return prefix[stop] - prefix[start] - gap if stop > start else 0.0

    infinite = float("inf")
    best = [[infinite] * (n + 1) for _ in range(columns + 1)]
    cut = [[n] * (n + 1) for _ in range(columns + 1)]
    for depth in range(columns + 1):
        best[depth][n] = 0.0
    for depth in range(1, columns + 1):
        for start in range(n - 1, -1, -1):
            for stop in range(start + 1, n + 1):
                value = max(run(start, stop), best[depth - 1][stop])
                # `<=` keeps the *last* optimum, which is the longest first
                # run: earlier columns fill up and the ragged edge lands at
                # the bottom of the last one, the way a page is read.
                if value <= best[depth][start]:
                    best[depth][start], cut[depth][start] = value, stop

    bounds, at = [], 0
    for depth in range(columns, 0, -1):
        at = cut[depth][at]
        bounds.append(at)
    return bounds


def grid(items: Iterable[Diagram], cols: int | None = None,
         rows: int | None = None, gap: Length = 0.0,
         col_gap: Length | None = None, row_gap: Length | None = None,
         align: str = "center", valign: str = "center") -> Diagram:
    """Fill a real grid row-major: shared column widths and row heights.

    A column is as wide as its widest cell and a row as tall as its tallest, so
    columns line up down the whole figure rather than drifting the way nested
    stacks would. A short final row is fine; it just leaves cells empty.

    Give `cols`, or `rows` to derive the columns from, or neither and get a
    squarish grid. `align` places a cell's content horizontally ("left"/"w",
    "center"/"c", "right"/"e"), `valign` vertically ("top"/"n", "center"/"c",
    "bottom"/"s").
    """
    horizontal = _resolve_align(align, _X_ALIGN, "grid columns")
    vertical = _resolve_align(valign, _Y_ALIGN, "grid rows")
    entries = _prepare(items, "grid")
    if not entries:
        return Diagram(kind="grid")

    count = len(entries)
    for name, value in (("cols", cols), ("rows", rows)):
        if value is None:
            continue
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError(
                f"{name} is a count of grid tracks, so it must be an int, "
                f"not {type(value).__name__} ({value!r})"
            )
        if value < 1:
            raise ValueError(f"{name} must be at least 1, not {value}")
    if cols is None:
        cols = math.ceil(count / rows) if rows else math.ceil(math.sqrt(count))
    if rows is not None and rows * cols < count:
        raise ValueError(
            f"{count} items do not fit in a {rows}x{cols} grid"
        )
    n_rows = math.ceil(count / cols)

    gap_x = mm(gap if col_gap is None else col_gap)
    gap_y = mm(gap if row_gap is None else row_gap)

    boxes = [_box_of(item) for item in entries]
    widths = [0.0] * cols
    heights = [0.0] * n_rows
    for index, box in enumerate(boxes):
        if box is None:
            continue
        row, col = divmod(index, cols)
        widths[col] = max(widths[col], box.width)
        heights[row] = max(heights[row], box.height)

    lefts = [0.0] * cols
    for col in range(1, cols):
        lefts[col] = lefts[col - 1] + widths[col - 1] + gap_x
    tops = [0.0] * n_rows
    for row in range(1, n_rows):
        tops[row] = tops[row - 1] + heights[row - 1] + gap_y

    placed: list[Diagram] = []
    for index, (item, box) in enumerate(zip(entries, boxes)):
        if box is None:
            placed.append(item)
            continue
        row, col = divmod(index, cols)
        cell = Rect(lefts[col], tops[row],
                    lefts[col] + widths[col], tops[row] + heights[row])
        dx = _cell_offset(box.x0, box.x1, cell.x0, cell.x1, horizontal)
        dy = _cell_offset(box.y0, box.y1, cell.y0, cell.y1, vertical)
        placed.append(item.placed(Affine.translation(dx, dy)))
    # A grid has two gaps. The one recorded as `gap` is the smaller, because
    # that is the one a crowding finding is measured against: if the rows are
    # 2mm apart and the columns 8mm, "2mm was asked for" is the true statement
    # about the tightest pair on the page. Both are recorded separately too --
    # see `_noted_grid` for why the smaller one alone is not enough.
    node = _annotated(_centered(placed, "grid"), min(gap_x, gap_y))
    return _noted_grid(node, cols, n_rows, gap_x, gap_y)


def _noted_grid(node: Diagram, cols: int, rows: int,
                gap_x: float, gap_y: float) -> Diagram:
    """Record the track structure a diagnostic cannot recover from geometry.

    Which cells are neighbours is the question every grid finding turns on --
    "these two are 2mm apart" means one thing across a row and another down a
    column -- and by the time a rule sees the tree there is nothing but a
    centred group of placed children. Two cells in one row and two in one
    column look identical from the outside; so do a 3x2 grid and a 2x3 one
    holding the same six things, when the contents happen to be square.

    Four notes, on the grid node (core M17, carried through a placement by
    M19):

    * `grid_shape` -- `(rows, cols)`, the track counts.
    * `grid_cells` -- one `(row, col)` per child, in `node.children` order,
      so a rule with a child in hand finds its cell by position. A parallel
      tuple rather than a mapping by node id, because ids are reminted by
      `copy()` while the order of the children is not.
    * `col_gap`, `row_gap` -- the two gaps as asked for, in millimetres. The
      existing `gap` note is `min` of the two and cannot be un-mixed: a rule
      measuring a horizontal pair has to compare against `col_gap`, and
      reading `gap` there reports the row spacing as the column's intent.
    """
    record = getattr(node, "note", None)
    if not callable(record):                             # pragma: no cover
        return node                                      # pre-M17 core
    record("grid_shape", (rows, cols))
    record("grid_cells", tuple(divmod(i, cols)
                               for i in range(len(node.children))))
    record("col_gap", gap_x)
    record("row_gap", gap_y)
    return node


def _cell_offset(lo: float, hi: float, cell_lo: float, cell_hi: float,
                 mode: str) -> float:
    if mode == "start":
        return cell_lo - lo
    if mode == "end":
        return cell_hi - hi
    return (cell_lo + cell_hi) / 2.0 - (lo + hi) / 2.0


# -- padding and framing --------------------------------------------------


def pad(item: Diagram, top: Length, right: Length | None = None,
        bottom: Length | None = None, left: Length | None = None) -> Diagram:
    """Grow the space an item occupies, CSS shorthand order.

    The room is claimed by an envelope override computed as a Minkowski sum, so
    padding grows the item's actual reach rather than rounding it up to a box --
    pad a rotated ellipse by 1mm and it gains exactly 1mm on every axis,
    including the diagonals. Nothing is drawn, and the trace is untouched, so an
    arrow aimed at a padded item still lands on the content's own boundary
    instead of stopping at thin air.

    Padding cannot shrink a diagram; a negative value is clamped to zero.
    Asymmetric padding leaves the content off-centre inside the result, whose
    box, like everything else here, is centred on its origin.
    """
    needs_diagram("pad", item)
    top = max(0.0, mm(top))
    right = top if right is None else max(0.0, mm(right))
    bottom = top if bottom is None else max(0.0, mm(bottom))
    left = right if left is None else max(0.0, mm(left))

    if item.is_empty or (top == right == bottom == left == 0.0):
        return _centered([item], "pad")

    grown = item.envelope.expand(top, right, bottom, left)
    box = grown.bbox()
    offset = IDENTITY if box is None else Affine.translation(
        -box.center.x, -box.center.y)
    node = Diagram(children=(item,), transform=offset, kind="pad",
                   envelope_override=grown)
    carry = getattr(node, "carry_notes", None)
    return carry(item) if callable(carry) else node


def frame(content: Diagram, pad: Length = 0.0, radius: Length | None = None,
          shape: str = "rect", min_width: Length | None = None,
          min_height: Length | None = None, kind: str = "frame") -> Diagram:
    """Draw a shape around content, behind it.

    The shape is sized to the padded content box and grown to `min_width` /
    `min_height` about that box's centre. It carries no style of its own -- no
    fill, no stroke, not even a width -- so whatever the caller or the theme
    puts on the result is what gets painted. `radius` rounds a rect; an ellipse
    is sized to the box rather than around it, so pad it if you want the
    corners of the content covered.
    """
    if shape not in ("rect", "ellipse"):
        raise ValueError(f"shape must be 'rect' or 'ellipse', not {shape!r}")
    if not isinstance(content, Diagram):
        raise TypeError(
            f"{kind}() draws a shape around a diagram and was given "
            f"{type(content).__name__} ({content!r}); its size comes from "
            f"min_width=/min_height=, and a label has to be shaped first -- "
            f"{kind}(inklet.text('a label')), or inklet.box('a label') for both"
        )
    box = _box_of(content)
    if box is None:
        raise DiagramError(
            f"cannot frame {content.id}: an empty diagram has no bounding box"
        )
    padded = box.pad(mm(pad))
    width = max(padded.width, 0.0 if min_width is None else mm(min_width))
    height = max(padded.height, 0.0 if min_height is None else mm(min_height))
    prim = (EllipsePrim(width / 2.0, height / 2.0) if shape == "ellipse"
            else RectPrim(width, height, 0.0 if radius is None else mm(radius)))
    centre = padded.center
    backdrop = Diagram(prim=prim, kind=kind,
                       transform=Affine.translation(centre.x, centre.y))
    return _centered([backdrop, content], "framed", notes_from=content)


def box(content: Diagram, pad: Length = BOX_PAD, radius: Length | None = None,
        shape: str = "rect", min_width: Length | None = None,
        min_height: Length | None = None) -> Diagram:
    """A `frame` with a default 2mm of breathing room, for boxing a label.

    Its shape is tagged `box` rather than `frame` so a theme can tell the two
    apart: a box names a thing and carries the ink, while a frame groups things
    and should recede.
    """
    return frame(content, pad=pad, radius=radius, shape=shape,
                 min_width=min_width, min_height=min_height, kind="box")


# -- placement ------------------------------------------------------------


def align_to(item: Diagram, anchor: str) -> Diagram:
    """Move an item so its named anchor lands on the origin.

    Compass names and any anchor the caller registered both work. This is the
    way out of the centred-on-origin convention the rest of the module keeps:
    `align_to(d, "nw")` puts a diagram's top-left corner at (0, 0).

    A compass name means the corner of the box `item.bbox` reports, so
    `align_to(label.rotated(-90), "nw")` puts the corner you can see at the
    origin rather than the one the label had before it was turned. See
    `placed_anchor`.
    """
    needs_diagram("align_to", item)
    point = placed_anchor(item, anchor)
    return item.placed(Affine.translation(-point.x, -point.y))


def spacer(width: Length = 0.0, height: Length = 0.0) -> Diagram:
    """Empty space that is really there: a phantom box, centred on its origin.

    Unlike an empty diagram, a spacer takes part in stacking, so
    `hstack([a, spacer(width=5), b])` really does open 5mm between them.
    """
    w, h = mm(width), mm(height)
    if w < 0.0 or h < 0.0:
        raise ValueError(f"spacer cannot be negative: {w} x {h}")
    return Diagram(prim=PhantomPrim(Rect.from_size(w, h)), kind="spacer")
