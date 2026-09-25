"""UpSet plots: the sizes of set intersections as bars over a membership matrix.

`upset_layout` does the counting and draws nothing. It accepts either

- a mapping of set name to members, `{"A": {"g1", "g2"}, "B": {"g2"}}`. Each
  element is counted once, in the intersection of exactly the sets that
  contain it, so the intersections are disjoint and their sizes add up to
  the number of distinct elements; or
- a sequence of membership records. A record is `(members, count)`, where
  `members` is a tuple of set names and `count` a number, or a bare tuple of
  set names counted once. Records with the same members are added together.

It returns the sets in display order, each set's size, and the intersections
after sorting, the `min_size` cutoff and `max_intersections`. A set's size is
counted over all the data, not only over the intersections shown.

`upset` draws the layout as three panels on shared band scales: the
intersection sizes as bars on top, the membership matrix below them (one
column per intersection, one row per set, a dark dot for a member and a pale
dot for a non-member, and a line joining the member dots) and, optionally,
the set sizes as horizontal bars on the left of the matrix, with the set names
between the two. The panels are laid out with `column` and `row`, which line
them up on their plot areas, so a bar stands exactly over its column.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from numbers import Real
from typing import Mapping, Sequence

from ..core import Diagram, DiagramError, Vec2, mm
from ..diagnostics.abut import abutting
from ..draw.coords import active_theme
from ..draw.path import polyline
from ..draw.place import place as draw_place
from ..draw.shapes import MARK_LINE_KIND, marker as make_marker
from ..themes.color import mix
from .furniture import AREA_KIND
from .scale import band, linear, nice_step

__all__ = ["upset", "upset_layout", "UpSetLayout", "Intersection",
           "UPSET_SORTS"]

#: Accepted values of `upset(sort=)`: largest intersection first; lowest
#: degree (fewest sets) first, then largest; or the order of the input.
UPSET_SORTS = ("size", "degree", "input")

#: Default column and row pitch of the matrix, in mm.
_PITCH = 3.4

#: Dot diameter as a fraction of the smaller of the column and row pitch.
_DOT_OF_PITCH = 0.56

#: Bar width as a fraction of the column or row pitch.
_BAR_OF_PITCH = 0.62

#: How far past the largest set the set-size axis may run to end on a
#: labelled tick, as a multiple of that set's size.
_SET_OVERSHOOT = 1.25

#: Non-member dots and the row stripes, as blends of the muted colour towards
#: paper. The dots stay visible on the stripes.
_EMPTY_TINT = 0.68
_STRIPE_TINT = 0.9


@dataclass(frozen=True)
class Intersection:
    """One exclusive intersection: the `members` (set names, in set order)
    that an element belongs to and no others, and its `size`."""
    members: tuple[str, ...]
    size: float

    @property
    def degree(self) -> int:
        """How many sets the intersection belongs to."""
        return len(self.members)


@dataclass(frozen=True)
class UpSetLayout:
    """`sets` in display order, top to bottom; `set_sizes` in the same order;
    `intersections` as drawn, left to right; `dropped` the intersections
    removed by `min_size` or `max_intersections`."""
    sets: tuple[str, ...]
    set_sizes: tuple[float, ...]
    intersections: tuple[Intersection, ...]
    dropped: tuple[Intersection, ...]


def _is_record(item) -> bool:
    """Whether `item` is a `(members, count)` pair rather than a bare tuple
    of set names."""
    return (isinstance(item, (tuple, list)) and len(item) == 2
            and isinstance(item[1], Real) and not isinstance(item[1], bool)
            and not isinstance(item[0], Real))


def _counts(data) -> tuple[list[str], dict[frozenset, float], list[frozenset]]:
    """Set names in first-seen order, the count per member set, and the
    member sets in first-seen order."""
    names: list[str] = []
    counts: dict[frozenset, float] = {}
    order: list[frozenset] = []

    def add(members, count: float) -> None:
        key = frozenset(members)
        if key not in counts:
            counts[key] = 0.0
            order.append(key)
        counts[key] += count

    if isinstance(data, Mapping):
        where: dict = {}
        for name, members in data.items():
            name = str(name)
            if isinstance(members, (str, bytes)) or not hasattr(members, "__iter__"):
                raise DiagramError(
                    f"upset set {name!r} needs a collection of members, "
                    f"got {members!r}")
            names.append(name)
            for element in members:
                where.setdefault(element, []).append(name)
        for element, sets in where.items():
            add(sets, 1.0)
        return names, counts, order
    if isinstance(data, (str, bytes)) or not hasattr(data, "__iter__"):
        raise DiagramError(
            "upset data is a mapping of set name to members or a sequence of "
            f"(members, count) records, not {type(data).__name__}")
    for item in data:
        if _is_record(item):
            members, count = item
            count = float(count)
        else:
            members, count = item, 1.0
        if isinstance(members, str):
            members = (members,)
        members = [str(m) for m in members]
        if math.isnan(count) or count < 0:
            raise DiagramError(f"upset counts must be zero or more, got {item!r}")
        if len(set(members)) != len(members):
            raise DiagramError(f"upset record {item!r} names a set twice")
        for name in members:
            if name not in names:
                names.append(name)
        add(members, count)
    return names, counts, order


def upset_layout(data, *, sets: Sequence[str] | None = None,
                 sort: str = "size", sort_sets: bool = True,
                 min_size: float = 1, max_intersections: int | None = None,
                 empty: bool = False) -> UpSetLayout:
    """The sets and intersections of an UpSet plot, without drawing.

    `data` is a mapping of set name to members, or a sequence of
    `(members, count)` records and bare member tuples; see the module
    docstring. `sets=` fixes which sets are shown and in what order; sets
    that are not listed are left out, with the intersections that involve
    them. Without it, `sort_sets=True` puts the largest set at the top and
    `False` keeps the order in which the sets first appear.

    `sort` orders the intersections: `"size"` (largest first, then fewer
    sets), `"degree"` (fewer sets first, then largest) or `"input"` (first
    seen first; for a mapping, the order of the elements). Ties keep the set
    order. Intersections smaller than `min_size` are dropped, then only the
    first `max_intersections` are kept. The intersection of no sets (records
    with no members) is kept only with `empty=True`.
    """
    if sort not in UPSET_SORTS:
        raise DiagramError(
            f"upset sort is one of {', '.join(UPSET_SORTS)}, not {sort!r}")
    if max_intersections is not None and max_intersections < 1:
        raise DiagramError(
            f"max_intersections must be 1 or more, got {max_intersections!r}")
    names, counts, order = _counts(data)
    if sets is not None:
        chosen = [str(s) for s in sets]
        if len(set(chosen)) != len(chosen):
            raise DiagramError(f"upset sets= repeats a name: {chosen}")
        # A listed set with no members is shown with size 0.
        names_shown = chosen
    else:
        names_shown = list(names)
    if not names_shown:
        raise DiagramError("upset data has no sets")
    size_of = {name: 0.0 for name in names_shown}
    for key, count in counts.items():
        for name in key:
            if name in size_of:
                size_of[name] += count
    if sets is None and sort_sets:
        names_shown.sort(key=lambda n: (-size_of[n], names.index(n)))
    rank = {name: k for k, name in enumerate(names_shown)}
    shown = set(names_shown)
    kept: list[tuple[int, Intersection]] = []
    for seen, key in enumerate(order):
        if not key <= shown:
            continue
        if not key and not empty:
            continue
        members = tuple(sorted(key, key=rank.__getitem__))
        kept.append((seen, Intersection(members=members, size=counts[key])))

    def by_sets(item: Intersection) -> tuple:
        return tuple(rank[m] for m in item.members)

    if sort == "size":
        kept.sort(key=lambda p: (-p[1].size, p[1].degree, by_sets(p[1])))
    elif sort == "degree":
        kept.sort(key=lambda p: (p[1].degree, -p[1].size, by_sets(p[1])))
    items = [i for _, i in kept]
    shown_items = [i for i in items if i.size >= min_size]
    dropped = [i for i in items if i.size < min_size]
    if max_intersections is not None:
        dropped = shown_items[max_intersections:] + dropped
        shown_items = shown_items[:max_intersections]
    return UpSetLayout(sets=tuple(names_shown),
                       set_sizes=tuple(size_of[n] for n in names_shown),
                       intersections=tuple(shown_items), dropped=tuple(dropped))


def _ticks(top: float, count: int, most: int,
           end: bool = True) -> tuple[float, list[float]]:
    """The end of a size axis from zero and its round ticks, at most `most`
    of them so the axis never has to thin them.

    With `end=True` the axis runs to a whole number of steps at or past
    `top`, so it ends on a labelled tick. With `end=False` it ends at `top`
    and the ticks stop at or below it, which keeps a narrow axis from
    running far past its longest bar.
    """
    if top <= 0:
        return 1.0, [0.0, 1.0]
    most = max(2, most)
    for asked in range(max(1, count), 0, -1):
        step = nice_step(top, asked)
        steps = (math.ceil(top / step - 1e-9) if end
                 else math.floor(top / step + 1e-9))
        if 1 <= steps and steps + 1 <= most:
            break
    else:
        power = 10.0 ** math.floor(math.log10(top))
        if end:
            step = next(f * power for f in (1.0, 2.0, 5.0, 10.0)
                        if f * power >= top - 1e-9)
        else:
            step = next(f * power for f in (5.0, 2.0, 1.0)
                        if f * power <= top + 1e-9)
        steps = 1
    high = steps * step if end else max(top, steps * step)
    return high, [k * step for k in range(steps + 1)]


def _key(item: Intersection) -> str:
    return " & ".join(item.members) if item.members else "(none)"


def upset(data, *, sets: Sequence[str] | None = None, sort: str = "size",
          sort_sets: bool = True, min_size: float = 1,
          max_intersections: int | None = None, empty: bool = False,
          set_sizes: bool = True, width: float | str | None = None,
          height: float | str = 26, matrix_height: float | str | None = None,
          set_width: float | str = 16, color: str | None = None,
          labels=None, stripes: bool = True,
          bar_label: str | None = "intersection size",
          set_label: str | None = "set size",
          gap: float | str | None = None, count: int = 4) -> Diagram:
    """An UpSet plot: intersection sizes as bars over a membership matrix.

    `data` is a mapping of set name to members, or a sequence of
    `(members, count)` records (bare member tuples count once):

        inklet.upset({"RNA": rna_hits, "ATAC": atac_hits, "ChIP": chip_hits})
        inklet.upset([(("RNA", "ATAC"), 37), (("RNA",), 92), (("ATAC",), 53)])

    Each column is one exclusive intersection: the elements in exactly those
    sets. The matrix marks its sets with dark dots joined by a line and the
    other sets with pale dots. The bar above the column is its size, and the
    bars at the left (`set_sizes=True`) are the set sizes, counted over all
    the data. The set names sit between the set bars and the matrix.

    `sets`, `sort` (`"size"`, `"degree"` or `"input"`), `sort_sets`,
    `min_size`, `max_intersections` and `empty` choose and order what is
    shown; see `inklet.plot.upset_layout`, which returns the same counts
    without drawing.

    Sizes are in mm. `width` is the matrix and bar width (default 3.4 mm per
    intersection), `height` the height of the intersection bars,
    `matrix_height` the matrix height (default 3.4 mm per set) and
    `set_width` the width of the set-size bars. `gap` is the space between
    the three panels. `color` is the ink of the bars and member dots.
    `labels=` writes each intersection size above its bar and takes the
    forms of `Panel.bars(labels=)`, such as `True` or `"{:.0f}"`; the bar
    axis is extended so the tallest label fits. `stripes=True` shades every
    other set row. `bar_label` and `set_label` name the two size axes, and
    `count` is about how many ticks the intersection axis gets.

    Returns one diagram. Its plot area is the union of the three panels'
    areas, so `letters`, `row` and `column` place it like a panel. It
    carries an `upset` note with the sets, set sizes and the shown and
    dropped intersections.
    """
    layout = upset_layout(data, sets=sets, sort=sort, sort_sets=sort_sets,
                          min_size=min_size, max_intersections=max_intersections,
                          empty=empty)
    if not layout.intersections:
        raise DiagramError(
            "upset has no intersections to draw; lower min_size or check the data")
    from .panel import column, panel, row

    theme = active_theme()
    ink = color or theme.ink
    keys = [_key(i) for i in layout.intersections]
    columns = len(keys)
    rows = len(layout.sets)
    pitch = _PITCH
    if labels is not None and labels is not False and width is None:
        # Wide enough that neighbouring value labels keep a gap.
        from .axis import TICK_LABEL_KIND, text_node
        from .bar_labels import label_texts

        texts = label_texts(labels, [[i.size for i in layout.intersections]])[0]
        widest = max((text_node(t, theme.font_size_small, TICK_LABEL_KIND,
                                markup=False).bbox.width for t in texts if t),
                     default=0.0)
        pitch = max(pitch, widest + theme.gap("xs"))
    w = pitch * columns if width is None else mm(width)
    h_matrix = _PITCH * rows if matrix_height is None else mm(matrix_height)
    h_bars = mm(height)
    space = theme.gap("xs") if gap is None else mm(gap)
    if w <= 0 or h_matrix <= 0 or h_bars <= 0:
        raise DiagramError("upset needs a positive width and heights")
    x = band(keys, padding=0.0, outer=0.0)
    # The first set at the top: a y band runs upward.
    y = band(list(reversed(layout.sets)), padding=0.0, outer=0.0)
    column_step = w / columns
    row_step = h_matrix / rows

    # Intersection sizes.
    top = max(i.size for i in layout.intersections)
    if labels is not None and labels is not False:
        # Room above the tallest bar for its value label: the text height
        # plus the gap `bars` leaves past a bar end.
        room = 1.7 * theme.font_size_small
        if room < h_bars:
            top = top * h_bars / (h_bars - room)
    small = theme.font_size_small
    high, marks = _ticks(top, count, int(h_bars // (2.2 * small)) + 1)
    bars = panel(w, h_bars, x=x, y=linear((0.0, high)))
    sizes = [i.size for i in layout.intersections]
    bar_options = {} if labels is None else {"labels": labels,
                                             "label_position": "end"}
    bars.bars(keys, sizes, width=_BAR_OF_PITCH, color=[ink], stroke="none",
              **bar_options)
    bars.axis("left", label=bar_label, ticks=marks)

    # The membership matrix.
    grid = panel(w, h_matrix, x=x, y=y)
    dot = _DOT_OF_PITCH * min(column_step, row_step)
    pale = mix(theme.muted, theme.paper, _EMPTY_TINT)
    band_rows: list = []
    if stripes:
        for k, name in enumerate(layout.sets):
            if k % 2:
                continue
            centre = grid.y.map(name)
            band_rows.append(polyline(
                ((grid.area.x0, centre - row_step / 2), (grid.area.x1, centre - row_step / 2),
                 (grid.area.x1, centre + row_step / 2), (grid.area.x0, centre + row_step / 2)),
                closed=True, filled=True, kind=AREA_KIND,
                fill=mix(theme.muted, theme.paper, _STRIPE_TINT), stroke="none"))
    # Pale dots first, so a line joining two members runs over the pale dots
    # between them, then the member dots over the line ends.
    empties: list = []
    links: list = []
    dots: list = []
    for key, item in zip(keys, layout.intersections):
        at = grid.x.map(key)
        member = set(item.members)
        heights = [grid.y.map(name) for name in item.members]
        if len(heights) >= 2:
            links.append(polyline(((at, min(heights)), (at, max(heights))),
                                  kind=MARK_LINE_KIND, stroke=ink,
                                  stroke_width=theme.thick,
                                  stroke_linecap="butt"))
        for name in layout.sets:
            into = dots if name in member else empties
            into.append((Vec2(at, grid.y.map(name)),
                         make_marker("circle", dot,
                                     fill=ink if name in member else pale)))
    # The dots are a grid at a fixed pitch; their spacing is the design.
    grid.draw(draw_place(band_rows + empties + links + dots, origin=(0, 0),
                         kind=abutting("upset-matrix")))
    grid.axis("left", tick_size=0, tick_pad=theme.gap("xs"), spine=False,
              thin=False)

    if set_sizes:
        biggest = max(layout.set_sizes) or 1.0
        wide = (0.62 * len(f"{biggest:g}") + 1.6) * small
        most = int(mm(set_width) // wide) + 1
        # End on a labelled tick unless that runs the narrow axis well past
        # the largest set; then end at the largest set.
        high, marks = _ticks(biggest, 3, most)
        if high > _SET_OVERSHOOT * biggest:
            high, marks = _ticks(biggest, 3, most, end=False)
        side = panel(mm(set_width), h_matrix, x=linear((high, 0.0)), y=y)
        side.bars(list(layout.sets), list(layout.set_sizes), orient="h",
                  width=_BAR_OF_PITCH, color=[ink], stroke="none")
        side.axis("bottom", label=set_label, ticks=marks)
        lower = row([side, grid], gap=space)
    else:
        lower = row([grid], gap=space)
    node = column([bars, lower], gap=space, align="right")
    note = {"sets": layout.sets, "set_sizes": layout.set_sizes,
            "intersections": [(i.members, i.size) for i in layout.intersections],
            "dropped": [(i.members, i.size) for i in layout.dropped]}
    node.notes["upset"] = note
    return node
